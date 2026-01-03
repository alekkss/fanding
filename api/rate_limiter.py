# -*- coding: utf-8 -*-

"""Rate Limiter для Bybit API v5"""

import time
import logging
import threading
from collections import deque
from typing import Optional

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limiter для Bybit API с учетом weight каждого endpoint
    Bybit лимит: 120 запросов в секунду (основной), или 600 weight/sec для некоторых endpoint
    """
    
    # Weight для каждого endpoint согласно документации Bybit
    ENDPOINT_WEIGHTS = {
        "/market/tickers": 1,
        "/market/orderbook": 1,
        "/market/instruments-info": 1,
        "/market/time": 1,
        "/order/create": 1,
        "/position/set-leverage": 1,
        "/account/wallet-balance": 1,
    }
    
    def __init__(self, max_requests_per_second: int = 50, max_weight_per_second: int = 300):
        """
        Args:
            max_requests_per_second: Максимум запросов в секунду (безопасное значение < 120)
            max_weight_per_second: Максимум weight в секунду (безопасное значение < 600)
        """
        self.max_requests_per_second = max_requests_per_second
        self.max_weight_per_second = max_weight_per_second
        
        # Хранилище timestamps последних запросов
        self.request_times = deque()
        self.weight_times = deque()  # (timestamp, weight)
        
        self.lock = threading.Lock()
        
        # Статистика
        self.total_requests = 0
        self.total_weight = 0
        self.rate_limit_hits = 0
        
        logger.info(f"RateLimiter инициализирован: {max_requests_per_second} req/sec, {max_weight_per_second} weight/sec")
    
    def get_endpoint_weight(self, endpoint: str) -> int:
        """Возвращает weight для endpoint"""
        # Убираем query параметры если есть
        base_endpoint = endpoint.split('?')[0]
        return self.ENDPOINT_WEIGHTS.get(base_endpoint, 1)
    
    def wait_if_needed(self, endpoint: str) -> None:
        """
        Проверяет rate limits и ждет если необходимо
        """
        weight = self.get_endpoint_weight(endpoint)
        
        with self.lock:
            now = time.time()
            
            # Очищаем старые записи (старше 1 секунды)
            self._cleanup_old_records(now)
            
            # Проверяем лимит по количеству запросов
            if len(self.request_times) >= self.max_requests_per_second:
                oldest_request = self.request_times[0]
                wait_time = 1.0 - (now - oldest_request)
                
                if wait_time > 0:
                    self.rate_limit_hits += 1
                    logger.debug(f"⏱️ Rate limit: ждем {wait_time:.2f}s (запросов: {len(self.request_times)}/{self.max_requests_per_second})")
                    time.sleep(wait_time)
                    now = time.time()
                    self._cleanup_old_records(now)
            
            # Проверяем лимит по weight
            current_weight = sum(w for _, w in self.weight_times)
            if current_weight + weight > self.max_weight_per_second:
                if self.weight_times:
                    oldest_weight_time = self.weight_times[0][0]
                    wait_time = 1.0 - (now - oldest_weight_time)
                    
                    if wait_time > 0:
                        self.rate_limit_hits += 1
                        logger.warning(f"⏱️ Weight limit: ждем {wait_time:.2f}s (weight: {current_weight + weight}/{self.max_weight_per_second})")
                        time.sleep(wait_time)
                        now = time.time()
                        self._cleanup_old_records(now)
            
            # Записываем новый запрос
            self.request_times.append(now)
            self.weight_times.append((now, weight))
            self.total_requests += 1
            self.total_weight += weight
    
    def _cleanup_old_records(self, now: float) -> None:
        """Удаляет записи старше 1 секунды"""
        # Очистка request_times
        while self.request_times and now - self.request_times[0] > 1.0:
            self.request_times.popleft()
        
        # Очистка weight_times
        while self.weight_times and now - self.weight_times[0][0] > 1.0:
            self.weight_times.popleft()
    
    def get_stats(self) -> dict:
        """Возвращает статистику использования"""
        with self.lock:
            now = time.time()
            self._cleanup_old_records(now)
            
            current_weight = sum(w for _, w in self.weight_times)
            
            return {
                "total_requests": self.total_requests,
                "total_weight": self.total_weight,
                "rate_limit_hits": self.rate_limit_hits,
                "current_requests_in_window": len(self.request_times),
                "current_weight_in_window": current_weight,
                "max_requests_per_second": self.max_requests_per_second,
                "max_weight_per_second": self.max_weight_per_second
            }
    
    def reset_stats(self) -> None:
        """Сбрасывает статистику"""
        with self.lock:
            self.total_requests = 0
            self.total_weight = 0
            self.rate_limit_hits = 0


# Глобальный экземпляр rate limiter
_global_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Возвращает глобальный экземпляр rate limiter"""
    global _global_rate_limiter
    if _global_rate_limiter is None:
        _global_rate_limiter = RateLimiter(
            max_requests_per_second=50,  # Безопасное значение
            max_weight_per_second=300    # Безопасное значение
        )
    return _global_rate_limiter
