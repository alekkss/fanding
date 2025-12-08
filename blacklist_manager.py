# -*- coding: utf-8 -*-

"""Управление списком исключенных криптовалют"""

import os
import json
import logging
import threading
from datetime import datetime
from typing import Set, Optional

from config import BLACKLIST_FILE, CRITICAL_ERROR_CODES

logger = logging.getLogger(__name__)

class BlacklistManager:
    """Менеджер для управления списком запрещенных криптовалют"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern для глобального доступа"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.blacklist_file = BLACKLIST_FILE
        self.blacklist: Set[str] = set()
        self.blacklist_details = {}  # {crypto: {reason, timestamp, error_code}}
        self.lock = threading.RLock()
        self._load_blacklist()
        self._initialized = True
    
    def _load_blacklist(self) -> None:
        """Загружает blacklist из файла"""
        try:
            if os.path.exists(self.blacklist_file):
                with open(self.blacklist_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.blacklist_details = data
                    self.blacklist = set(data.keys())
                    logger.info(f"🚫 Загружен blacklist: {len(self.blacklist)} криптовалют")
                    if self.blacklist:
                        logger.info(f"   Список: {', '.join(sorted(self.blacklist))}")
        except Exception as e:
            logger.error(f"Ошибка загрузки blacklist: {e}")
    
    def _save_blacklist(self) -> None:
        """Сохраняет blacklist в файл"""
        try:
            with open(self.blacklist_file, 'w', encoding='utf-8') as f:
                json.dump(self.blacklist_details, f, indent=2, ensure_ascii=False)
            logger.info(f"💾 Blacklist сохранен: {len(self.blacklist)} криптовалют")
        except Exception as e:
            logger.error(f"Ошибка сохранения blacklist: {e}")
    
    def add_to_blacklist(self, crypto: str, reason: str, error_code: Optional[int] = None) -> bool:
        """
        Добавляет криптовалюту в blacklist
        
        Args:
            crypto: символ криптовалюты
            reason: причина добавления
            error_code: код ошибки (опционально)
        
        Returns:
            bool: True если добавлено, False если уже в списке
        """
        with self.lock:
            if crypto in self.blacklist:
                logger.warning(f"🚫 [{crypto}] Уже в blacklist")
                return False
            
            self.blacklist.add(crypto)
            self.blacklist_details[crypto] = {
                "reason": reason,
                "error_code": error_code,
                "timestamp": datetime.now().isoformat(),
            }
            
            logger.warning(f"🚫 [{crypto}] ДОБАВЛЕН В BLACKLIST")
            logger.warning(f"   └─ Причина: {reason}")
            if error_code:
                logger.warning(f"   └─ Код ошибки: {error_code}")
            
            self._save_blacklist()
            return True
    
    def is_blacklisted(self, crypto: str) -> bool:
        """Проверяет находится ли криптовалюта в blacklist"""
        with self.lock:
            return crypto in self.blacklist
    
    def remove_from_blacklist(self, crypto: str) -> bool:
        """Удаляет криптовалюту из blacklist (для ручного управления)"""
        with self.lock:
            if crypto not in self.blacklist:
                return False
            
            self.blacklist.discard(crypto)
            if crypto in self.blacklist_details:
                del self.blacklist_details[crypto]
            
            logger.info(f"✅ [{crypto}] Удален из blacklist")
            self._save_blacklist()
            return True
    
    def get_blacklist(self) -> Set[str]:
        """Возвращает копию списка blacklist"""
        with self.lock:
            return self.blacklist.copy()
    
    def get_blacklist_details(self, crypto: str) -> Optional[dict]:
        """Возвращает детали о причине добавления в blacklist"""
        with self.lock:
            return self.blacklist_details.get(crypto)
    
    @staticmethod
    def should_blacklist_error(error_code: int) -> bool:
        """Проверяет является ли код ошибки критическим для blacklist"""
        return error_code in CRITICAL_ERROR_CODES


# Глобальный экземпляр
blacklist_manager = BlacklistManager()
