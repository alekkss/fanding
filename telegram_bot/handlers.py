# -*- coding: utf-8 -*-

"""
Обработчики команд Telegram бота.
Обрабатывает базовые команды: /start, /status, /positions, /stats, /blacklist.
"""

import logging
from typing import Optional
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from telegram_bot.config import telegram_config, is_admin, add_admin
from telegram_bot.formatters import MessageFormatter
from database.repositories.position_repository import PositionRepository
from database.repositories.history_repository import HistoryRepository
from database.repositories.blacklist_repository import BlacklistRepository

logger = logging.getLogger(__name__)


class CommandHandlers:
    """
    Обработчики команд Telegram бота.
    
    Single Responsibility: только обработка команд пользователя.
    Dependency Injection: получает репозитории через конструктор.
    """

    def __init__(
        self,
        position_repo: Optional[PositionRepository] = None,
        history_repo: Optional[HistoryRepository] = None,
        blacklist_repo: Optional[BlacklistRepository] = None
    ):
        """
        Инициализация обработчиков.
        
        Args:
            position_repo: Репозиторий позиций
            history_repo: Репозиторий истории
            blacklist_repo: Репозиторий blacklist
        """
        self.position_repo = position_repo or PositionRepository()
        self.history_repo = history_repo or HistoryRepository()
        self.blacklist_repo = blacklist_repo or BlacklistRepository()
        self.formatter = MessageFormatter()
        logger.info("✅ CommandHandlers инициализирован")

    def _check_admin(self, update: Update) -> bool:
        """
        Проверяет права администратора.
        
        Args:
            update: Telegram Update объект
            
        Returns:
            bool: True если пользователь админ
        """
        user = update.effective_user
        chat_id = update.effective_chat.id

        if not is_admin(chat_id):
            logger.warning(f"⚠️ Неавторизованный доступ от {user.username} (chat_id={chat_id})")
            return False

        return True

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Обработчик команды /start.
        Показывает приветствие и chat_id для первичной настройки.
        """
        user = update.effective_user
        chat_id = update.effective_chat.id
        logger.info(f"📱 /start от {user.username} (chat_id={chat_id})")

        # Проверка прав
        is_authorized = is_admin(chat_id)

        if is_authorized:
            message = f"""👋 Привет, *{user.first_name}*!

🤖 Я бот для мониторинга арбитражного бота Bybit.

*Доступные команды:*
📊 */status* - текущее состояние системы
📍 */positions* - список открытых позиций
📈 */stats* - статистика торговли
🚫 */blacklist* - список заблокированных пар

✅ Ты авторизован как администратор.
"""
        else:
            message = f"""👋 Привет, *{user.first_name}*!

🤖 Я бот для мониторинга арбитражного бота Bybit.

⚠️ Ты не авторизован.

*Твой chat_id:* `{chat_id}`

