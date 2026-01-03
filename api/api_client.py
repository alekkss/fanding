# -*- coding: utf-8 -*-

"""Клиент для работы с Bybit API"""

import json
import hmac
import hashlib
import requests
import logging
import time
from typing import Optional

from api.auth import get_api_key, get_api_secret
from utils.utils import get_corrected_timestamp
from config import API_BASE_URL, RECV_WINDOW
from api.rate_limiter import get_rate_limiter

logger = logging.getLogger(__name__)


class BybitAPIClient:
    """Клиент для взаимодействия с Bybit API v5"""
    
    # Количество повторных попыток при ошибках
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0  # секунды

    @staticmethod
    def get(endpoint: str, params: dict = None) -> dict:
        """GET запрос к API с rate limiting и retry логикой"""
        rate_limiter = get_rate_limiter()
        
        for attempt in range(BybitAPIClient.MAX_RETRIES):
            try:
                # НОВОЕ: Ждем если достигнут rate limit
                rate_limiter.wait_if_needed(endpoint)
                
                url = f"{API_BASE_URL}{endpoint}"
                response = requests.get(url, params=params, timeout=10)
                
                # НОВОЕ: Проверяем HTTP 429 (rate limit)
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 5))
                    logger.warning(f"⚠️ HTTP 429 Rate Limit для GET {endpoint}, ждем {retry_after}s")
                    time.sleep(retry_after)
                    continue
                
                response.raise_for_status()
                data = response.json()
                
                # НОВОЕ: Проверяем retCode в ответе (специфика Bybit)
                ret_code = data.get('retCode')
                if ret_code == 10006:  # Rate limit exceeded
                    logger.warning(f"⚠️ Bybit Rate Limit (retCode 10006) для GET {endpoint}, повтор через {BybitAPIClient.RETRY_DELAY}s")
                    time.sleep(BybitAPIClient.RETRY_DELAY)
                    continue
                
                return data
                
            except requests.exceptions.Timeout:
                logger.warning(f"⏱️ Timeout для GET {endpoint}, попытка {attempt + 1}/{BybitAPIClient.MAX_RETRIES}")
                if attempt < BybitAPIClient.MAX_RETRIES - 1:
                    time.sleep(BybitAPIClient.RETRY_DELAY * (attempt + 1))
                    continue
                else:
                    logger.error(f"❌ GET {endpoint} timeout после {BybitAPIClient.MAX_RETRIES} попыток")
                    return {}
            
            except requests.exceptions.RequestException as e:
                logger.error(f"❌ GET {endpoint} ошибка: {e}, попытка {attempt + 1}/{BybitAPIClient.MAX_RETRIES}")
                if attempt < BybitAPIClient.MAX_RETRIES - 1:
                    time.sleep(BybitAPIClient.RETRY_DELAY * (attempt + 1))
                    continue
                else:
                    return {}
        
        return {}

    @staticmethod
    def post(endpoint: str, data: dict) -> dict:
        """POST запрос к API с подписью, rate limiting и retry логикой"""
        rate_limiter = get_rate_limiter()
        
        for attempt in range(BybitAPIClient.MAX_RETRIES):
            try:
                # НОВОЕ: Ждем если достигнут rate limit
                rate_limiter.wait_if_needed(endpoint)
                
                url = f"{API_BASE_URL}{endpoint}"
                api_key = get_api_key()
                api_secret = get_api_secret()
                
                timestamp = get_corrected_timestamp()
                if timestamp is None:
                    logger.error("Не удалось получить timestamp")
                    return {}
                
                timestamp_str = str(timestamp)
                body_str = json.dumps(data)
                param_str = timestamp_str + api_key + RECV_WINDOW + body_str
                
                signature = hmac.new(
                    api_secret.encode('utf-8'),
                    param_str.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                
                headers = {
                    "X-BAPI-API-KEY": api_key,
                    "X-BAPI-TIMESTAMP": timestamp_str,
                    "X-BAPI-SIGN": signature,
                    "X-BAPI-RECV-WINDOW": RECV_WINDOW,
                    "Content-Type": "application/json"
                }
                
                response = requests.post(url, data=body_str, headers=headers, timeout=10)
                
                # НОВОЕ: Проверяем HTTP 429 (rate limit)
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 5))
                    logger.warning(f"⚠️ HTTP 429 Rate Limit для POST {endpoint}, ждем {retry_after}s")
                    time.sleep(retry_after)
                    continue
                
                response.raise_for_status()
                result = response.json()
                
                # НОВОЕ: Проверяем retCode в ответе
                ret_code = result.get('retCode')
                if ret_code == 10006:  # Rate limit exceeded
                    logger.warning(f"⚠️ Bybit Rate Limit (retCode 10006) для POST {endpoint}, повтор через {BybitAPIClient.RETRY_DELAY}s")
                    time.sleep(BybitAPIClient.RETRY_DELAY)
                    continue
                
                return result
                
            except requests.exceptions.Timeout:
                logger.warning(f"⏱️ Timeout для POST {endpoint}, попытка {attempt + 1}/{BybitAPIClient.MAX_RETRIES}")
                if attempt < BybitAPIClient.MAX_RETRIES - 1:
                    time.sleep(BybitAPIClient.RETRY_DELAY * (attempt + 1))
                    continue
                else:
                    logger.error(f"❌ POST {endpoint} timeout после {BybitAPIClient.MAX_RETRIES} попыток")
                    return {}
            
            except requests.exceptions.RequestException as e:
                logger.error(f"❌ POST {endpoint} ошибка: {e}, попытка {attempt + 1}/{BybitAPIClient.MAX_RETRIES}")
                if attempt < BybitAPIClient.MAX_RETRIES - 1:
                    time.sleep(BybitAPIClient.RETRY_DELAY * (attempt + 1))
                    continue
                else:
                    return {}
        
        return {}
