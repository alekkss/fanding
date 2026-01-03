# funding_calculator.py
# -*- coding: utf-8 -*-

import logging
import requests
from datetime import datetime, timedelta
from typing import Optional
from api.auth import get_api_key, get_api_secret, create_signature
from utils.utils import get_corrected_timestamp
from config import API_BASE_URL, RECV_WINDOW

logger = logging.getLogger(__name__)

class RealizedFundingCalculator:
    """
    Калькулятор РЕАЛЬНОГО накопленного фандинга.
    Запрашивает историю исполнений (executions) с типом 'Funding' у биржи.
    """
    
    @staticmethod
    def _get_signed(endpoint: str, params: dict = None) -> dict:
        """
        Выполняет приватный GET запрос с подписью для Bybit API v5
        
        Args:
            endpoint: Endpoint без базового URL (например "/execution/list")
            params: Параметры запроса
        
        Returns:
            dict: Ответ API
        """
        try:
            if params is None:
                params = {}
            
            url = f"{API_BASE_URL}{endpoint}"
            api_key = get_api_key()
            api_secret = get_api_secret()
            timestamp = get_corrected_timestamp()
            
            if timestamp is None:
                logger.error("Не удалось получить timestamp")
                return {}
            
            timestamp_str = str(timestamp)
            
            # Добавляем обязательные параметры для подписи
            params_with_auth = {
                "api_key": api_key,
                "timestamp": timestamp_str,
                **params
            }
            
            # ИСПОЛЬЗУЕМ ТВОЮ ФУНКЦИЮ create_signature из auth.py
            signature = create_signature(api_secret, params_with_auth)
            
            # Добавляем подпись
            params_with_auth["sign"] = signature
            
            # Выполняем запрос
            response = requests.get(url, params=params_with_auth, timeout=10)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Ошибка приватного GET запроса {endpoint}: {e}")
            return {}
    
    @staticmethod
    def get_accumulated_funding(
        crypto: str,
        start_time_iso: str,
        end_time_iso: Optional[str] = None
    ) -> float:
        """
        Возвращает сумму полученного (или уплаченного) фандинга в USDT.
        
        Args:
            crypto: Символ (например, "BTC")
            start_time_iso: Время открытия позиции (ISO format string)
            end_time_iso: Время закрытия (ISO format string). Если None, берется текущее.
        
        Returns:
            float: Сумма фандинга (Положительное число = ПРИБЫЛЬ, Отрицательное = УБЫТОК)
        """
        try:
            symbol = f"{crypto}USDT"
            
            # 1. Конвертация времени в миллисекунды
            dt_start = datetime.fromisoformat(start_time_iso)
            
            if end_time_iso:
                dt_end = datetime.fromisoformat(end_time_iso)
            else:
                dt_end = datetime.now()
            
            logger.info(f"[{crypto}] 🔎 Запрос истории фандинга: {dt_start} -> {dt_end}")
            
            # 2. НОВОЕ: Разбиваем на интервалы по 7 дней (API ограничение)
            MAX_DAYS = 7
            all_executions = []
            
            current_start = dt_start
            
            while current_start < dt_end:
                # Конец текущего интервала: либо +7 дней, либо конечная дата
                current_end = min(current_start + timedelta(days=MAX_DAYS), dt_end)
                
                start_ts = int(current_start.timestamp() * 1000)
                end_ts = int(current_end.timestamp() * 1000)
                
                logger.debug(f"[{crypto}] Запрос интервала: {current_start} -> {current_end}")
                
                params = {
                    "category": "linear",
                    "symbol": symbol,
                    "execType": "Funding",
                    "startTime": str(start_ts),
                    "endTime": str(end_ts),
                    "limit": "100"
                }
                
                # Используем приватный GET с подписью
                response = RealizedFundingCalculator._get_signed("/execution/list", params)
                
                if not response or response.get('retCode') != 0:
                    logger.error(f"[{crypto}] Ошибка API для интервала {current_start}-{current_end}: {response}")
                    # Продолжаем со следующим интервалом
                    current_start = current_end
                    continue
                
                executions = response.get('result', {}).get('list', [])
                
                if executions:
                    all_executions.extend(executions)
                    logger.debug(f"[{crypto}] Получено {len(executions)} записей за интервал")
                
                # Переходим к следующему интервалу
                current_start = current_end
            
            if not all_executions:
                logger.info(f"[{crypto}] ℹ️ Выплат фандинга за весь период не найдено")
                return 0.0
            
            # 3. Суммирование
            total_funding_pnl = 0.0
            
            for item in all_executions:
                # В Bybit execFee - это КОМИССИЯ.
                # Если execFee > 0, вы заплатили (убыток).
                # Если execFee < 0, вам начислили (прибыль).
                # Для PnL нам нужно: ( -1 * execFee )
                fee = float(item.get('execFee', 0.0))
                funding_pnl = -fee  # Инвертируем, чтобы положительное число было прибылью
                total_funding_pnl += funding_pnl
                
                # Лог для отладки
                exec_time = datetime.fromtimestamp(int(item['execTime']) / 1000)
                logger.debug(f" 📅 {exec_time}: Fee={fee} -> PnL={funding_pnl}")
            
            logger.info(f"[{crypto}] 💰 Итоговый фандинг: {total_funding_pnl:.4f} USDT ({len(all_executions)} выплат)")
            return total_funding_pnl
            
        except Exception as e:
            logger.error(f"[{crypto}] ❌ Критическая ошибка расчета фандинга: {e}")
            return 0.0
