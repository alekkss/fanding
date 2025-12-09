# pnl_calculator.py
# -*- coding: utf-8 -*-

from typing import Dict

class PnLCalculator:
    """
    Калькулятор прибыли/убытка для арбитражных сделок.
    Стратегия: Long Spot + Short Futures
    Статический класс без состояния.
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
        
        Args:
            spot_entry_price: Цена покупки спота
            spot_exit_price: Цена продажи спота
            futures_entry_price: Цена открытия шорта на фьючерсе
            futures_exit_price: Цена закрытия шорта на фьючерсе
            spot_qty: Количество монет на споте
            futures_qty: Количество монет на фьючерсе
            commission_rate: Ставка комиссии (например, 0.002 для 0.2%)
            total_funding_received: Накопленный фандинг (+ прибыль / - убыток)
        
        Returns:
            dict: {
                "net_pnl": Чистая прибыль/убыток,
                "price_pnl": PnL от изменения цен,
                "spot_pnl": PnL только от спота,
                "futures_pnl": PnL только от фьючерса,
                "commission": Общая комиссия,
                "funding": Фандинг
            }
        """
        
        # 1. PnL от СПОТА (Long позиция)
        # Купили дешево → Продали дорого = Прибыль
        # Формула: (Цена продажи - Цена покупки) * Количество
        spot_pnl = (spot_exit_price - spot_entry_price) * spot_qty
        
        # 2. PnL от ФЬЮЧЕРСА (Short позиция)
        # Продали дорого → Купили дешево = Прибыль
        # ВАЖНО: Для шорта инвертируем формулу!
        # Формула: (Цена открытия - Цена закрытия) * Количество
        futures_pnl = (futures_entry_price - futures_exit_price) * futures_qty
        
        # 3. Общий Price PnL
        price_pnl = spot_pnl + futures_pnl
        
        # 4. Комиссия
        # Считаем объем в USDT для всех операций:
        # - Вход: покупка спота + продажа фьючерса
        # - Выход: продажа спота + покупка фьючерса
        
        # Объем входа
        spot_entry_volume = spot_qty * spot_entry_price
        futures_entry_volume = futures_qty * futures_entry_price
        
        # Объем выхода
        spot_exit_volume = spot_qty * spot_exit_price
        futures_exit_volume = futures_qty * futures_exit_price
        
        # Общий объем всех операций
        total_volume = (spot_entry_volume + futures_entry_volume + 
                       spot_exit_volume + futures_exit_volume)
        
        # Комиссия = Общий объем * Ставка
        commission = total_volume * commission_rate
        
        # 5. Чистая прибыль/убыток
        # Net PnL = Price PnL + Funding - Commission
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
        
        Args:
            entry_spread_pct: Спред при входе (%)
            close_spread_pct: Спред при выходе (%)
        
        Returns:
            dict: {
                "spread_change": Изменение спреда,
                "spread_direction": "narrowed" | "widened" | "unchanged"
            }
        """
        spread_change = close_spread_pct - entry_spread_pct
        
        if spread_change < -0.01:
            direction = "narrowed"  # Спред сузился (хорошо)
        elif spread_change > 0.01:
            direction = "widened"   # Спред расширился (плохо)
        else:
            direction = "unchanged"
        
        return {
            "spread_change": round(spread_change, 4),
            "spread_direction": direction
        }
