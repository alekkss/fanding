# -*- coding: utf-8 -*-
"""
Форматирование сообщений для Telegram бота.
Преобразует данные в красивые Markdown сообщения с эмодзи.
"""

from datetime import datetime
from typing import List, Dict, Any


class MessageFormatter:
    """
    Форматирование сообщений для различных типов уведомлений.
    
    Single Responsibility: только форматирование текста.
    Все методы статические - нет состояния.
    """
    
    @staticmethod
    def format_position_opened(position_data: Dict[str, Any]) -> str:
        """
        Форматирует сообщение об открытии позиции.
        
        Args:
            position_data: Словарь с данными позиции
                - crypto: str
                - spot_entry_price: float
                - futures_entry_price: float
                - spot_qty: float
                - entry_spread_pct: float
                - funding_rate: float (опционально)
                - entry_timestamp: str (ISO format)
                
        Returns:
            str: Отформатированное сообщение
        """
        crypto = position_data.get('crypto', 'UNKNOWN')
        spot_price = position_data.get('spot_entry_price', 0)
        futures_price = position_data.get('futures_entry_price', 0)
        qty = position_data.get('spot_qty', 0)
        spread = position_data.get('entry_spread_pct', 0)
        fr = position_data.get('funding_rate', 0)
        timestamp = position_data.get('entry_timestamp', '')
        
        # Парсинг timestamp
        try:
            dt = datetime.fromisoformat(timestamp)
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            time_str = timestamp
        
        message = f"""🟢 *ПОЗИЦИЯ ОТКРЫТА*

💎 *{crypto}*
📊 Спред: `{spread:.2f}%` | FR: `{fr:.3f}%`

*Вход:*
├─ Спот: `{spot_price:,.2f}` USDT
├─ Фьючерс: `{futures_price:,.2f}` USDT
└─ Qty: `{qty:.4f}` {crypto}

⏰ {time_str}
"""
        return message
    
    @staticmethod
    def format_position_closed(closed_data: Dict[str, Any]) -> str:
        """
        Форматирует сообщение о закрытии позиции.
        
        Args:
            closed_data: Словарь с данными закрытой позиции
                - crypto: str
                - entry_time: str
                - close_time: str
                - pnl: dict (spot_pnl, futures_pnl, funding, commission, net_pnl)
                
        Returns:
            str: Отформатированное сообщение
        """
        crypto = closed_data.get('crypto', 'UNKNOWN')
        entry_time = closed_data.get('entry_time', '')
        close_time = closed_data.get('close_time', '')
        pnl = closed_data.get('pnl', {})
        
        # Расчет времени удержания
        try:
            entry_dt = datetime.fromisoformat(entry_time)
            close_dt = datetime.fromisoformat(close_time)
            duration = close_dt - entry_dt
            hours = int(duration.total_seconds() // 3600)
            minutes = int((duration.total_seconds() % 3600) // 60)
            duration_str = f"{hours}ч {minutes}м"
        except:
            duration_str = "N/A"
        
        # PnL данные
        spot_pnl = pnl.get('spot_pnl', 0)
        futures_pnl = pnl.get('futures_pnl', 0)
        funding = pnl.get('funding', 0)
        commission = pnl.get('commission', 0)
        net_pnl = pnl.get('net_pnl', 0)
        
        # Эмодзи для результата
        result_emoji = "✅" if net_pnl > 0 else "❌"
        
        message = f"""💰 *ПОЗИЦИЯ ЗАКРЫТА*

💎 *{crypto}*
⏱️ Удержание: `{duration_str}`

*PnL Breakdown:*
├─ Спот: `{spot_pnl:+.2f}` USDT
├─ Фьючерс: `{futures_pnl:+.2f}` USDT
├─ Funding: `{funding:+.2f}` USDT
├─ Commission: `-{commission:.2f}` USDT
└─ *NET: `{net_pnl:+.2f}` USDT* {result_emoji}
"""
        return message
    
    @staticmethod
    def format_critical_error(error_data: Dict[str, Any]) -> str:
        """
        Форматирует сообщение о критической ошибке.
        
        Args:
            error_data: Словарь с данными ошибки
                - type: str ('futures_opened_spot_failed' или 'system_error')
                - crypto: str (опционально)
                - qty: float (опционально)
                - message: str (описание ошибки)
                
        Returns:
            str: Отформатированное сообщение
        """
        error_type = error_data.get('type', 'unknown')
        message_text = error_data.get('message', 'Неизвестная ошибка')
        
        if error_type == 'futures_opened_spot_failed':
            crypto = error_data.get('crypto', 'UNKNOWN')
            qty = error_data.get('qty', 0)
            
            message = f"""🔴 *КРИТИЧЕСКАЯ ОШИБКА*

⚠️ Фьючерс открыт, спот НЕ открыт!
💎 *{crypto}*
📦 Qty: `{qty:.4f}`

🛠️ *ТРЕБУЕТСЯ РУЧНОЕ ЗАКРЫТИЕ*

_Детали:_ {message_text}
"""
        else:
            # Системная критическая ошибка
            message = f"""🔴 *КРИТИЧЕСКАЯ ОШИБКА СИСТЕМЫ*

⚠️ {message_text}

🛠️ Требуется внимание!
"""
        
        return message
    
    @staticmethod
    def format_blacklist_added(blacklist_data: Dict[str, Any]) -> str:
        """
        Форматирует сообщение о добавлении в blacklist.
        
        Args:
            blacklist_data: Словарь с данными blacklist
                - crypto: str
                - reason: str
                - error_code: int (опционально)
                
        Returns:
            str: Отформатированное сообщение
        """
        crypto = blacklist_data.get('crypto', 'UNKNOWN')
        reason = blacklist_data.get('reason', 'Не указана')
        error_code = blacklist_data.get('error_code')
        
        message = f"""🚫 *ДОБАВЛЕН В BLACKLIST*

💎 *{crypto}*
📝 Причина: _{reason}_
"""
        
        if error_code:
            message += f"\n⚠️ Код ошибки: `{error_code}`"
        
        return message
    
    @staticmethod
    def format_status(status_data: Dict[str, Any]) -> str:
        """
        Форматирует сообщение со статусом системы.
        
        Args:
            status_data: Словарь со статусом
                - open_positions: list
                - blacklist_count: int
                - uptime: str (опционально)
                
        Returns:
            str: Отформатированное сообщение
        """
        open_positions = status_data.get('open_positions', [])
        blacklist_count = status_data.get('blacklist_count', 0)
        uptime = status_data.get('uptime', 'N/A')
        
        message = f"""📊 *СТАТУС СИСТЕМЫ*

🟢 Открытых позиций: `{len(open_positions)}`
"""
        
        # Список открытых позиций
        if open_positions:
            message += "\n*Позиции:*\n"
            for pos in open_positions:
                crypto = pos.get('crypto', 'UNKNOWN')
                spread = pos.get('entry_spread_pct', 0)
                message += f"├─ {crypto} (спред: `{spread:.2f}%`)\n"
        else:
            message += "└─ _Нет открытых позиций_\n"
        
        message += f"\n🚫 Blacklist: `{blacklist_count}` монет"
        
        if uptime != 'N/A':
            message += f"\n⏰ Uptime: `{uptime}`"
        
        return message
    
    @staticmethod
    def format_statistics(stats_data: Dict[str, Any]) -> str:
        """
        Форматирует сообщение со статистикой.
        
        Args:
            stats_data: Словарь со статистикой
                - total_trades: int
                - winning_trades: int
                - win_rate: float
                - total_pnl: float
                - avg_pnl: float
                
        Returns:
            str: Отформатированное сообщение
        """
        total_trades = stats_data.get('total_trades', 0)
        winning_trades = stats_data.get('winning_trades', 0)
        win_rate = stats_data.get('win_rate', 0)
        total_pnl = stats_data.get('total_pnl', 0)
        avg_pnl = stats_data.get('avg_pnl', 0)
        
        # Эмодзи для результата
        pnl_emoji = "📈" if total_pnl > 0 else "📉"
        
        message = f"""📊 *СТАТИСТИКА*

🔢 Всего сделок: `{total_trades}`
✅ Прибыльных: `{winning_trades}`
📈 Win Rate: `{win_rate:.1%}`

💰 *Финансы:*
├─ Total PnL: `{total_pnl:+.2f}` USDT {pnl_emoji}
└─ Avg PnL: `{avg_pnl:+.2f}` USDT
"""
        
        return message
    
    @staticmethod
    def format_positions_list(positions: List[Dict[str, Any]]) -> str:
        """
        Форматирует список открытых позиций.
        
        Args:
            positions: Список позиций из PositionRepository (словари)
            
        Returns:
            str: Форматированное сообщение
        """
        if not positions:
            return "📍 Нет открытых позиций"
        
        lines = [f"📍 ОТКРЫТЫЕ ПОЗИЦИИ ({len(positions)})\n"]
        
        for idx, pos in enumerate(positions, 1):
            crypto = pos.get('crypto', 'N/A')
            
            # Парсим время входа
            try:
                entry_timestamp = pos.get('entry_timestamp', '')
                entry_time = datetime.fromisoformat(entry_timestamp)
                time_str = entry_time.strftime("%d.%m %H:%M")
            except:
                time_str = "N/A"
            
            # Рассчитываем текущее время в позиции
            try:
                entry_timestamp = pos.get('entry_timestamp', '')
                entry_dt = datetime.fromisoformat(entry_timestamp)
                now = datetime.now()
                duration = now - entry_dt
                hours = int(duration.total_seconds() // 3600)
                minutes = int((duration.total_seconds() % 3600) // 60)
                duration_str = f"{hours}ч {minutes}мин"
            except:
                duration_str = "N/A"
            
            spot_price = pos.get('spot_entry_price', 0.0)
            futures_price = pos.get('futures_entry_price', 0.0)
            spot_qty = pos.get('spot_qty', 0.0)
            futures_qty = pos.get('futures_qty', 0.0)
            spread = pos.get('entry_spread_pct', 0.0)
            
            lines.append(f"{idx}. {crypto}")
            lines.append(f"├─ Вход: {time_str} ({duration_str} назад)")
            lines.append(f"├─ Спот: {spot_price:.6f} USDT (qty: {spot_qty:.4f})")
            lines.append(f"├─ Фьючерс: {futures_price:.6f} USDT (qty: {futures_qty:.4f})")
            lines.append(f"└─ Спред: {spread:.2f}%")
            
            # Добавляем пустую строку между позициями (кроме последней)
            if idx < len(positions):
                lines.append("")
        
        return "\n".join(lines)
