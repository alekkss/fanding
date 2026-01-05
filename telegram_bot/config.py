# -*- coding: utf-8 -*-
"""
Конфигурация Telegram бота для арбитражного бота.
"""

import os
from typing import List
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()


class TelegramConfig:
    """
    Конфигурация Telegram бота.
    
    Централизует все настройки бота для удобного управления.
    Использует переменные окружения для чувствительных данных (токен).
    """
    
    # Токен бота (из переменной окружения или значение по умолчанию)
    BOT_TOKEN: str = os.getenv(
        "TELEGRAM_BOT_TOKEN"
    )
    
    # Whitelist разрешенных chat_id (добавь свой после первого /start)
    ADMIN_CHAT_IDS: List[int] = [
        436816068
        # Например: 123456789
    ]
    
    # Основной chat_id для уведомлений (первый из whitelist или None)
    @property
    def NOTIFICATION_CHAT_ID(self) -> int | None:
        """Возвращает первый chat_id из whitelist для уведомлений."""
        return self.ADMIN_CHAT_IDS[0] if self.ADMIN_CHAT_IDS else None
    
    # Настройки уведомлений
    NOTIFICATIONS_ENABLED: bool = True
    
    # Таймаут для отправки сообщений (секунды)
    MESSAGE_TIMEOUT: int = 10
    
    # Максимум попыток отправки при ошибке
    MAX_RETRY_ATTEMPTS: int = 3
    
    # Задержка между попытками (секунды)
    RETRY_DELAY: int = 2
    
    # Формат временных меток
    DATETIME_FORMAT: str = "%Y-%m-%d %H:%M:%S"
    
    # Telegram API настройки
    PARSE_MODE: str = "Markdown"  # Markdown или HTML
    
    # Disable web page preview для ссылок
    DISABLE_WEB_PAGE_PREVIEW: bool = True


# Глобальный экземпляр конфигурации
telegram_config = TelegramConfig()


def is_admin(chat_id: int) -> bool:
    """
    Проверяет является ли пользователь администратором.
    
    Args:
        chat_id: Telegram chat_id пользователя
        
    Returns:
        bool: True если пользователь в whitelist
    """
    return chat_id in telegram_config.ADMIN_CHAT_IDS


def add_admin(chat_id: int) -> bool:
    """
    Добавляет chat_id в whitelist администраторов.
    
    Args:
        chat_id: Telegram chat_id для добавления
        
    Returns:
        bool: True если добавлен, False если уже был в списке
    """
    if chat_id in telegram_config.ADMIN_CHAT_IDS:
        return False
    
    telegram_config.ADMIN_CHAT_IDS.append(chat_id)
    return True
