# -*- coding: utf-8 -*-

"""Управление множественных позиций через базу данных"""

import logging
import threading
from datetime import datetime
from typing import Dict, Optional, List

from database.repositories.position_repository import PositionRepository
from database.repositories.history_repository import HistoryRepository

logger = logging.getLogger(__name__)


class MultiPositionManager:
    """
    Менеджер для управления несколькими позициями одновременно.
    
    Рефакторенная версия с использованием Repository Pattern.
    Все данные хранятся в БД вместо JSON файлов.
    """
    
    def __init__(
        self,
        position_repo: Optional[PositionRepository] = None,
        history_repo: Optional[HistoryRepository] = None
    ):
        """
        Args:
            position_repo: Репозиторий для работы с позициями (опционально)
            history_repo: Репозиторий для работы с историей (опционально)
        """
        # Dependency Injection: позволяет подменить репозитории для тестов
        self.position_repo = position_repo or PositionRepository()
        self.history_repo = history_repo or HistoryRepository()
        
        # RLock для thread-safety (позволяет повторный захват)
        self.lock = threading.RLock()
        
        # Логируем количество существующих позиций при инициализации
        positions_count = self.position_repo.get_positions_count()
        if positions_count > 0:
            logger.info(f"✅ Найдено открытых позиций: {positions_count}")
            cryptos = self.position_repo.get_open_cryptos()
            logger.info(f"📋 Список: {', '.join(cryptos)}")
    
    def save_position(
        self,
        crypto: str,
        spot_price: float,
        futures_price: float,
        spot_qty: float,
        futures_qty: float,
        spread_pct: float,
        add_buys: List[float] = None
    ) -> bool:
        """
        Сохраняет позицию для конкретной криптовалюты.
        
        Args:
            crypto: Символ криптовалюты
            spot_price: Цена входа на споте
            futures_price: Цена входа на фьючерсе
            spot_qty: Количество на споте
            futures_qty: Количество на фьючерсе
            spread_pct: Спред при входе (%)
            add_buys: Список уровней докупок (опционально, пока не используется в БД)
            
        Returns:
            bool: True если сохранено успешно
        """
        if add_buys is None:
            add_buys = []
        
        with self.lock:
            try:
                # Проверяем существует ли позиция
                existing_position = self.position_repo.get_by_crypto(crypto)
                
                if existing_position:
                    # Обновляем существующую позицию
                    existing_position.spot_entry_price = spot_price
                    existing_position.futures_entry_price = futures_price
                    existing_position.spot_qty = spot_qty
                    existing_position.futures_qty = futures_qty
                    existing_position.entry_spread_pct = spread_pct
                    
                    self.position_repo.save(existing_position)
                    logger.info(f"[SAVE] Позиция обновлена: {crypto}")
                else:
                    # Создаем новую позицию
                    position = self.position_repo.create_position(
                        crypto=crypto,
                        spot_entry_price=spot_price,
                        futures_entry_price=futures_price,
                        spot_qty=spot_qty,
                        futures_qty=futures_qty,
                        entry_spread_pct=spread_pct
                    )
                    
                    if not position:
                        logger.error(f"[SAVE] Не удалось создать позицию {crypto}")
                        return False
                    
                    logger.info(f"[SAVE] Позиция создана: {crypto}")
                
                return True
                
            except Exception as e:
                logger.error(f"Ошибка сохранения позиции {crypto}: {e}")
                return False
    
    def increment_funding_count(self, crypto: str, current_fr: float) -> bool:
        """
        Увеличивает счетчик выплат фандинга и отслеживает низкий FR.
        
        Args:
            crypto: Символ криптовалюты
            current_fr: Текущий funding rate (%)
            
        Returns:
            bool: True если обновление успешно
        """
        from config import LOW_FR_TRACKING_THRESHOLD, MIN_FUNDING_PAYMENTS_FOR_CLOSE
        
        with self.lock:
            try:
                # Используем метод репозитория
                success = self.position_repo.increment_funding_count(
                    crypto=crypto,
                    current_fr=current_fr,
                    low_fr_threshold=LOW_FR_TRACKING_THRESHOLD
                )
                
                if not success:
                    return False
                
                # Проверяем нужно ли активировать мягкий режим
                position = self.position_repo.get_by_crypto(crypto)
                if position and position.low_fr_count >= MIN_FUNDING_PAYMENTS_FOR_CLOSE:
                    if not position.consecutive_low_fr:
                        self.position_repo.activate_soft_close_mode(crypto)
                
                return True
                
            except Exception as e:
                logger.error(f"Ошибка обновления funding {crypto}: {e}")
                return False
    
    def get_position(self, crypto: str) -> Optional[dict]:
        """
        Получает позицию для конкретной криптовалюты в формате dict.
        
        Args:
            crypto: Символ криптовалюты
            
        Returns:
            dict | None: Данные позиции или None
        """
        with self.lock:
            position = self.position_repo.get_by_crypto(crypto)
            if position:
                return position.to_dict()
            return None
    
    def has_position(self, crypto: str) -> bool:
        """
        Проверяет есть ли открытая позиция для криптовалюты.
        
        Args:
            crypto: Символ криптовалюты
            
        Returns:
            bool: True если позиция существует
        """
        with self.lock:
            return self.position_repo.has_position(crypto)
    
    def get_all_positions(self) -> Dict[str, dict]:
        """
        Возвращает все открытые позиции в формате dict.
        
        Returns:
            Dict[str, dict]: Словарь {crypto: position_data}
        """
        with self.lock:
            positions = self.position_repo.get_all_open()
            return {pos.crypto: pos.to_dict() for pos in positions}
    
    def get_open_cryptos(self) -> List[str]:
        """
        Возвращает список криптовалют с открытыми позициями.
        
        Returns:
            List[str]: Список символов
        """
        with self.lock:
            return self.position_repo.get_open_cryptos()
    
    def clear_position(self, crypto: str) -> bool:
        """
        Удаляет позицию для конкретной криптовалюты.
        
        Args:
            crypto: Символ криптовалюты
            
        Returns:
            bool: True если удалено успешно
        """
        with self.lock:
            try:
                success = self.position_repo.delete_by_crypto(crypto)
                if success:
                    logger.info(f"[CLEAR] Позиция очищена: {crypto}")
                return success
            except Exception as e:
                logger.error(f"Ошибка очистки позиции {crypto}: {e}")
                return False
    
    def update_quantities(
        self,
        crypto: str,
        additional_spot_qty: float,
        additional_futures_qty: float
    ) -> bool:
        """
        Обновляет количество монет после докупки.
        
        Args:
            crypto: Символ криптовалюты
            additional_spot_qty: Дополнительное количество спот
            additional_futures_qty: Дополнительное количество фьючерс
            
        Returns:
            bool: True если обновлено успешно
        """
        with self.lock:
            try:
                position = self.position_repo.get_by_crypto(crypto)
                
                if not position:
                    logger.error(f"Позиция {crypto} не найдена для обновления")
                    return False
                
                # Обновляем количество
                new_spot_qty = position.spot_qty + additional_spot_qty
                new_futures_qty = position.futures_qty + additional_futures_qty
                
                success = self.position_repo.update_position_quantities(
                    crypto=crypto,
                    spot_qty=new_spot_qty,
                    futures_qty=new_futures_qty
                )
                
                if success:
                    logger.info(
                        f"[UPDATE] Обновлено qty для {crypto}: "
                        f"spot={new_spot_qty:.4f}, futures={new_futures_qty:.4f}"
                    )
                
                return success
                
            except Exception as e:
                logger.error(f"Ошибка обновления количества {crypto}: {e}")
                return False
    
    def add_to_position(
        self,
        crypto: str,
        new_spot_price: float,
        new_futures_price: float,
        new_spot_qty: float,
        new_futures_qty: float,
        new_spread_pct: float
    ) -> bool:
        """
        Докупка к существующей позиции с усреднением цен.
        
        Формула усреднения:
        average_price = (old_price * old_qty + new_price * new_qty) / (old_qty + new_qty)
        
        Args:
            crypto: Символ криптовалюты
            new_spot_price: Цена докупки спот
            new_futures_price: Цена докупки фьючерс
            new_spot_qty: Количество докупки спот
            new_futures_qty: Количество докупки фьючерс
            new_spread_pct: Спред при докупке
            
        Returns:
            bool: True если докупка успешна
        """
        with self.lock:
            try:
                from datetime import datetime
                
                # Получаем текущую позицию
                position = self.position_repo.get_by_crypto(crypto)
                if not position:
                    logger.error(f"[{crypto}] Позиция не найдена для докупки")
                    return False
                
                # Сохраняем старые значения
                old_spot_qty = position.spot_qty
                old_futures_qty = position.futures_qty
                old_avg_spot_price = position.average_spot_entry_price
                old_avg_futures_price = position.average_futures_entry_price
                
                # Рассчитываем новые усредненные цены
                total_spot_qty = old_spot_qty + new_spot_qty
                total_futures_qty = old_futures_qty + new_futures_qty
                
                new_avg_spot_price = (
                    (old_avg_spot_price * old_spot_qty + new_spot_price * new_spot_qty) / 
                    total_spot_qty
                )
                
                new_avg_futures_price = (
                    (old_avg_futures_price * old_futures_qty + new_futures_price * new_futures_qty) / 
                    total_futures_qty
                )
                
                # Обновляем позицию в БД
                position.spot_qty = total_spot_qty
                position.futures_qty = total_futures_qty
                position.average_spot_entry_price = new_avg_spot_price
                position.average_futures_entry_price = new_avg_futures_price
                position.last_entry_spread_pct = new_spread_pct
                position.total_entries += 1
                position.last_addition_timestamp = datetime.now()
                position.updated_at = datetime.now()
                
                # Сохраняем изменения
                self.position_repo.save(position)
                
                # Логирование
                logger.info("=" * 70)
                logger.info(f"📈 ДОКУПКА ПОЗИЦИИ: {crypto} (вход #{position.total_entries})")
                logger.info("=" * 70)
                logger.info(f"📊 УСРЕДНЕНИЕ ЦЕН:")
                logger.info(
                    f"  Спот: {old_avg_spot_price:.6f} → {new_avg_spot_price:.6f} "
                    f"(новая: {new_spot_price:.6f})"
                )
                logger.info(
                    f"  Фьючерс: {old_avg_futures_price:.6f} → {new_avg_futures_price:.6f} "
                    f"(новая: {new_futures_price:.6f})"
                )
                logger.info(f"")
                logger.info(f"📦 КОЛИЧЕСТВО:")
                logger.info(
                    f"  Спот: {old_spot_qty:.4f} + {new_spot_qty:.4f} = {total_spot_qty:.4f}"
                )
                logger.info(
                    f"  Фьючерс: {old_futures_qty:.4f} + {new_futures_qty:.4f} = {total_futures_qty:.4f}"
                )
                logger.info(f"")
                logger.info(f"📈 СПРЕД: {new_spread_pct:.4f}%")
                logger.info(f"🔢 Всего входов: {position.total_entries}")
                logger.info("=" * 70)
                
                return True
                
            except Exception as e:
                logger.error(f"[{crypto}] Ошибка докупки позиции: {e}", exc_info=True)
                return False
    
    def add_additional_buy(self, crypto: str, spread_level: float) -> bool:
        """
        Добавляет уровень докупки.
        
        Note: Пока просто логируем, т.к. addition_buy_spreads не в БД модели.
              Можно добавить позже отдельную таблицу или JSON поле.
        
        Args:
            crypto: Символ криптовалюты
            spread_level: Уровень спреда докупки
            
        Returns:
            bool: True если добавлено
        """
        with self.lock:
            if not self.has_position(crypto):
                return False
            
            logger.info(f"[{crypto}] Докупка на уровне спреда: {spread_level:.2f}%")
            # TODO: Добавить таблицу additional_buys если потребуется
            return True
    
    def get_positions_count(self) -> int:
        """
        Возвращает количество открытых позиций.
        
        Returns:
            int: Количество позиций
        """
        with self.lock:
            return self.position_repo.get_positions_count()
    
    def close_position_with_pnl(
        self,
        crypto: str,
        close_spot_price: float,
        close_futures_price: float
    ) -> Optional[dict]:
        """
        Закрывает позицию, считает PnL с учетом реального фандинга и сохраняет в историю.
        
        Args:
            crypto: Символ криптовалюты
            close_spot_price: Цена закрытия спот
            close_futures_price: Цена закрытия фьючерс
            
        Returns:
            dict | None: PnL данные или None при ошибке
        """
        from calculators.pnl_calculator import PnLCalculator
        from calculators.funding_calculator import RealizedFundingCalculator
        from config import COMMISSION_PCT
        
        with self.lock:
            try:
                # Получаем позицию из БД
                position = self.position_repo.get_by_crypto(crypto)
                
                if not position:
                    logger.error(f"Позиция {crypto} не найдена для закрытия")
                    return None
                
                # 1. Расчет реального фандинга через API
                entry_timestamp = position.entry_timestamp.isoformat()
                logger.info(f"[{crypto}] 💰 Рассчитываем накопленный фандинг с момента открытия...")
                
                try:
                    accumulated_funding = RealizedFundingCalculator.get_accumulated_funding(
                        crypto=crypto,
                        start_time_iso=entry_timestamp,
                        end_time_iso=None  # До текущего момента
                    )
                    
                    if accumulated_funding is None:
                        logger.error(f"[{crypto}] ❌ Не удалось получить данные фандинга!")
                        logger.warning(f"[{crypto}] ⚠️ PnL будет рассчитан БЕЗ учета фандинга")
                        accumulated_funding = 0.0
                        funding_error = True
                    else:
                        logger.info(f"[{crypto}] ✅ Накопленный фандинг: {accumulated_funding:.4f} USDT")
                        funding_error = False
                        
                except Exception as e:
                    logger.error(f"[{crypto}] ❌ Ошибка расчета фандинга: {e}")
                    accumulated_funding = 0.0
                    funding_error = True
                
                # 2. Комиссия
                commission_rate = COMMISSION_PCT / 100.0
                
                # 3. Расчет PnL
                pnl_result = PnLCalculator.calculate_pnl(
                    spot_entry_price=position.average_spot_entry_price,
                    spot_exit_price=close_spot_price,
                    futures_entry_price=position.average_futures_entry_price,
                    futures_exit_price=close_futures_price,
                    spot_qty=position.spot_qty,
                    futures_qty=position.futures_qty,
                    commission_rate=commission_rate,
                    total_funding_received=accumulated_funding
                )
                
                # 4. Расчет изменения спреда
                close_spread_pct = (close_futures_price - close_spot_price) / close_spot_price * 100
                spread_info = PnLCalculator.calculate_spread_change(
                    entry_spread_pct=position.entry_spread_pct,
                    close_spread_pct=close_spread_pct
                )
                
                # 5. Сохранение в историю через репозиторий
                close_timestamp = datetime.now()
                
                self.history_repo.save_closed_position(
                    crypto=crypto,
                    entry_timestamp=position.entry_timestamp,
                    close_timestamp=close_timestamp,
                    spot_entry_price=position.spot_entry_price,
                    futures_entry_price=position.futures_entry_price,
                    spot_exit_price=close_spot_price,
                    futures_exit_price=close_futures_price,
                    spot_qty=position.spot_qty,
                    futures_qty=position.futures_qty,
                    entry_spread_pct=position.entry_spread_pct,
                    close_spread_pct=close_spread_pct,
                    pnl_data=pnl_result,
                    funding_payments_count=position.funding_payments_count
                )
                
                # 6. Детальный лог
                logger.info("=" * 70)
                logger.info(f"💰 ЗАКРЫТА ПОЗИЦИЯ: {crypto}")
                logger.info("=" * 70)

                # 🆕 Показываем количество входов если была докупка
                if position.total_entries > 1:
                    logger.info(f"🔢 КОЛИЧЕСТВО ВХОДОВ: {position.total_entries}")
                    logger.info(f"  Первый вход: Спот {position.spot_entry_price:.6f}, Фьючерс {position.futures_entry_price:.6f}")
                    logger.info(f"  Усредненная: Спот {position.average_spot_entry_price:.6f}, Фьючерс {position.average_futures_entry_price:.6f}")
                    logger.info(f"")

                logger.info(f"📊 ЦЕНЫ:")
                logger.info(
                    f"  Спот: {position.average_spot_entry_price:.6f} → {close_spot_price:.6f} "
                    f"({((close_spot_price/position.average_spot_entry_price-1)*100):+.2f}%)"
                )
                logger.info(
                    f"  Фьючерс: {position.average_futures_entry_price:.6f} → {close_futures_price:.6f} "
                    f"({((close_futures_price/position.average_futures_entry_price-1)*100):+.2f}%)"
                )
                logger.info(f"")
                logger.info(f"📈 СПРЕД:")
                logger.info(f"   Вход: {position.entry_spread_pct:.4f}%")
                logger.info(f"   Выход: {close_spread_pct:.4f}%")
                logger.info(f"   Изменение: {spread_info['spread_change']:+.4f}% ({spread_info['spread_direction']})")
                logger.info(f"")
                logger.info(f"💵 PnL BREAKDOWN:")
                logger.info(f"   ├─ Спот PnL: {pnl_result['spot_pnl']:+.4f} USDT")
                logger.info(f"   ├─ Фьючерс PnL: {pnl_result['futures_pnl']:+.4f} USDT")
                logger.info(f"   ├─ Price PnL: {pnl_result['price_pnl']:+.4f} USDT")
                
                if funding_error:
                    logger.warning(f"   ├─ Funding: ⚠️ ОШИБКА РАСЧЕТА")
                else:
                    logger.info(f"   ├─ Funding: {pnl_result['funding']:+.4f} USDT")
                
                logger.info(f"   ├─ Commission: -{pnl_result['commission']:.4f} USDT")
                logger.info(
                    f"   └─ NET PnL: {pnl_result['net_pnl']:+.4f} USDT "
                    f"{'✅' if pnl_result['net_pnl'] > 0 else '❌'}"
                )
                logger.info("=" * 70)
                
                # 7. Удаляем открытую позицию из БД
                self.clear_position(crypto)
                
                return pnl_result
                
            except Exception as e:
                logger.error(f"Ошибка закрытия позиции {crypto}: {e}", exc_info=True)
                return None
