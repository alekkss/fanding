# -*- coding: utf-8 -*-
"""
Репозиторий для работы с blacklist криптовалют.
Управляет списком исключенных торговых пар.
"""

import logging
from typing import Optional, List, Dict, Set
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from database.models import Blacklist
from database.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class BlacklistRepository(BaseRepository[Blacklist]):
    """
    Репозиторий для работы с blacklist криптовалют.
    
    Предоставляет методы:
    - Проверка наличия в blacklist
    - Добавление в blacklist
    - Удаление из blacklist
    - Получение всего списка blacklist
    - Получение деталей о причине блокировки
    """
    
    def __init__(self):
        """Инициализация репозитория с моделью Blacklist."""
        super().__init__(model=Blacklist)
    
    def is_blacklisted(self, crypto: str) -> bool:
        """
        Проверить находится ли криптовалюта в blacklist.
        
        Args:
            crypto: Символ криптовалюты (например, "BTC")
            
        Returns:
            bool: True если в blacklist
        """
        try:
            exists = self.exists(crypto=crypto)
            logger.debug(f"[BLACKLIST REPO] {crypto} в blacklist: {exists}")
            return exists
        except Exception as e:
            logger.error(f"[BLACKLIST REPO] Ошибка проверки {crypto}: {e}")
            return False
    
    def get_by_crypto(self, crypto: str) -> Optional[Blacklist]:
        """
        Получить запись blacklist по символу криптовалюты.
        
        Args:
            crypto: Символ криптовалюты
            
        Returns:
            Blacklist | None: Запись blacklist или None
        """
        try:
            blacklist_entry = self.find_one(crypto=crypto)
            
            if blacklist_entry:
                logger.debug(f"[BLACKLIST REPO] Запись найдена для {crypto}")
            else:
                logger.debug(f"[BLACKLIST REPO] Запись не найдена для {crypto}")
            
            return blacklist_entry
        except Exception as e:
            logger.error(f"[BLACKLIST REPO] Ошибка поиска {crypto}: {e}")
            return None
    
    def add_to_blacklist(
        self,
        crypto: str,
        reason: str,
        error_code: Optional[int] = None,
        timestamp: Optional[datetime] = None
    ) -> bool:
        """
        Добавить криптовалюту в blacklist.
        
        Args:
            crypto: Символ криптовалюты
            reason: Причина добавления в blacklist
            error_code: Код ошибки (опционально)
            timestamp: Время добавления (опционально, по умолчанию текущее)
            
        Returns:
            bool: True если добавлено успешно, False если уже в списке
        """
        try:
            # Проверяем существование
            if self.is_blacklisted(crypto):
                logger.warning(f"[BLACKLIST REPO] 🚫 {crypto} уже в blacklist")
                return False
            
            # Создаем новую запись
            blacklist_entry = Blacklist(
                crypto=crypto,
                reason=reason,
                error_code=error_code,
                timestamp=timestamp or datetime.now()
            )
            
            self.save(blacklist_entry)
            
            logger.warning(f"[BLACKLIST REPO] 🚫 ДОБАВЛЕН В BLACKLIST: {crypto}")
            logger.warning(f"[BLACKLIST REPO]  └─ Причина: {reason}")
            if error_code:
                logger.warning(f"[BLACKLIST REPO]  └─ Код ошибки: {error_code}")
            
            return True
            
        except IntegrityError as e:
            logger.error(f"[BLACKLIST REPO] ❌ {crypto} уже существует (constraint): {e}")
            return False
        except SQLAlchemyError as e:
            logger.error(f"[BLACKLIST REPO] ❌ Ошибка добавления {crypto}: {e}")
            return False
    
    def remove_from_blacklist(self, crypto: str) -> bool:
        """
        Удалить криптовалюту из blacklist.
        
        Args:
            crypto: Символ криптовалюты
            
        Returns:
            bool: True если удалено успешно, False если не найдено
        """
        try:
            blacklist_entry = self.get_by_crypto(crypto)
            
            if not blacklist_entry:
                logger.warning(f"[BLACKLIST REPO] {crypto} не найден в blacklist для удаления")
                return False
            
            result = self.delete(blacklist_entry.id)
            
            if result:
                logger.info(f"[BLACKLIST REPO] ✅ {crypto} удален из blacklist")
            
            return result
            
        except SQLAlchemyError as e:
            logger.error(f"[BLACKLIST REPO] ❌ Ошибка удаления {crypto}: {e}")
            return False
    
    def get_all_blacklisted(self) -> Set[str]:
        """
        Получить множество всех криптовалют в blacklist.
        
        Returns:
            Set[str]: Множество символов криптовалют
        """
        try:
            blacklist_entries = self.get_all()
            cryptos = {entry.crypto for entry in blacklist_entries}
            
            logger.debug(f"[BLACKLIST REPO] Всего в blacklist: {len(cryptos)}")
            if cryptos:
                logger.debug(f"[BLACKLIST REPO] Список: {', '.join(sorted(cryptos))}")
            
            return cryptos
            
        except Exception as e:
            logger.error(f"[BLACKLIST REPO] Ошибка получения blacklist: {e}")
            return set()
    
    def get_blacklist_details(self, crypto: str) -> Optional[Dict]:
        """
        Получить детали о причине добавления в blacklist.
        
        Args:
            crypto: Символ криптовалюты
            
        Returns:
            Dict | None: Словарь с деталями или None
        """
        try:
            blacklist_entry = self.get_by_crypto(crypto)
            
            if not blacklist_entry:
                return None
            
            details = blacklist_entry.to_dict()
            logger.debug(f"[BLACKLIST REPO] Детали для {crypto}: {details}")
            return details
            
        except Exception as e:
            logger.error(f"[BLACKLIST REPO] Ошибка получения деталей {crypto}: {e}")
            return None
    
    def get_all_details(self) -> Dict[str, Dict]:
        """
        Получить детали всех записей blacklist в формате словаря.
        
        Returns:
            Dict[str, Dict]: Словарь {crypto: {reason, error_code, timestamp}}
        """
        try:
            blacklist_entries = self.get_all()
            details = {}
            
            for entry in blacklist_entries:
                details[entry.crypto] = {
                    "reason": entry.reason,
                    "error_code": entry.error_code,
                    "timestamp": entry.timestamp.isoformat()
                }
            
            logger.debug(f"[BLACKLIST REPO] Получены детали для {len(details)} записей")
            return details
            
        except Exception as e:
            logger.error(f"[BLACKLIST REPO] Ошибка получения деталей blacklist: {e}")
            return {}
    
    def get_blacklist_count(self) -> int:
        """
        Получить количество криптовалют в blacklist.
        
        Returns:
            int: Количество записей
        """
        return self.count()
    
    def get_by_error_code(self, error_code: int) -> List[Blacklist]:
        """
        Получить все записи с конкретным кодом ошибки.
        
        Args:
            error_code: Код ошибки
            
        Returns:
            List[Blacklist]: Список записей blacklist
        """
        try:
            entries = self.find_all(error_code=error_code)
            logger.debug(f"[BLACKLIST REPO] Найдено {len(entries)} записей с error_code={error_code}")
            return entries
        except Exception as e:
            logger.error(f"[BLACKLIST REPO] Ошибка поиска по error_code={error_code}: {e}")
            return []
    
    def bulk_add(self, blacklist_data: Dict[str, Dict]) -> int:
        """
        Массовое добавление криптовалют в blacklist (для миграции).
        
        Args:
            blacklist_data: Словарь в формате {crypto: {reason, error_code, timestamp}}
            
        Returns:
            int: Количество успешно добавленных записей
        """
        added_count = 0
        
        for crypto, data in blacklist_data.items():
            try:
                # Парсим timestamp из ISO формата
                timestamp_str = data.get('timestamp')
                if timestamp_str:
                    timestamp = datetime.fromisoformat(timestamp_str)
                else:
                    timestamp = datetime.now()
                
                success = self.add_to_blacklist(
                    crypto=crypto,
                    reason=data.get('reason', 'Unknown reason'),
                    error_code=data.get('error_code'),
                    timestamp=timestamp
                )
                
                if success:
                    added_count += 1
                    
            except Exception as e:
                logger.error(f"[BLACKLIST REPO] Ошибка добавления {crypto} при bulk_add: {e}")
                continue
        
        logger.info(f"[BLACKLIST REPO] ✅ Массовое добавление: {added_count}/{len(blacklist_data)} записей")
        return added_count
    
    @staticmethod
    def should_blacklist_error(error_code: int, critical_codes: List[int]) -> bool:
        """
        Проверить является ли код ошибки критическим для blacklist.
        
        Args:
            error_code: Код ошибки
            critical_codes: Список критических кодов из config
            
        Returns:
            bool: True если код критический
        """
        return error_code in critical_codes
