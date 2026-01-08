# -*- coding: utf-8 -*-
"""
Сервис отправки уведомлений в Telegram.
Singleton с thread-safe отправкой и retry механизмом.
"""

import logging
import threading
import time
import asyncio
from typing import Dict, Any, Optional
from queue import Queue

import telegram
from telegram.error import TelegramError, TimedOut, NetworkError

from telegram_bot.config import telegram_config
from telegram_bot.formatters import MessageFormatter

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Singleton-сервис для отправки уведомлений в Telegram.
    
    Thread-safe, использует очередь для неблокирующей отправки.
    Автоматические retry при ошибках сети.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern для глобального доступа."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Инициализация сервиса."""
        if self._initialized:
            return
        
        self.config = telegram_config
        self.formatter = MessageFormatter()
        
        # Telegram Bot
        self.bot: Optional[telegram.Bot] = None
        
        # Очередь сообщений для асинхронной отправки
        self.message_queue: Queue = Queue()
        
        # Поток для обработки очереди
        self.worker_thread: Optional[threading.Thread] = None
        self.shutdown_event = threading.Event()
        
        # Инициализация бота
        self._init_bot()
        
        # Запуск worker потока
        self._start_worker()
        
        self._initialized = True
        logger.info("✅ NotificationService инициализирован")
    
    def _init_bot(self) -> None:
        """Инициализирует Telegram Bot."""
        try:
            self.bot = telegram.Bot(token=self.config.BOT_TOKEN)
            logger.info("✅ Telegram Bot инициализирован")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации Telegram Bot: {e}")
            self.bot = None
    
    def _start_worker(self) -> None:
        """Запускает worker поток для обработки очереди сообщений."""
        self.worker_thread = threading.Thread(
            target=self._process_queue,
            name="TelegramNotificationWorker",
            daemon=True
        )
        self.worker_thread.start()
        logger.info("✅ Worker поток уведомлений запущен")
    
    def _process_queue(self) -> None:
        """Обрабатывает очередь сообщений в отдельном потоке."""
        while not self.shutdown_event.is_set():
            try:
                # Ждем сообщение из очереди (timeout 1 сек)
                if not self.message_queue.empty():
                    message_data = self.message_queue.get(timeout=1)
                    
                    # Отправляем сообщение
                    self._send_message_with_retry(
                        chat_id=message_data['chat_id'],
                        text=message_data['text']
                    )
                    
                    self.message_queue.task_done()
                else:
                    time.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"❌ Ошибка в worker потоке уведомлений: {e}")
                time.sleep(1)
    
    def _send_message_with_retry(self, chat_id: int, text: str) -> bool:
        """
        Отправляет сообщение с retry механизмом.
        
        Args:
            chat_id: ID чата для отправки
            text: Текст сообщения
            
        Returns:
            bool: True если отправлено успешно
        """
        if not self.bot:
            logger.error("❌ Telegram Bot не инициализирован")
            return False
        
        for attempt in range(1, self.config.MAX_RETRY_ATTEMPTS + 1):
            try:
                # 🆕 Синхронный вызов async функции через asyncio.run()
                asyncio.run(self.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=self.config.PARSE_MODE,
                    disable_web_page_preview=self.config.DISABLE_WEB_PAGE_PREVIEW,
                    read_timeout=self.config.MESSAGE_TIMEOUT,
                    write_timeout=self.config.MESSAGE_TIMEOUT
                ))
                logger.debug(f"✅ Сообщение отправлено в chat_id={chat_id}")
                return True
                
            except (TimedOut, NetworkError) as e:
                logger.warning(
                    f"⚠️ Ошибка сети при отправке (попытка {attempt}/{self.config.MAX_RETRY_ATTEMPTS}): {e}"
                )
                if attempt < self.config.MAX_RETRY_ATTEMPTS:
                    time.sleep(self.config.RETRY_DELAY)
                    
            except TelegramError as e:
                logger.error(f"❌ Telegram API ошибка: {e}")
                return False
                
            except Exception as e:
                logger.error(f"❌ Неожиданная ошибка при отправке: {e}")
                return False
        
        logger.error(f"❌ Не удалось отправить сообщение после {self.config.MAX_RETRY_ATTEMPTS} попыток")
        return False
    
    def _enqueue_message(self, text: str, chat_id: Optional[int] = None) -> None:
        """
        Добавляет сообщение в очередь для отправки.
        
        Args:
            text: Текст сообщения
            chat_id: ID чата (если None, использует из конфига)
        """
        if not self.config.NOTIFICATIONS_ENABLED:
            logger.debug("Уведомления отключены в конфиге")
            return
        
        target_chat_id = chat_id or self.config.NOTIFICATION_CHAT_ID
        
        if not target_chat_id:
            logger.warning("⚠️ NOTIFICATION_CHAT_ID не настроен, сообщение не отправлено")
            return
        
        self.message_queue.put({
            'chat_id': target_chat_id,
            'text': text
        })
    
    # === Публичные методы для отправки уведомлений ===
    
    def notify_position_opened(self, position_data: Dict[str, Any]) -> None:
        """
        Отправляет уведомление об открытии позиции.
        
        Args:
            position_data: Данные позиции (см. MessageFormatter.format_position_opened)
        """
        try:
            message = self.formatter.format_position_opened(position_data)
            self._enqueue_message(message)
            logger.info(f"📤 Уведомление: позиция открыта {position_data.get('crypto')}")
        except Exception as e:
            logger.error(f"❌ Ошибка создания уведомления об открытии: {e}")
    
    def notify_position_closed(self, closed_data: Dict[str, Any]) -> None:
        """
        Отправляет уведомление о закрытии позиции.
        
        Args:
            closed_data: Данные закрытой позиции (см. MessageFormatter.format_position_closed)
        """
        try:
            message = self.formatter.format_position_closed(closed_data)
            self._enqueue_message(message)
            logger.info(f"📤 Уведомление: позиция закрыта {closed_data.get('crypto')}")
        except Exception as e:
            logger.error(f"❌ Ошибка создания уведомления о закрытии: {e}")
    
    def notify_critical_error(self, error_data: Dict[str, Any]) -> None:
        """
        Отправляет уведомление о критической ошибке.
        
        Args:
            error_data: Данные ошибки (см. MessageFormatter.format_critical_error)
        """
        try:
            message = self.formatter.format_critical_error(error_data)
            self._enqueue_message(message)
            logger.error(f"📤 КРИТИЧЕСКОЕ уведомление: {error_data.get('message')}")
        except Exception as e:
            logger.error(f"❌ Ошибка создания критического уведомления: {e}")
    
    def notify_blacklist_added(self, blacklist_data: Dict[str, Any]) -> None:
        """
        Отправляет уведомление о добавлении в blacklist.
        
        Args:
            blacklist_data: Данные blacklist (см. MessageFormatter.format_blacklist_added)
        """
        try:
            message = self.formatter.format_blacklist_added(blacklist_data)
            self._enqueue_message(message)
            logger.info(f"📤 Уведомление: добавлен в blacklist {blacklist_data.get('crypto')}")
        except Exception as e:
            logger.error(f"❌ Ошибка создания уведомления о blacklist: {e}")
    
    def shutdown(self) -> None:
        """Корректная остановка сервиса."""
        logger.info("🛑 Остановка NotificationService...")
        self.shutdown_event.set()
        
        # Ждем опустошения очереди
        self.message_queue.join()
        
        # Ждем завершения worker потока
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5)
        
        logger.info("✅ NotificationService остановлен")


# Глобальный экземпляр
notification_service = NotificationService()
