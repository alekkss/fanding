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
📜 */history [N]* - последние N сделок (по умолчанию 10)
🚫 */blacklist* - список заблокированных пар
➕ */blacklist add [CRYPTO] [причина]* - добавить в blacklist
➖ */blacklist remove [CRYPTO]* - удалить из blacklist

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
    
    async def history(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Обработчик команды /history [N].
        Показывает последние N закрытых сделок с детальной информацией по PnL.
        
        По умолчанию показывает 10 последних сделок.
        """
        chat_id = update.effective_chat.id
        logger.info(f"📱 /history от chat_id={chat_id}")

        # Проверка прав
        if not self._check_admin(update):
            await update.message.reply_text(
                "⛔ Доступ запрещен. Используй /start для получения chat_id.",
                parse_mode='Markdown'
            )
            return

        try:
            # Парсинг количества записей из аргументов
            limit = 10  # По умолчанию 10
            args = context.args
            
            if args:
                try:
                    limit = int(args[0])
                    # Ограничение: от 1 до 50 записей
                    limit = max(1, min(limit, 50))
                except ValueError:
                    await update.message.reply_text(
                        "❌ Неправильный формат.\n\n"
                        "Используй: `/history [N]`\n"
                        "Пример: `/history 15`",
                        parse_mode='Markdown'
                    )
                    return

            # Получение последних закрытых позиций
            closed_positions = self.history_repo.get_recent_history(limit=limit)

            if not closed_positions:
                message = "📊 *ИСТОРИЯ СДЕЛОК*\n\n✅ Нет закрытых позиций"
                await update.message.reply_text(message, parse_mode='Markdown')
                return

            # Формирование сообщения
            message_lines = [f"📊 *ИСТОРИЯ ПОСЛЕДНИХ {len(closed_positions)} СДЕЛОК*\n"]

            total_net_pnl = 0.0

            for idx, pos in enumerate(closed_positions, 1):
                # Рассчитываем общий PnL
                total_net_pnl += pos.net_pnl

                # Эмодзи в зависимости от результата
                pnl_emoji = "✅" if pos.net_pnl > 0 else "❌"
                
                # Форматирование времени
                close_time = pos.close_timestamp.strftime("%d.%m %H:%M")
                
                # Длительность позиции
                duration = pos.close_timestamp - pos.entry_timestamp
                hours = int(duration.total_seconds() / 3600)
                minutes = int((duration.total_seconds() % 3600) / 60)
                duration_str = f"{hours}ч {minutes}м" if hours > 0 else f"{minutes}м"

                # Форматирование сделки
                entry_text = f"{idx}. {pnl_emoji} *{pos.crypto}*\n"
                entry_text += f"├─ ⏰ {close_time} ({duration_str})\n"
                entry_text += f"├─ 📈 Спот PnL: `{pos.spot_pnl:+.4f}` USDT\n" if pos.spot_pnl else ""
                entry_text += f"├─ 📉 Фьючерс PnL: `{pos.futures_pnl:+.4f}` USDT\n" if pos.futures_pnl else ""
                entry_text += f"├─ 💰 Funding: `{pos.funding_pnl:+.4f}` USDT\n"
                entry_text += f"├─ 💸 Комиссия: `-{abs(pos.commission):.4f}` USDT\n"
                entry_text += f"└─ 💵 *Net PnL: `{pos.net_pnl:+.4f}` USDT*\n"

                message_lines.append(entry_text)

            # Итоговая статистика
            avg_pnl = total_net_pnl / len(closed_positions)
            win_count = sum(1 for pos in closed_positions if pos.net_pnl > 0)
            win_rate = (win_count / len(closed_positions)) * 100

            summary = f"\n📊 *ИТОГО:*\n"
            summary += f"├─ Общий PnL: `{total_net_pnl:+.4f}` USDT\n"
            summary += f"├─ Средний PnL: `{avg_pnl:+.4f}` USDT\n"
            summary += f"└─ Win Rate: `{win_rate:.1f}%` ({win_count}/{len(closed_positions)})"

            message_lines.append(summary)

            message = "\n".join(message_lines)

            # Telegram ограничивает длину сообщения 4096 символов
            if len(message) > 4096:
                # Разбиваем на части
                parts = []
                current_part = f"📊 *ИСТОРИЯ ПОСЛЕДНИХ {len(closed_positions)} СДЕЛОК*\n\n"
                
                for idx, pos in enumerate(closed_positions, 1):
                    pnl_emoji = "✅" if pos.net_pnl > 0 else "❌"
                    close_time = pos.close_timestamp.strftime("%d.%m %H:%M")
                    duration = pos.close_timestamp - pos.entry_timestamp
                    hours = int(duration.total_seconds() / 3600)
                    minutes = int((duration.total_seconds() % 3600) / 60)
                    duration_str = f"{hours}ч {minutes}м" if hours > 0 else f"{minutes}м"

                    entry_text = f"{idx}. {pnl_emoji} *{pos.crypto}*\n"
                    entry_text += f"├─ ⏰ {close_time} ({duration_str})\n"
                    entry_text += f"├─ 📈 Спот: `{pos.spot_pnl:+.4f}` USDT\n" if pos.spot_pnl else ""
                    entry_text += f"├─ 📉 Фьючерс: `{pos.futures_pnl:+.4f}` USDT\n" if pos.futures_pnl else ""
                    entry_text += f"├─ 💰 FR: `{pos.funding_pnl:+.4f}` USDT\n"
                    entry_text += f"├─ 💸 Fee: `-{abs(pos.commission):.4f}` USDT\n"
                    entry_text += f"└─ 💵 Net: `{pos.net_pnl:+.4f}` USDT\n\n"

                    if len(current_part) + len(entry_text) > 3500:
                        parts.append(current_part)
                        current_part = entry_text
                    else:
                        current_part += entry_text

                # Добавляем последнюю часть с итогами
                if current_part:
                    current_part += summary
                    parts.append(current_part)

                # Отправляем по частям
                for part in parts:
                    await update.message.reply_text(part, parse_mode='Markdown')
            else:
                await update.message.reply_text(message, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"❌ Ошибка получения истории: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ Ошибка получения истории. Проверь логи.",
                parse_mode='Markdown'
            )

    async def blacklist(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Обработчик команды /blacklist.
        
        Поддерживает подкоманды:
        - /blacklist - показать список заблокированных пар
        - /blacklist add [CRYPTO] [причина] - добавить пару в blacklist
        - /blacklist remove [CRYPTO] - удалить пару из blacklist
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
            # Проверяем наличие аргументов (подкоманд)
            args = context.args  # Список аргументов после команды

            # Подкоманда: /blacklist add [CRYPTO] [причина]
            if args and args[0].lower() == 'add':
                await self._blacklist_add(update, args[1:])
                return

            # Подкоманда: /blacklist remove [CRYPTO]
            if args and args[0].lower() == 'remove':
                await self._blacklist_remove(update, args[1:])
                return

            # По умолчанию: показать список blacklist
            await self._blacklist_show(update)

        except Exception as e:
            logger.error(f"❌ Ошибка в команде /blacklist: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ Ошибка выполнения команды. Проверь логи.",
                parse_mode='Markdown'
            )

    async def _blacklist_show(self, update: Update) -> None:
        """
        Показать список всех заблокированных криптовалют.
        """
        # Получение всех записей blacklist
        blacklist_entries = self.blacklist_repo.get_all()

        if not blacklist_entries:
            message = "🚫 *BLACKLIST*\n\n✅ Нет заблокированных пар"
            await update.message.reply_text(message, parse_mode='Markdown')
            return

        # Формирование сообщения
        message_lines = [f"🚫 *BLACKLIST* ({len(blacklist_entries)} пар)\n"]

        for idx, entry in enumerate(blacklist_entries, 1):
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
            current_part = f"🚫 *BLACKLIST* ({len(blacklist_entries)} пар)\n\n"
            
            for idx, entry in enumerate(blacklist_entries, 1):
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

    async def _blacklist_add(self, update: Update, args: list) -> None:
        """
        Добавить криптовалюту в blacklist вручную.
        
        Args:
            update: Telegram Update объект
            args: Аргументы команды [CRYPTO, причина...]
        """
        # Валидация: нужен минимум crypto и причина
        if len(args) < 2:
            await update.message.reply_text(
                "❌ *Неправильный формат команды*\n\n"
                "Используй: `/blacklist add [CRYPTO] [причина]`\n\n"
                "Пример:\n"
                "`/blacklist add BTC Manual block - suspicious activity`",
                parse_mode='Markdown'
            )
            return

        # Парсинг аргументов
        crypto = args[0].upper()  # Первый аргумент - символ криптовалюты
        reason = " ".join(args[1:])  # Все остальное - причина

        logger.info(f"📱 Попытка добавить {crypto} в blacklist. Причина: {reason}")

        # Проверка: уже в blacklist?
        if self.blacklist_repo.is_blacklisted(crypto):
            await update.message.reply_text(
                f"⚠️ *{crypto}* уже находится в blacklist",
                parse_mode='Markdown'
            )
            return

        # Добавление в БД
        success = self.blacklist_repo.add_to_blacklist(
            crypto=crypto,
            reason=f"Manual: {reason}",
            error_code=None,
            timestamp=datetime.now()
        )

        if success:
            # Успешное добавление
            message = f"""✅ *{crypto} добавлен в blacklist*

📝 Причина: {reason}
📅 Время: {datetime.now().strftime("%d.%m.%Y %H:%M")}

Бот больше не будет открывать позиции по этой паре."""
            
            logger.info(f"✅ {crypto} успешно добавлен в blacklist через Telegram")
        else:
            # Ошибка добавления
            message = f"❌ Не удалось добавить *{crypto}* в blacklist. Проверь логи."
            logger.error(f"❌ Ошибка добавления {crypto} в blacklist")

        await update.message.reply_text(message, parse_mode='Markdown')

    async def _blacklist_remove(self, update: Update, args: list) -> None:
        """
        Удалить криптовалюту из blacklist.
        
        Args:
            update: Telegram Update объект
            args: Аргументы команды [CRYPTO]
        """
        # Валидация: нужен символ криптовалюты
        if len(args) < 1:
            await update.message.reply_text(
                "❌ *Неправильный формат команды*\n\n"
                "Используй: `/blacklist remove [CRYPTO]`\n\n"
                "Пример:\n"
                "`/blacklist remove BTC`",
                parse_mode='Markdown'
            )
            return

        # Парсинг аргументов
        crypto = args[0].upper()  # Символ криптовалюты

        logger.info(f"📱 Попытка удалить {crypto} из blacklist")

        # Проверка: есть ли в blacklist?
        if not self.blacklist_repo.is_blacklisted(crypto):
            await update.message.reply_text(
                f"⚠️ *{crypto}* не найден в blacklist",
                parse_mode='Markdown'
            )
            return

        # Получаем детали перед удалением (для вывода в сообщении)
        entry = self.blacklist_repo.get_by_crypto(crypto)
        reason = entry.reason if entry else "Неизвестна"

        # Удаление из БД
        success = self.blacklist_repo.remove_from_blacklist(crypto)

        if success:
            # Успешное удаление
            message = f"""✅ *{crypto} удален из blacklist*

📝 Причина блокировки была: {reason}
📅 Время удаления: {datetime.now().strftime("%d.%m.%Y %H:%M")}

Бот снова может открывать позиции по этой паре."""
            
            logger.info(f"✅ {crypto} успешно удален из blacklist через Telegram")
        else:
            # Ошибка удаления
            message = f"❌ Не удалось удалить *{crypto}* из blacklist. Проверь логи."
            logger.error(f"❌ Ошибка удаления {crypto} из blacklist")

        await update.message.reply_text(message, parse_mode='Markdown')

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
