# -*- coding: utf-8 -*-
"""Анализатор спредов"""
import logging
from config import MIN_SPREAD_PCT

logger = logging.getLogger(__name__)

class SpreadAnalyzer:
    """Анализ и фильтрация спредов"""
    
    @staticmethod
    def calculate_all_spreads(orderbooks: dict) -> list:
        """Рассчитывает спреды для всех пар"""
        all_pairs = []
        for crypto, prices in orderbooks.items():
            spot_ask = prices['spot_ask']
            futures_bid = prices['futures_bid']
            
            if spot_ask <= 0:
                continue
            
            spread = futures_bid - spot_ask
            spread_pct = (spread / spot_ask) * 100
            
            all_pairs.append({
                "crypto": crypto,
                "spot_ask": spot_ask,
                "futures_bid": futures_bid,
                "spread_pct": round(spread_pct, 6)
            })
        
        all_pairs.sort(key=lambda x: x['spread_pct'], reverse=True)
        return all_pairs
    
    @staticmethod
    def filter_and_display(orderbooks: dict) -> list:
        """Фильтрует и отображает пары по минимальному спреду"""
        logger.info(f"📊 Анализ спредов...")
        all_pairs = SpreadAnalyzer.calculate_all_spreads(orderbooks)
        
        logger.info(f"ТОП-5 спредов:")
        for i, pair in enumerate(all_pairs[:5], 1):
            status = "✅ PASS" if pair['spread_pct'] >= MIN_SPREAD_PCT else "❌ FAIL"
            logger.info(
                f"  {i}. {status} {pair['crypto']:8s} | "
                f"ASK: {pair['spot_ask']:.6f} | "
                f"BID: {pair['futures_bid']:.6f} | "
                f"Спред: {pair['spread_pct']:.4f}%"
            )
        
        filtered_pairs = [p for p in all_pairs if p['spread_pct'] >= MIN_SPREAD_PCT]
        logger.info(f"✅ OK: {len(filtered_pairs)} пар >= {MIN_SPREAD_PCT}%")
        
        if filtered_pairs:
            logger.info(f"ТОП-10 после фильтрации (>= {MIN_SPREAD_PCT}%):")
            for i, pair in enumerate(filtered_pairs[:10], 1):
                logger.info(
                    f"  {i}. {pair['crypto']:8s} | "
                    f"ASK: {pair['spot_ask']:.6f} | "
                    f"BID: {pair['futures_bid']:.6f} | "
                    f"Спред: {pair['spread_pct']:.4f}%"
                )
        
        return filtered_pairs
