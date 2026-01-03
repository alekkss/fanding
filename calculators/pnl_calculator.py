# pnl_calculator.py
# -*- coding: utf-8 -*-

from typing import Dict

class PnLCalculator:
    """
    Калькулятор прибыли/убытка для арбитражных сделок.
    Стратегия: Long Spot + Short Futures
    """
    
    @staticmethod
    def calculate_pnl(
        spot_entry_price: float,
        spot_exit_price: float,
        futures_entry_price: float,
        futures_exit_price: float,
        spot_qty: float,
        futures_qty: float,
        commission_rate: float,
        total_funding_received: float
    ) -> Dict[str, float]:
        """
        Рассчитывает чистую прибыль/убыток по арбитражной сделке.
        """
        
        # 1. PnL от СПОТА (Long позиция)
        spot_pnl = (spot_exit_price - spot_entry_price) * spot_qty
        
        # 2. PnL от ФЬЮЧЕРСА (Short позиция)
        futures_pnl = (futures_entry_price - futures_exit_price) * futures_qty
        
        # 3. Общий Price PnL
        price_pnl = spot_pnl + futures_pnl
        
        # 4. 🆕 ПРАВИЛЬНЫЙ РАСЧЕТ КОМИССИИ
        # Считаем среднюю позицию (так как спот и фьючерс это одна позиция)
        spot_entry_volume = spot_qty * spot_entry_price
        futures_entry_volume = futures_qty * futures_entry_price
        average_position_size = (spot_entry_volume + futures_entry_volume) / 2
        
        # Комиссия за круг (вход + выход)
        # Множитель 2: одна операция на открытие, одна на закрытие
        commission = average_position_size * 2 * commission_rate
        
        # Альтернативный метод (более точный при изменении цены):
        # spot_exit_volume = spot_qty * spot_exit_price
        # futures_exit_volume = futures_qty * futures_exit_price
        # 
        # Комиссия от спота
        # spot_commission = (spot_entry_volume + spot_exit_volume) * commission_rate
        # 
        # Комиссия от фьючерса
        # futures_commission = (futures_entry_volume + futures_exit_volume) * commission_rate
        # 
        # Средняя комиссия (так как это одна позиция с хеджем)
        # commission = (spot_commission + futures_commission) / 2
        
        # 5. Чистая прибыль/убыток
        net_pnl = price_pnl + total_funding_received - commission
        
        return {
            "net_pnl": round(net_pnl, 4),
            "price_pnl": round(price_pnl, 4),
            "spot_pnl": round(spot_pnl, 4),
            "futures_pnl": round(futures_pnl, 4),
            "commission": round(commission, 4),
            "funding": round(total_funding_received, 4)
        }
    
    @staticmethod
    def calculate_spread_change(
        entry_spread_pct: float,
        close_spread_pct: float
    ) -> Dict[str, float]:
        """
        Рассчитывает изменение спреда между входом и выходом.
        """
        spread_change = close_spread_pct - entry_spread_pct
        
        if spread_change < -0.01:
            direction = "narrowed"
        elif spread_change > 0.01:
            direction = "widened"
        else:
            direction = "unchanged"
        
        return {
            "spread_change": round(spread_change, 4),
            "spread_direction": direction
        }
