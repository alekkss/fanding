# -*- coding: utf-8 -*-
"""Управление плечом"""
import logging
from api_client import BybitAPIClient
from config import LEVERAGE

logger = logging.getLogger(__name__)

class LeverageManager:
    @staticmethod
    def set_leverage(symbol: str, leverage: int = LEVERAGE) -> bool:
        try:
            data = {
                "category": "linear",
                "symbol": f"{symbol}USDT",
                "buyLeverage": str(leverage),
                "sellLeverage": str(leverage)
            }
            response = BybitAPIClient.post("/position/set-leverage", data)
            if response.get('retCode') == 0 or response.get('retCode') == 110043:
                logger.info(f"Плечо {leverage}x установлено для {symbol}")
                return True
            else:
                logger.error(f"Ошибка установки плеча: {response}")
                return False
        except Exception as e:
            logger.error(f"Ошибка установки плеча: {e}")
            return False
    
    @staticmethod
    def check_and_set_leverage(symbol: str) -> bool:
        return LeverageManager.set_leverage(symbol, LEVERAGE)
