# -*- coding: utf-8 -*-

"""Управление списком исключенных криптовалют через базу данных"""

import logging
import threading
from datetime import datetime
from typing import Set, Optional

from database.repositories.blacklist_repository import BlacklistRepository
from config import CRITICAL_ERROR_CODES

logger = logging.getLogger(__name__)


class BlacklistManager:
    """
    Менеджер для управления списком запрещенных криптовалют.
    
    Рефакторенная версия с использованием Repository Pattern.
    Данные хранятся в БД, но кешируются в памяти для быстрого доступа.
    Сохранен Singleton pattern для обратной совместимости.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, blacklist_repo: Optional[BlacklistRepository] = None):
        """
        Singleton pattern для глобального доступа.
        
        Args:
            blacklist_repo: Репозиторий для работы с blacklist (опционально)
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, blacklist_repo: Optional[BlacklistRepository] = None):
        """
        Args:
            blacklist_repo: Репозиторий для работы с blacklist (опционально)
        """
        if self._initialized:
            return
        
        # Dependency Injection: позволяет подменить репозиторий для тестов
        self.blacklist_repo = blacklist_repo or BlacklistRepository()
        
        # Кеш в памяти для быстрого доступа
        self.blacklist: Set[str] = set()
        self.blacklist_details = {}  # {crypto: {reason, timestamp, error_code}}
        
        # RLock для thread-safety
        self.lock = threading.RLock()
        
        # Загружаем данные из БД в кеш
        self._load_blacklist()
        
        self._initialized = True
    
    def _load_blacklist(self) -> None:
        """Загружает blacklist из БД в кеш памяти."""
        try:
            # Получаем все записи из БД
            self.blacklist = self.blacklist_repo.get_all_blacklisted()
            self.blacklist_details = self.blacklist_repo.get_all_details()
            
            logger.info(f"🚫 Загружен blacklist из БД: {len(self.blacklist)} криптовалют")
            if self.blacklist:
                logger.info(f"   Список: {', '.join(sorted(self.blacklist))}")
                
        except Exception as e:
            logger.error(f"Ошибка загрузки blacklist из БД: {e}")
    
    def _sync_cache_from_db(self) -> None:
        """Синхронизирует кеш с БД (для случаев изменений извне)."""
        try:
            self.blacklist = self.blacklist_repo.get_all_blacklisted()
            self.blacklist_details = self.blacklist_repo.get_all_details()
        except Exception as e:
            logger.error(f"Ошибка синхронизации кеша: {e}")
    
    def add_to_blacklist(
        self,
        crypto: str,
        reason: str,
        error_code: Optional[int] = None
    ) -> bool:
        """
        Добавляет криптовалюту в blacklist.
        
        Args:
            crypto: Символ криптовалюты
            reason: Причина добавления
            error_code: Код ошибки (опционально)
            
        Returns:
            bool: True если добавлено, False если уже в списке
        """
        with self.lock:
            # Проверяем кеш
            if crypto in self.blacklist:
                logger.warning(f"🚫 [{crypto}] Уже в blacklist")
                return False
            
            # Добавляем в БД через репозиторий
            success = self.blacklist_repo.add_to_blacklist(
                crypto=crypto,
                reason=reason,
                error_code=error_code
            )
            
            if success:
                # Обновляем кеш
                self.blacklist.add(crypto)
                self.blacklist_details[crypto] = {
                    "reason": reason,
                    "error_code": error_code,
                    "timestamp": datetime.now().isoformat()
                }
                
                logger.warning(f"🚫 [{crypto}] ДОБАВЛЕН В BLACKLIST")
                logger.warning(f"   └─ Причина: {reason}")
                if error_code:
                    logger.warning(f"   └─ Код ошибки: {error_code}")
            
            return success
    
    def is_blacklisted(self, crypto: str) -> bool:
        """
        Проверяет находится ли криптовалюта в blacklist.
        
        Args:
            crypto: Символ криптовалюты
            
        Returns:
            bool: True если в blacklist
        """
        with self.lock:
            # Быстрая проверка через кеш
            return crypto in self.blacklist
    
    def remove_from_blacklist(self, crypto: str) -> bool:
        """
        Удаляет криптовалюту из blacklist (для ручного управления).
        
        Args:
            crypto: Символ криптовалюты
            
        Returns:
            bool: True если удалено успешно
        """
        with self.lock:
            # Проверяем кеш
            if crypto not in self.blacklist:
                logger.warning(f"[{crypto}] Не найден в blacklist для удаления")
                return False
            
            # Удаляем из БД
            success = self.blacklist_repo.remove_from_blacklist(crypto)
            
            if success:
                # Обновляем кеш
                self.blacklist.discard(crypto)
                if crypto in self.blacklist_details:
                    del self.blacklist_details[crypto]
                
                logger.info(f"✅ [{crypto}] Удален из blacklist")
            
            return success
    
    def get_blacklist(self) -> Set[str]:
        """
        Возвращает копию списка blacklist.
        
        Returns:
            Set[str]: Множество символов криптовалют в blacklist
        """
        with self.lock:
            return self.blacklist.copy()
    
    def get_blacklist_details(self, crypto: str) -> Optional[dict]:
        """
        Возвращает детали о причине добавления в blacklist.
        
        Args:
            crypto: Символ криптовалюты
            
        Returns:
            dict | None: Детали или None если не найдено
        """
        with self.lock:
            # Сначала проверяем кеш
            if crypto in self.blacklist_details:
                return self.blacklist_details[crypto]
            
            # Если нет в кеше, запрашиваем из БД
            return self.blacklist_repo.get_blacklist_details(crypto)
    
    def refresh_cache(self) -> None:
        """
        Принудительно обновляет кеш из БД.
        Полезно если данные были изменены извне (другим процессом).
        """
        with self.lock:
            logger.info("🔄 Обновление кеша blacklist из БД...")
            self._sync_cache_from_db()
            logger.info(f"✅ Кеш обновлен: {len(self.blacklist)} записей")
    
    def get_blacklist_count(self) -> int:
        """
        Возвращает количество криптовалют в blacklist.
        
        Returns:
            int: Количество записей
        """
        with self.lock:
            return len(self.blacklist)
    
    @staticmethod
    def should_blacklist_error(error_code: int) -> bool:
        """
        Проверяет является ли код ошибки критическим для blacklist.
        
        Args:
            error_code: Код ошибки API
            
        Returns:
            bool: True если код критический
        """
        return error_code in CRITICAL_ERROR_CODES


# Глобальный экземпляр (для обратной совместимости)
blacklist_manager = BlacklistManager()
