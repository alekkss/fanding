# -*- coding: utf-8 -*-
"""Калькулятор арбитража"""
import logging
from config import COMMISSION_PCT, MIN_PROFIT_PCT, MIN_FUNDING_RATE

logger = logging.getLogger(__name__)

class ArbitrageCalculator:
    @staticmethod
    def calculate_profit_from_pair(pair: dict, funding_rate: float) -> dict:
        spread_pct = pair['spread_pct']
        net_profit_pct = spread_pct + funding_rate - COMMISSION_PCT
        
        return {
            "crypto": pair['crypto'],
            "spot_ask": pair['spot_ask'],
            "futures_bid": pair['futures_bid'],
            "spread_pct": spread_pct,
            "funding_rate": round(funding_rate, 6),
            "net_profit_pct": round(net_profit_pct, 6)
        }
    
    @staticmethod
    def find_best_opportunity(filtered_pairs: list, funding_rates: dict) -> tuple:
        logger.info("🔍 Поиск лучшей возможности...")
        opportunities = []
        rejected_by_fr = []
        
        for pair in filtered_pairs:
            crypto = pair['crypto']
            if crypto not in funding_rates:
                continue
            
            fr = funding_rates[crypto]
            if fr < MIN_FUNDING_RATE:
                rejected_by_fr.append({
                    "crypto": crypto,
                    "spread_pct": pair['spread_pct'],
                    "funding_rate": fr
                })
                continue
            
            profit_data = ArbitrageCalculator.calculate_profit_from_pair(pair, fr)
            opportunities.append(profit_data)
        
        if rejected_by_fr:
            logger.info(f"❌ Отклонено по FR: {len(rejected_by_fr)}")
            for i, rej in enumerate(rejected_by_fr[:5], 1):
                logger.info(f"  {i}. {rej['crypto']:8s} | Спред: {rej['spread_pct']:.4f}% | FR: {rej['funding_rate']:.4f}%")
        
        if not opportunities:
            logger.warning("⚠️ Нет возможностей после фильтрации FR")
            return None, 0, None
        
        opportunities.sort(key=lambda x: x['net_profit_pct'], reverse=True)
        
        logger.info(f"ТОП-10 по чистой прибыли (с FR):")
        for i, opp in enumerate(opportunities[:10], 1):
            status = "✅ PROFIT" if opp['net_profit_pct'] >= MIN_PROFIT_PCT else "⚠️ LOW"
            logger.info(
                f"  {i}. {status} {opp['crypto']:8s} | ASK: {opp['spot_ask']:.6f} | BID: {opp['futures_bid']:.6f} | "
                f"Спред: {opp['spread_pct']:.4f}% | FR: {opp['funding_rate']:.4f}% | Profit: {opp['net_profit_pct']:.4f}%"
            )
        
        best = opportunities[0]
        if best['net_profit_pct'] >= MIN_PROFIT_PCT:
            logger.info(f"🎯 BEST: {best['crypto']} | Profit: {best['net_profit_pct']:.4f}%")
            return best['crypto'], best['net_profit_pct'], best
        
        logger.info(f"⚠️ WARNING: Best profit {best['net_profit_pct']:.4f}% < минимума {MIN_PROFIT_PCT}%")
        return None, 0, None
    
    @staticmethod
    def find_top_opportunities(filtered_pairs: list, funding_rates: dict, limit: int = 3) -> list:
        """Находит топ N лучших возможностей"""
        logger.info(f"🔍 Поиск топ-{limit} возможностей...")
        
        opportunities = []
        
        for pair in filtered_pairs:
            crypto = pair['crypto']
            
            if crypto not in funding_rates:
                continue
            
            fr = funding_rates[crypto]
            if fr < MIN_FUNDING_RATE:
                continue
            
            result = ArbitrageCalculator.calculate_profit_from_pair(pair, fr)
            
            if result['net_profit_pct'] >= MIN_PROFIT_PCT:
                opportunities.append(result)
        
        # Сортируем по прибыли
        opportunities.sort(key=lambda x: x['net_profit_pct'], reverse=True)
        
        # Возвращаем топ N
        top_opportunities = opportunities[:limit]
        
        logger.info(f"✅ Найдено {len(top_opportunities)} прибыльных возможностей")
        for i, opp in enumerate(top_opportunities, 1):
            logger.info(f"   {i}. {opp['crypto']} | Profit: {opp['net_profit_pct']:.4f}%")
        
        return top_opportunities

