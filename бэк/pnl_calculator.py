from typing import Dict


class PnLCalculator:
    """Калькулятор прибыли/убытка для закрытых сделок"""
    
    def __init__(self, commission_rate: float):
        self._commission_rate = commission_rate
    
    def calculate_pnl(
        self,
        entry_price: float,
        exit_price: float,
        position_size: float,
        spread: float,
        total_funding_received: float
    ) -> Dict[str, float]:
        """
        Рассчитывает чистую прибыль/убыток по сделке
        
        Args:
            entry_price: Цена входа
            exit_price: Цена выхода
            position_size: Размер позиции в USDT
            spread: Спред в USDT
            total_funding_received: Полученный фандинг (может быть отрицательным)
        
        Returns:
            Словарь с детализацией PnL
        """
        # Прибыль/убыток от изменения цены
        price_pnl = ((exit_price - entry_price) / entry_price) * position_size
        
        # Комиссия за полный цикл
        commission = position_size * self._commission_rate
        
        # Затраты на спред
        spread_cost = spread
        
        # Чистая прибыль
        net_pnl = price_pnl - spread_cost - commission + total_funding_received
        
        return {
            "net_pnl": net_pnl,
            "price_pnl": price_pnl,
            "commission": commission,
            "spread_cost": spread_cost,
            "funding": total_funding_received
        }
