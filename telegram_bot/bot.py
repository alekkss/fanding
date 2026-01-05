# -*- coding: utf-8 -*-
"""
Главный класс Telegram бота.
Инициализация, регистрация handlers, запуск polling.
"""

import logging
import threading
from typing import Optional

from telegram.ext import Application, CommandHandler

from telegram_bot.config import telegram_config
from telegram_bot.handlers import CommandHandlers
from database.repositories.position_repository import PositionRepository
from database.repositories.history_repository import HistoryRepository
from database.repositories.blacklist_repository import BlacklistRepository

logger = logging.getLogger(__name__)


class TelegramBot:
    """
    Главный класс Telegram бота для арбитражной системы.
    
    Single Responsibility: управление жизненным циклом Telegram бота.
    Dependency Injection: получает репозитории извне для связи с системой.
    """
    
    def __init__(
        self,
        position_repo: Optional[PositionRepository] = None,
        history_repo: Optional[HistoryRepository] = None,
        blacklist_repo: Optional[BlacklistRepository] = None
    ):
        """
        Инициализация бота.
        
        Args:
            position_repo: Репозиторий позиций
            history_repo: Репозиторий истории
            blacklist_repo: Репозиторий blacklist
        """
        self.config = telegram_config
        
        # Репозитории (DI)
        self.position_repo = position_repo or PositionRepository()
        self.history_repo = history_repo or HistoryRepository()
        self.blacklist_repo = blacklist_repo or BlacklistRepository()
        
        # Обработчики команд
        self.handlers = CommandHandlers(
            position_repo=self.position_repo,
            history_repo=self.history_repo,
            blacklist_repo=self.blacklist_repo
        )
        
        # Telegram Application
        self.application: Optional[Application] = None
        
        # Поток для запуска бота
        self.bot_thread: Optional[threading.Thread] = None
        self.running = False
        
        logger.info("✅ TelegramBot инициализирован")
    
    def _build_application(self) -> Application:
        """
        Создает и настраивает Telegram Application.
        
        Returns:
            Application: Настроенный Telegram Application
        """
        # Создание Application
        application = (
            Application.builder()
            .token(self.config.BOT_TOKEN)
            .read_timeout(self.config.MESSAGE_TIMEOUT)
            .write_timeout(self.config.MESSAGE_TIMEOUT)
            .build()
        )
        
        # Регистрация обработчиков команд
        application.add_handler(CommandHandler("start", self.handlers.start))
        application.add_handler(CommandHandler("status", self.handlers.status))
        application.add_handler(CommandHandler("positions", self.handlers.positions))
        application.add_handler(CommandHandler("stats", self.handlers.stats))
        
        # Регистрация обработчика ошибок
        application.add_error_handler(self.handlers.error_handler)
        
        logger.info("✅ Handlers зарегистрированы")
        
        return application
    
    def _run_polling(self) -> None:
        """
        Запускает polling в текущем потоке.
        
        Блокирующий вызов - используется в отдельном потоке.
        """
        try:
            logger.info("🚀 Запуск Telegram Bot polling...")
            
            # Запуск polling (блокирующий вызов)
            self.application.run_polling(
                allowed_updates=["message", "callback_query"],
                drop_pending_updates=True
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка в Telegram Bot polling: {e}", exc_info=True)
        finally:
            self.running = False
            logger.info("🛑 Telegram Bot polling остановлен")
    
    def start(self) -> bool:
        """
        Запускает Telegram бота в отдельном потоке.
        
        Returns:
            bool: True если запущен успешно
        """
        if self.running:
            logger.warning("⚠️ Telegram Bot уже запущен")
            return False
        
        try:
            # Создание Application
            self.application = self._build_application()
            
            # Запуск в отдельном потоке
            self.bot_thread = threading.Thread(
                target=self._run_polling,
                name="TelegramBotThread",
                daemon=True
            )
            
            self.running = True
            self.bot_thread.start()
            
            logger.info("✅ Telegram Bot запущен в отдельном потоке")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка запуска Telegram Bot: {e}", exc_info=True)
            self.running = False
            return False
    
    def stop(self) -> None:
        """
        Останавливает Telegram бота.
        
        Корректное завершение с ожиданием завершения потока.
        """
        if not self.running:
            logger.warning("⚠️ Telegram Bot уже остановлен")
            return
        
        try:
            logger.info("🛑 Остановка Telegram Bot...")
            
            # Остановка Application
            if self.application:
                self.application.stop()
            
            self.running = False
            
            # Ожидание завершения потока
            if self.bot_thread and self.bot_thread.is_alive():
                self.bot_thread.join(timeout=5)
            
            logger.info("✅ Telegram Bot остановлен")
            
        except Exception as e:
            logger.error(f"❌ Ошибка остановки Telegram Bot: {e}", exc_info=True)
    
    def is_running(self) -> bool:
        """
        Проверяет запущен ли бот.
        
        Returns:
            bool: True если бот работает
        """
        return self.running and self.bot_thread and self.bot_thread.is_alive()
