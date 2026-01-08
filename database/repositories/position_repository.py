# -*- coding: utf-8 -*-
"""
Репозиторий для работы с открытыми позициями.
Реализует специфичные методы для управления арбитражными позициями.
"""

import logging
from typing import Optional, List, Dict
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from database.models import Position
from database.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class PositionRepository(BaseRepository[Position]):
    """
    Репозиторий для работы с открытыми позициями.
    
    Предоставляет методы:
    - Поиск позиции по crypto символу
    - Получение всех открытых позиций
    - Создание новой позиции
    - Обновление счетчиков funding rate
    - Удаление позиции (закрытие)
    """
    
    def __init__(self):
        """Инициализация репозитория с моделью Position."""
        super().__init__(model=Position)
    
    def get_by_crypto(self, crypto: str) -> Optional[Position]:
        """
        Получить позицию по символу криптовалюты.
        
        Args:
            crypto: Символ криптовалюты (например, "BTC")
            
        Returns:
            Position | None: Найденная позиция или None
        """
        try:
            logger.debug(f"[REPO] Поиск позиции для {crypto}")
            position = self.find_one(crypto=crypto)
            
            if position:
                logger.debug(f"[REPO] Позиция найдена: {crypto}")
            else:
                logger.debug(f"[REPO] Позиция не найдена: {crypto}")
            
            return position
        except Exception as e:
            logger.error(f"[REPO] Ошибка поиска позиции {crypto}: {e}")
            return None
    
    def has_position(self, crypto: str) -> bool:
        """
        Проверить существование открытой позиции для криптовалюты.
        
        Args:
            crypto: Символ криптовалюты
            
        Returns:
            bool: True если позиция существует
        """
        return self.exists(crypto=crypto)
    
    def get_all_open(self) -> List[Position]:
        """
        Получить все открытые позиции.
        
        Returns:
            List[Position]: Список всех открытых позиций
        """
        try:
            positions = self.get_all()
            logger.info(f"[REPO] Получено {len(positions)} открытых позиций")
            return positions
        except Exception as e:
            logger.error(f"[REPO] Ошибка получения открытых позиций: {e}")
            return []
    
    def get_open_cryptos(self) -> List[str]:
        """
        Получить список символов всех открытых позиций.
        
        Returns:
            List[str]: Список символов криптовалют
        """
        try:
            positions = self.get_all_open()
            cryptos = [pos.crypto for pos in positions]
            logger.debug(f"[REPO] Открытые позиции: {cryptos}")
            return cryptos
        except Exception as e:
            logger.error(f"[REPO] Ошибка получения списка открытых позиций: {e}")
            return []
    
    def create_position(
        self,
        crypto: str,
        spot_entry_price: float,
        futures_entry_price: float,
        spot_qty: float,
        futures_qty: float,
        entry_spread_pct: float,
        entry_timestamp: Optional[datetime] = None,
        # 🆕 Параметры для системы докупок
        total_entries: int = 1,
        average_spot_entry_price: Optional[float] = None,
        average_futures_entry_price: Optional[float] = None,
        last_addition_timestamp: Optional[datetime] = None,
        last_entry_spread_pct: Optional[float] = None
    ) -> Optional[Position]:
        """
        Создать новую позицию.
        
        Args:
            crypto: Символ криптовалюты
            spot_entry_price: Цена входа на споте
            futures_entry_price: Цена входа на фьючерсе
            spot_qty: Количество на споте
            futures_qty: Количество на фьючерсе
            entry_spread_pct: Спред при входе (%)
            entry_timestamp: Время входа (опционально)
            
        Returns:
            Position | None: Созданная позиция или None при ошибке
        """
        try:
            # Проверка существования позиции
            if self.has_position(crypto):
                logger.warning(f"[REPO] Позиция {crypto} уже существует")
                return None
            
            position = Position(
                crypto=crypto,
                spot_entry_price=spot_entry_price,
                futures_entry_price=futures_entry_price,
                spot_qty=spot_qty,
                futures_qty=futures_qty,
                entry_spread_pct=entry_spread_pct,
                entry_timestamp=entry_timestamp or datetime.now(),
                funding_payments_count=0,
                low_fr_count=0,
                consecutive_low_fr=False,
                last_funding_check_time=None,
                # 🆕 Поля для системы докупок
                total_entries=total_entries,
                average_spot_entry_price=average_spot_entry_price,
                average_futures_entry_price=average_futures_entry_price,
                last_addition_timestamp=last_addition_timestamp,
                last_entry_spread_pct=last_entry_spread_pct
            )
            
            saved_position = self.save(position)
            logger.info(f"[REPO] ✅ Позиция создана: {crypto} | ID={saved_position.id}")
            return saved_position
            
        except IntegrityError as e:
            logger.error(f"[REPO] ❌ Позиция {crypto} уже существует (constraint): {e}")
            return None
        except SQLAlchemyError as e:
            logger.error(f"[REPO] ❌ Ошибка создания позиции {crypto}: {e}")
            return None
    
    def update_position_quantities(
        self,
        crypto: str,
        spot_qty: float,
        futures_qty: float
    ) -> bool:
        """
        Обновить количество монет в позиции (для докупки).
        
        Args:
            crypto: Символ криптовалюты
            spot_qty: Новое количество на споте
            futures_qty: Новое количество на фьючерсе
            
        Returns:
            bool: True если обновлено успешно
        """
        try:
            position = self.get_by_crypto(crypto)
            
            if not position:
                logger.error(f"[REPO] Позиция {crypto} не найдена для обновления qty")
                return False
            
            position.spot_qty = spot_qty
            position.futures_qty = futures_qty
            
            self.save(position)
            logger.info(f"[REPO] ✅ Обновлено qty для {crypto}: spot={spot_qty}, futures={futures_qty}")
            return True
            
        except SQLAlchemyError as e:
            logger.error(f"[REPO] ❌ Ошибка обновления qty {crypto}: {e}")
            return False
    
    def increment_funding_count(
        self,
        crypto: str,
        current_fr: float,
        low_fr_threshold: float
    ) -> bool:
        """
        Увеличить счетчик выплат фандинга и отследить низкий FR.
        
        Args:
            crypto: Символ криптовалюты
            current_fr: Текущий funding rate (%)
            low_fr_threshold: Порог низкого FR (из config)
            
        Returns:
            bool: True если обновлено успешно
        """
        try:
            position = self.get_by_crypto(crypto)
            
            if not position:
                logger.error(f"[REPO] Позиция {crypto} не найдена для обновления funding")
                return False
            
            # Увеличиваем общий счетчик
            position.funding_payments_count += 1
            position.last_funding_check_time = datetime.now()
            
            # Отслеживаем низкий FR
            if current_fr <= low_fr_threshold:
                position.low_fr_count += 1
                logger.debug(
                    f"[REPO] [{crypto}] FR {current_fr:.4f}% <= {low_fr_threshold}%, "
                    f"счетчик низкого FR: {position.low_fr_count}"
                )
            else:
                # FR поднялся - сбрасываем счетчик
                position.low_fr_count = 0
                position.consecutive_low_fr = False
                logger.debug(f"[REPO] [{crypto}] FR {current_fr:.4f}% > {low_fr_threshold}%, счетчик сброшен")
            
            self.save(position)
            logger.debug(f"[REPO] ✅ Обновлен funding счетчик для {crypto}")
            return True
            
        except SQLAlchemyError as e:
            logger.error(f"[REPO] ❌ Ошибка обновления funding {crypto}: {e}")
            return False
    
    def activate_soft_close_mode(self, crypto: str) -> bool:
        """
        Активировать мягкий режим закрытия позиции.
        
        Args:
            crypto: Символ криптовалюты
            
        Returns:
            bool: True если активировано успешно
        """
        try:
            position = self.get_by_crypto(crypto)
            
            if not position:
                logger.error(f"[REPO] Позиция {crypto} не найдена для активации мягкого режима")
                return False
            
            position.consecutive_low_fr = True
            self.save(position)
            
            logger.info(f"[REPO] 🟡 Мягкий режим активирован для {crypto}")
            return True
            
        except SQLAlchemyError as e:
            logger.error(f"[REPO] ❌ Ошибка активации мягкого режима {crypto}: {e}")
            return False
    
    def delete_by_crypto(self, crypto: str) -> bool:
        """
        Удалить позицию по символу криптовалюты.
        
        Args:
            crypto: Символ криптовалюты
            
        Returns:
            bool: True если удалено успешно
        """
        try:
            position = self.get_by_crypto(crypto)
            
            if not position:
                logger.warning(f"[REPO] Позиция {crypto} не найдена для удаления")
                return False
            
            result = self.delete(position.id)
            
            if result:
                logger.info(f"[REPO] ✅ Позиция удалена: {crypto}")
            
            return result
            
        except SQLAlchemyError as e:
            logger.error(f"[REPO] ❌ Ошибка удаления позиции {crypto}: {e}")
            return False
    
    def get_positions_count(self) -> int:
        """
        Получить количество открытых позиций.
        
        Returns:
            int: Количество позиций
        """
        return self.count()
    
    def position_to_dict(self, crypto: str) -> Optional[Dict]:
        """
        Получить позицию в формате словаря (совместимость с JSON).
        
        Args:
            crypto: Символ криптовалюты
            
        Returns:
            Dict | None: Словарь с данными позиции или None
        """
        position = self.get_by_crypto(crypto)
        
        if position:
            return position.to_dict()
        
        return None
