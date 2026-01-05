# -*- coding: utf-8 -*-
"""
Интеграция Telegram бота с арбитражной системой.
Связывает бота с Orchestrator через уведомления.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

from telegram_bot.bot import TelegramBot
from telegram_bot.notifications import notification_service
from database.repositories.position_repository import PositionRepository
from database.repositories.history_repository import HistoryRepository
from database.repositories.blacklist_repository import BlacklistRepository

logger = logging.getLogger(__name__)


class TelegramIntegration:
    """
    Интеграция Telegram бота с арбитражной системой.
    
    Single Responsibility: связывает бота с системой через уведомления.
    Facade Pattern: предоставляет простой интерфейс для Orchestrator.
    """
    
    def __init__(
        self,
        position_repo: Optional[PositionRepository] = None,
        history_repo: Optional[HistoryRepository] = None,
        blacklist_repo: Optional[BlacklistRepository] = None
    ):
        """
        Инициализация интеграции.
        
        Args:
            position_repo: Репозиторий позиций
            history_repo: Репозиторий истории
            blacklist_repo: Репозиторий blacklist
        """
        # Репозитории (передаем в бота)
        self.position_repo = position_repo or PositionRepository()
        self.history_repo = history_repo or HistoryRepository()
        self.blacklist_repo = blacklist_repo or BlacklistRepository()
        
        # Telegram Bot
        self.bot = TelegramBot(
            position_repo=self.position_repo,
            history_repo=self.history_repo,
            blacklist_repo=self.blacklist_repo
        )
        
        # NotificationService (глобальный singleton)
        self.notification_service = notification_service
        
        logger.info("✅ TelegramIntegration инициализирована")
    
    def start(self) -> bool:
        """
        Запускает Telegram бота.
        
        Returns:
            bool: True если запущен успешно
        """
        success = self.bot.start()
        if success:
            logger.info("✅ Telegram интеграция активна")
        else:
            logger.error("❌ Не удалось запустить Telegram интеграцию")
        return success
    
    def stop(self) -> None:
        """
        Останавливает Telegram бота.
        """
        self.bot.stop()
        self.notification_service.shutdown()
        logger.info("✅ Telegram интеграция остановлена")
    
    def is_running(self) -> bool:
        """
        Проверяет работает ли бот.
        
        Returns:
            bool: True если бот работает
        """
        return self.bot.is_running()
    
    # === Методы для отправки уведомлений ===
    
    def notify_position_opened(
        self,
        crypto: str,
        spot_entry_price: float,
        futures_entry_price: float,
        spot_qty: float,
        entry_spread_pct: float,
        funding_rate: float = 0.0
    ) -> None:
        """
        Уведомление об открытии позиции.
        
        Args:
            crypto: Символ криптовалюты
            spot_entry_price: Цена входа по споту
            futures_entry_price: Цена входа по фьючерсу
            spot_qty: Количество монет
            entry_spread_pct: Спред при входе (%)
            funding_rate: Funding rate (%)
        """
        try:
            position_data = {
                'crypto': crypto,
                'spot_entry_price': spot_entry_price,
                'futures_entry_price': futures_entry_price,
                'spot_qty': spot_qty,
                'entry_spread_pct': entry_spread_pct,
                'funding_rate': funding_rate,
                'entry_timestamp': datetime.now().isoformat()
            }
            
            self.notification_service.notify_position_opened(position_data)
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления об открытии: {e}", exc_info=True)
    
    def notify_position_closed(
        self,
        crypto: str,
        entry_time: str,
        close_time: str,
        spot_pnl: float,
        futures_pnl: float,
        funding: float,
        commission: float,
        net_pnl: float
    ) -> None:
        """
        Уведомление о закрытии позиции.
        
        Args:
            crypto: Символ криптовалюты
            entry_time: Время открытия (ISO format)
            close_time: Время закрытия (ISO format)
            spot_pnl: PnL по споту
            futures_pnl: PnL по фьючерсу
            funding: Накопленный фандинг
            commission: Комиссии
            net_pnl: Чистая прибыль
        """
        try:
            closed_data = {
                'crypto': crypto,
                'entry_time': entry_time,
                'close_time': close_time,
                'pnl': {
                    'spot_pnl': spot_pnl,
                    'futures_pnl': futures_pnl,
                    'funding': funding,
                    'commission': commission,
                    'net_pnl': net_pnl
                }
            }
            
            self.notification_service.notify_position_closed(closed_data)
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления о закрытии: {e}", exc_info=True)
    
    def notify_critical_error(
        self,
        error_type: str,
        message: str,
        crypto: Optional[str] = None,
        qty: Optional[float] = None
    ) -> None:
        """
        Уведомление о критической ошибке.
        
        Args:
            error_type: Тип ошибки ('futures_opened_spot_failed' или 'system_error')
            message: Описание ошибки
            crypto: Символ криптовалюты (если применимо)
            qty: Количество (если применимо)
        """
        try:
            error_data = {
                'type': error_type,
                'message': message
            }
            
            if crypto:
                error_data['crypto'] = crypto
            if qty is not None:
                error_data['qty'] = qty
            
            self.notification_service.notify_critical_error(error_data)
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки критического уведомления: {e}", exc_info=True)
    
    def notify_blacklist_added(
        self,
        crypto: str,
        reason: str,
        error_code: Optional[int] = None
    ) -> None:
        """
        Уведомление о добавлении в blacklist.
        
        Args:
            crypto: Символ криптовалюты
            reason: Причина добавления
            error_code: Код ошибки (если есть)
        """
        try:
            blacklist_data = {
                'crypto': crypto,
                'reason': reason
            }
            
            if error_code:
                blacklist_data['error_code'] = error_code
            
            self.notification_service.notify_blacklist_added(blacklist_data)
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления о blacklist: {e}", exc_info=True)


# Глобальный экземпляр (создается в Orchestrator)
telegram_integration: Optional[TelegramIntegration] = None


def initialize_telegram_integration(
    position_repo: Optional[PositionRepository] = None,
    history_repo: Optional[HistoryRepository] = None,
    blacklist_repo: Optional[BlacklistRepository] = None
) -> TelegramIntegration:
    """
    Инициализирует глобальный экземпляр Telegram интеграции.
    
    Args:
        position_repo: Репозиторий позиций
        history_repo: Репозиторий истории
        blacklist_repo: Репозиторий blacklist
        
    Returns:
        TelegramIntegration: Инициализированный экземпляр
    """
    global telegram_integration
    
    telegram_integration = TelegramIntegration(
        position_repo=position_repo,
        history_repo=history_repo,
        blacklist_repo=blacklist_repo
    )
    
    return telegram_integration


def get_telegram_integration() -> Optional[TelegramIntegration]:
    """
    Получает глобальный экземпляр Telegram интеграции.
    
    Returns:
        TelegramIntegration или None если не инициализирован
    """
    return telegram_integration
