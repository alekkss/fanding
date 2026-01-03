# -*- coding: utf-8 -*-
"""Сервис для получения цен и orderbook"""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from api.api_client import BybitAPIClient
from config import MAX_WORKERS_ORDERBOOK

logger = logging.getLogger(__name__)

class PriceFetcher:
    """Получение цен и orderbook"""
    
    @staticmethod
    def get_all_symbols() -> list:
        """Получает список всех доступных символов на spot и futures"""
        logger.info("📊 Получение списка символов...")
        
        spot_data = BybitAPIClient.get("/market/tickers", {"category": "spot", "limit": 1000})
        spot_symbols = set()
        if spot_data.get('result', {}).get('list'):
            for ticker in spot_data['result']['list']:
                symbol = ticker['symbol']
                if symbol.endswith('USDT'):
                    crypto = symbol.replace('USDT', '')
                    spot_symbols.add(crypto)
        
        futures_data = BybitAPIClient.get("/market/tickers", {"category": "linear", "limit": 1000})
        futures_symbols = set()
        if futures_data.get('result', {}).get('list'):
            for ticker in futures_data['result']['list']:
                symbol = ticker['symbol']
                if symbol.endswith('USDT'):
                    crypto = symbol.replace('USDT', '')
                    futures_symbols.add(crypto)
        
        common_symbols = list(spot_symbols & futures_symbols)
        logger.info(f"✅ OK: {len(common_symbols)} символов")
        return common_symbols
    
    @staticmethod
    def get_orderbook(symbol: str, category: str) -> dict:
        """Получает orderbook для одного символа"""
        try:
            data = BybitAPIClient.get("/market/orderbook", {
                "category": category,
                "symbol": f"{symbol}USDT",
                "limit": 1
            })
            
            result = {}
            if data.get('result'):
                bids = data['result'].get('b', [])
                asks = data['result'].get('a', [])
                if bids:
                    result['bid'] = float(bids[0][0])
                if asks:
                    result['ask'] = float(asks[0][0])
            return result
        except Exception as e:
            logger.error(f"Ошибка orderbook {symbol}: {e}")
            return {}
    
    @staticmethod
    def get_orderbook_batch(symbols: list) -> dict:
        """Получает orderbook для списка символов параллельно"""
        logger.info(f"📖 Получение bidask для {len(symbols)} символов...")
        orderbooks = {}
        lock = threading.Lock()
        
        def fetch_orderbook(crypto):
            spot_ob = PriceFetcher.get_orderbook(crypto, "spot")
            futures_ob = PriceFetcher.get_orderbook(crypto, "linear")
            
            if spot_ob.get('ask') and futures_ob.get('bid'):
                with lock:
                    orderbooks[crypto] = {
                        "spot_ask": spot_ob['ask'],
                        "futures_bid": futures_ob['bid']
                    }
                return True
            return False
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS_ORDERBOOK) as executor:
            futures = {executor.submit(fetch_orderbook, crypto): crypto for crypto in symbols}
            for future in as_completed(futures):
                future.result()
                if len(orderbooks) % 50 == 0 and len(orderbooks) > 0:
                    logger.info(f"  └─ Загружено orderbook: {len(orderbooks)}/{len(symbols)}")
        
        logger.info(f"✅ OK: {len(orderbooks)} orderbook")
        return orderbooks
