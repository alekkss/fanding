# pnl_calculator.py
# -*- coding: utf-8 -*-

from typing import Dict

class PnLCalculator:
    """
    Калькулятор прибыли/убытка для закрытых сделок.
    Статический класс без состояния.
    """

    @staticmethod
    def calculate_pnl(
        entry_price: float,
        exit_price: float,
        position_size: float,
        commission_rate: float,
        total_funding_received: float
    ) -> Dict[str, float]:
        """
        Рассчитывает чистую прибыль/убыток по сделке.
        """
        # 1. PnL от цены (Price PnL)
        # Для арбитража (Long Spot + Short Future):
        # Прибыль = (Exit Spot - Entry Spot) + (Entry Future - Exit Future)
        # Но упрощенно можно считать через спред, если position_size в USDT:
        # PnL ~= (Spread_Change_Pct) * Size
        # Ниже классическая формула для совокупной позиции, приведенная к USDT
        price_pnl = ((exit_price - entry_price) / entry_price) * position_size

        # 2. Комиссия (Commission) за круг (вход + выход)
        # Entry Volume + Exit Volume ~= 2 * position_size
        total_volume = position_size * 2
        commission = total_volume * commission_rate

        # 3. Чистая прибыль
        net_pnl = price_pnl + total_funding_received - commission

        return {
            "net_pnl": round(net_pnl, 4),
            "price_pnl": round(price_pnl, 4),
            "commission": round(commission, 4),
            "funding": round(total_funding_received, 4)
        }
