# -*- coding: utf-8 -*-
"""Получение funding rates"""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from api.api_client import BybitAPIClient
from config import MAX_WORKERS_FUNDING

logger = logging.getLogger(__name__)

class FundingRateFetcher:
    @staticmethod
    def get_single_funding_rate(crypto: str) -> float:
        """Получает ТЕКУЩИЙ funding rate через /market/tickers"""
        try:
            data = BybitAPIClient.get("/market/tickers", {
                "category": "linear",
                "symbol": f"{crypto}USDT"
            })
            
            if data.get('result', {}).get('list'):
                ticker = data['result']['list'][0]
                funding_rate_raw = ticker.get('fundingRate')
                
                if funding_rate_raw is None or funding_rate_raw == '':
                    logger.warning(f"Funding rate для {crypto} отсутствует")
                    return 0.0
                
                # Преобразуем в float и умножаем на 100 для процентов
                funding_rate = float(funding_rate_raw) * 100
                
                logger.info(f"FR {crypto}: {funding_rate:.6f}%")
                
                return funding_rate
            else:
                logger.warning(f"Нет данных funding rate для {crypto}")
                return 0.0
                
        except Exception as e:
            logger.error(f"Ошибка получения FR для {crypto}: {e}")
            return 0.0

    @staticmethod
    def get_batch_funding_rates(crypto_list: list) -> dict:
        if not crypto_list:
            return {}
        logger.info(f"📊 Получение FR для {len(crypto_list)} символов...")
        funding_rates = {}
        lock = threading.Lock()
        
        def fetch_single(crypto):
            rate = FundingRateFetcher.get_single_funding_rate(crypto)
            with lock:
                funding_rates[crypto] = rate
            return True
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS_FUNDING) as executor:
            futures = {executor.submit(fetch_single, crypto): crypto for crypto in crypto_list}
            for future in as_completed(futures):
                future.result()
        
        logger.info(f"✅ OK: {len(funding_rates)} FR")
        
        # Логируем все FR
        for crypto, rate in funding_rates.items():
            logger.info(f"  └─ {crypto}: FR = {rate:.4f}%")
        
        return funding_rates