Добавь этот chat_id в `ADMIN_CHAT_IDS` в файле `telegram_bot/config.py` и перезапусти бота.
"""

        await update.message.reply_text(message, parse_mode='Markdown')

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Обработчик команды /status.
        Показывает текущее состояние системы: открытые позиции, blacklist.
        """
        chat_id = update.effective_chat.id
        logger.info(f"📱 /status от chat_id={chat_id}")

        # Проверка прав
        if not self._check_admin(update):
            await update.message.reply_text(
                "⛔ Доступ запрещен. Используй /start для получения chat_id.",
                parse_mode='Markdown'
            )
            return

        try:
            # Получение данных из репозиториев
            open_positions = self.position_repo.get_all_open()
            blacklist_count = len(self.blacklist_repo.get_all_blacklisted())

            # Преобразование позиций в список словарей
            positions_list = [pos.to_dict() for pos in open_positions]

            # Формирование статуса
            status_data = {
                'open_positions': positions_list,
                'blacklist_count': blacklist_count,
                'uptime': 'N/A'  # TODO: можно добавить uptime если нужно
            }

            message = self.formatter.format_status(status_data)
            await update.message.reply_text(message, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"❌ Ошибка получения статуса: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ Ошибка получения статуса. Проверь логи.",
                parse_mode='Markdown'
            )

    async def positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Обработчик команды /positions.
        Показывает список открытых позиций с деталями.
        """
        chat_id = update.effective_chat.id
        logger.info(f"📱 /positions от chat_id={chat_id}")

        # Проверка прав
        if not self._check_admin(update):
            await update.message.reply_text(
                "⛔ Доступ запрещен. Используй /start для получения chat_id.",
                parse_mode='Markdown'
            )
            return

        try:
            # Получение открытых позиций
            open_positions = self.position_repo.get_all_open()

            # Преобразование в список словарей
            positions_list = [pos.to_dict() for pos in open_positions]

            message = self.formatter.format_positions_list(positions_list)
            await update.message.reply_text(message, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"❌ Ошибка получения позиций: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ Ошибка получения позиций. Проверь логи.",
                parse_mode='Markdown'
            )

    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Обработчик команды /stats.
        Показывает статистику торговли: total PnL, win rate, avg PnL.
        """
        chat_id = update.effective_chat.id
        logger.info(f"📱 /stats от chat_id={chat_id}")

        # Проверка прав
        if not self._check_admin(update):
            await update.message.reply_text(
                "⛔ Доступ запрещен. Используй /start для получения chat_id.",
                parse_mode='Markdown'
            )
            return

        try:
            # Получение статистики из репозитория
            stats = self.history_repo.get_statistics()

            message = self.formatter.format_statistics(stats)
            await update.message.reply_text(message, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ Ошибка получения статистики. Проверь логи.",
                parse_mode='Markdown'
            )

    async def blacklist(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Обработчик команды /blacklist.
        Показывает список всех заблокированных криптовалют с причинами и кодами ошибок.
        """
        chat_id = update.effective_chat.id
        logger.info(f"📱 /blacklist от chat_id={chat_id}")

        # Проверка прав
        if not self._check_admin(update):
            await update.message.reply_text(
                "⛔ Доступ запрещен. Используй /start для получения chat_id.",
                parse_mode='Markdown'
            )
            return

        try:
            # Получение всех записей blacklist с деталями
            blacklist_details = self.blacklist_repo.get_all()

            if not blacklist_details:
                message = "🚫 *BLACKLIST*\n\n✅ Нет заблокированных пар"
                await update.message.reply_text(message, parse_mode='Markdown')
                return

            # Формирование сообщения
            message_lines = [f"🚫 *BLACKLIST* ({len(blacklist_details)} пар)\n"]

            for idx, entry in enumerate(blacklist_details, 1):
                crypto = entry.crypto
                reason = entry.reason or "Не указана"
                error_code = entry.error_code
                timestamp = entry.timestamp.strftime("%d.%m %H:%M") if entry.timestamp else "N/A"

                # Форматирование записи
                entry_text = f"{idx}. *{crypto}*\n"
                entry_text += f"├─ 📝 {reason}\n"
                
                if error_code:
                    entry_text += f"├─ 🔢 Код ошибки: `{error_code}`\n"
                
                entry_text += f"└─ 📅 {timestamp}\n"

                message_lines.append(entry_text)

            message = "\n".join(message_lines)

            # Telegram ограничивает длину сообщения 4096 символов
            if len(message) > 4096:
                # Разбиваем на несколько сообщений
                parts = []
                current_part = f"🚫 *BLACKLIST* ({len(blacklist_details)} пар)\n\n"
                
                for idx, entry in enumerate(blacklist_details, 1):
                    crypto = entry.crypto
                    reason = entry.reason or "Не указана"
                    error_code = entry.error_code
                    timestamp = entry.timestamp.strftime("%d.%m %H:%M") if entry.timestamp else "N/A"

                    entry_text = f"{idx}. *{crypto}*\n"
                    entry_text += f"├─ 📝 {reason}\n"
                    
                    if error_code:
                        entry_text += f"├─ 🔢 Код: `{error_code}`\n"
                    
                    entry_text += f"└─ 📅 {timestamp}\n\n"

                    # Проверка длины
                    if len(current_part) + len(entry_text) > 4000:
                        parts.append(current_part)
                        current_part = entry_text
                    else:
                        current_part += entry_text

                # Добавляем последнюю часть
                if current_part:
                    parts.append(current_part)

                # Отправляем по частям
                for part in parts:
                    await update.message.reply_text(part, parse_mode='Markdown')
            else:
                await update.message.reply_text(message, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"❌ Ошибка получения blacklist: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ Ошибка получения blacklist. Проверь логи.",
                parse_mode='Markdown'
            )

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Глобальный обработчик ошибок.
        Логирует все необработанные ошибки в handlers.
        """
        logger.error(f"❌ Ошибка в обработчике команды: {context.error}", exc_info=context.error)

        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Произошла ошибка при обработке команды. Проверь логи.",
                parse_mode='Markdown'
            )
