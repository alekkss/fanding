# -*- coding: utf-8 -*-

"""Мониторинг и исполнение торговых сигналов для множественных позиций"""

import time
import logging
from typing import Union
from datetime import datetime

from price_service import PriceFetcher
from funding_rate_service import FundingRateFetcher
from arbitrage_calculator import ArbitrageCalculator
from leverage_manager import LeverageManager
from order_executor import OrderExecutor
from blacklist_manager import blacklist_manager
from balance import get_coin_balance
from config import (
    MIN_FUNDING_RATE, MIN_PROFIT_PCT, COMMISSION_PCT, 
    MIN_ENTRY_SPREAD_PCT, CLOSE_FR_THRESHOLD, 
    MONITOR_INTERVAL_SEC, MAX_CLOSE_SPREAD_PCT
)

logger = logging.getLogger(__name__)


class OpportunityMonitor:
    
    @staticmethod
    def monitor_open_position_single(position: dict, crypto: str, position_manager) -> bool:
        """
        Мониторит одну открытую позицию (для многопоточного режима)
        Закрывает позицию когда FR < -0.001% И спред закрытия <= 0.5%
        
        Args:
            position: dict с данными позиции
            crypto: символ криптовалюты
            position_manager: экземпляр MultiPositionManager
        
        Returns:
            bool: True если позиция закрыта, False если мониторинг продолжается
        """
        from config import CLOSE_FR_THRESHOLD, MONITOR_INTERVAL_SEC, MAX_CLOSE_SPREAD_PCT
        
        entry_spread = position['entry_spread_pct']
        entry_spot_price = position['spot_entry_price']
        entry_futures_price = position['futures_entry_price']
        
        logger.info(f"[{crypto}] 🔍 Мониторинг закрытия...")
        logger.info(f"[{crypto}] └─ Входные цены: Спот={entry_spot_price:.6f}, Фьюч={entry_futures_price:.6f}")
        logger.info(f"[{crypto}] └─ Входной спред: {entry_spread:.4f}%")
        
        # Пауза 10 секунд после открытия позиции перед первой проверкой
        logger.info(f"[{crypto}] ⏸️ Пауза 10 секунд после открытия позиции...")
        time.sleep(10)
        
        attempts = 0
        max_attempts = 1000
        
        while attempts < max_attempts:
            attempts += 1
            
            # Проверяем что позиция еще существует
            current_position = position_manager.get_position(crypto)
            if not current_position:
                logger.warning(f"[{crypto}] Позиция исчезла, завершаем мониторинг")
                return False
            
            # Получаем текущий funding rate
            funding_rate = FundingRateFetcher.get_single_funding_rate(crypto)
            
            if funding_rate is None:
                logger.warning(f"[{crypto}] Не удалось получить FR, повтор через 60 сек")
                time.sleep(60)
                continue
            
            # Получаем orderbook для расчета спреда закрытия
            spot_ob = PriceFetcher.get_orderbook(crypto, "spot")
            fut_ob = PriceFetcher.get_orderbook(crypto, "linear")
            
            if not spot_ob or not fut_ob:
                logger.warning(f"[{crypto}] Не удалось получить orderbook, повтор через 60 сек")
                time.sleep(60)
                continue
            
            spot_bid = spot_ob.get('bid')
            fut_ask = fut_ob.get('ask')
            
            if not spot_bid or not fut_ask:
                logger.warning(f"[{crypto}] Нет BID/ASK, повтор через 60 сек")
                time.sleep(60)
                continue
            
            # Спред для ЗАКРЫТИЯ позиции (fut_ask - spot_bid)
            current_close_spread = (fut_ask - spot_bid) / spot_bid * 100
            
            logger.info(f"[{crypto}] [{attempts}/{max_attempts}] FR: {funding_rate:.4f}%, "
                    f"Спред закрытия: {current_close_spread:.4f}%")
            logger.info(f"[{crypto}] └─ Условия: FR < {CLOSE_FR_THRESHOLD}% И Спред <= {MAX_CLOSE_SPREAD_PCT}%")
            

            # Условие закрытия: FR < -0.001% И спред закрытия <= 0.5%
            if funding_rate < CLOSE_FR_THRESHOLD and current_close_spread <= MAX_CLOSE_SPREAD_PCT:
                logger.info(f"[{crypto}] 🔥 Условия закрытия выполнены:")
                logger.info(f"[{crypto}] └─ FR {funding_rate:.4f}% < {CLOSE_FR_THRESHOLD}% ✅")
                logger.info(f"[{crypto}] └─ Спред {current_close_spread:.4f}% <= {MAX_CLOSE_SPREAD_PCT}% ✅")
                
                # Обновляем позицию из менеджера
                fresh_position = position_manager.get_position(crypto)
                if not fresh_position:
                    logger.error(f"[{crypto}] Позиция исчезла перед закрытием")
                    return False
                
                # Закрываем позицию
                success = PositionCloser.close_position(fresh_position, crypto, position_manager)
                if success:
                    # Цены и спред для PnL: используем те же, что для закрытия
                    spot_close = spot_bid          # BID на споте
                    futures_close = fut_ask        # ASK на фьюче
                    spread_abs = futures_close - spot_close

                    pnl_result = position_manager.close_position_with_pnl(
                        crypto=crypto,
                        close_spot_price=spot_close,
                        close_futures_price=futures_close,
                        spread=spread_abs
                    )

                    logger.info(f"[{crypto}] ✅ Позиция закрыта, PnL: {pnl_result}")
                    return True
                else:
                    logger.error(f"[{crypto}] Ошибка закрытия позиции, повтор через 5 минут")
                    time.sleep(MONITOR_INTERVAL_SEC)
            else:
                # Логируем какое условие не выполнено
                if funding_rate >= CLOSE_FR_THRESHOLD:
                    logger.debug(f"[{crypto}] FR {funding_rate:.4f}% >= {CLOSE_FR_THRESHOLD}%, ждем снижения FR")
                if current_close_spread > MAX_CLOSE_SPREAD_PCT:
                    logger.debug(f"[{crypto}] Спред {current_close_spread:.4f}% > {MAX_CLOSE_SPREAD_PCT}%, ждем сужения спреда")
                
                time.sleep(MONITOR_INTERVAL_SEC)  # 300 секунд = 5 минут
        
        logger.warning(f"[{crypto}] ⏱️ Время мониторинга истекло ({max_attempts} попыток)")
        return False
    
    @staticmethod
    def monitor_and_execute(crypto: str, initial_data: dict, position_manager) -> bool:
        """
        Мониторит возможность и открывает позицию
        Условия открытия:
        1. spread_pct >= 0.0%
        2. funding_rate >= 0.01%
        """
        from blacklist_manager import blacklist_manager

        # Проверка blacklist в начале
        if blacklist_manager.is_blacklisted(crypto):
            details = blacklist_manager.get_blacklist_details(crypto)
            logger.warning(f"[{crypto}] 🚫 В blacklist, пропускаем")
            if details:
                logger.warning(f"[{crypto}]    Причина: {details.get('reason')}")
                logger.warning(f"[{crypto}]    Дата: {details.get('timestamp')}")
            return False

        logger.info(f"[{crypto}] 🔍 Мониторинг и исполнение сделки...")

        max_attempts = 100
        attempts = 0

        while attempts < max_attempts:
            attempts += 1

            # Проверяем что позиция еще не открыта
            if position_manager.has_position(crypto):
                logger.warning(f"[{crypto}] Позиция уже открыта, пропускаем")
                return False

            spot_orderbook = PriceFetcher.get_orderbook(crypto, "spot")
            futures_orderbook = PriceFetcher.get_orderbook(crypto, "linear")

            if not spot_orderbook or not futures_orderbook:
                logger.warning(f"[{crypto}] Нет данных orderbook, попытка {attempts}")
                time.sleep(5)
                continue

            spot_ask = spot_orderbook.get("ask")
            futures_bid = futures_orderbook.get("bid")

            if not spot_ask or not futures_bid:
                logger.warning(f"[{crypto}] Нет bid/ask, попытка {attempts}")
                time.sleep(5)
                continue

            spread = futures_bid - spot_ask
            spread_pct = (spread / spot_ask) * 100 if spot_ask > 0 else 0.0

            # Текущая ставка фандинга (процент за период, как отдает биржа)
            funding_rate = FundingRateFetcher.get_single_funding_rate(crypto)

            # Чистая прибыль для информации (в процентах)
            net_profit = spread_pct + funding_rate - COMMISSION_PCT

            logger.info(
                f"[{crypto}] [{attempts}/{max_attempts}] ASK {spot_ask:.6f} | BID {futures_bid:.6f} | "
                f"Спред {spread_pct:.4f}% | FR {funding_rate:.4f}% | Net Profit {net_profit:.4f}%"
            )

            # ПРОВЕРКА 1: FR должен быть положительным
            if funding_rate < MIN_FUNDING_RATE:
                logger.debug(f"[{crypto}] FR {funding_rate:.4f}% < {MIN_FUNDING_RATE}%, ждем...")
                time.sleep(5)
                continue

            # ПРОВЕРКА 2: Спред должен быть >= минимального
            if spread_pct >= MIN_ENTRY_SPREAD_PCT:
                logger.info(f"[{crypto}] 🎯 Условие выполнено!")
                logger.info(f"[{crypto}]    ✅ Спред: {spread_pct:.4f}% >= {MIN_ENTRY_SPREAD_PCT}%")
                logger.info(f"[{crypto}]    ✅ FR: {funding_rate:.4f}% >= {MIN_FUNDING_RATE}%")
                logger.info(f"[{crypto}]    💰 Net Profit (с учетом комиссий): {net_profit:.4f}%")

                # Устанавливаем плечо
                if not LeverageManager.check_and_set_leverage(crypto):
                    logger.error(f"[{crypto}] Не удалось установить плечо")
                    return False

                # Рассчитываем размер позиции
                actual_trade_amount = OrderExecutor.calculate_futures_amount(
                    crypto, futures_bid, OrderExecutor.TRADE_AMOUNT_USD
                )

                # Баланс до покупки
                balance_before = get_coin_balance(crypto)
                logger.info(f"[{crypto}] Баланс до покупки: {balance_before}")

                # Размещаем ордера
                spot_result = OrderExecutor.place_spot_order(crypto, "Buy", actual_trade_amount)
                futures_result = OrderExecutor.place_futures_order(
                    crypto, "Sell", futures_bid, actual_trade_amount
                )

                # Оба ордера успешны
                if spot_result["success"] and futures_result["success"]:
                    logger.info(f"[{crypto}] ✅ Оба ордера успешно исполнены")
                    logger.info(f"[{crypto}]    Спот OrderID: {spot_result['order_id']}")
                    logger.info(
                        f"[{crypto}]    Фьючерс OrderID: {futures_result['order_id']} "
                        f"qty={futures_result['qty']}"
                    )

                    time.sleep(1)

                    # Баланс после покупки
                    balance_after = get_coin_balance(crypto)
                    logger.info(f"[{crypto}] Баланс после покупки: {balance_after}")

                    purchased_qty = balance_after - balance_before
                    logger.info(f"[{crypto}] Куплено: {purchased_qty}")

                    futures_qty = futures_result["qty"]

                    # Сохраняем позицию
                    position_manager.save_position(
                        crypto=crypto,
                        spot_price=spot_ask,
                        futures_price=futures_bid,
                        spot_qty=purchased_qty,
                        futures_qty=futures_qty,
                        spread_pct=spread_pct,
                        add_buys=[],
                    )

                    # === СОХРАНЯЕМ СТАВКУ ФАНДИНГА В ПОЗИЦИЮ ===
                    position = position_manager.get_position(crypto)
                    if position is not None:
                        position["avg_funding_rate"] = funding_rate  # % за 8 часов
                        position_manager._save_raw_position(position)

                    logger.info(f"[{crypto}] ✅ Позиция открыта")
                    return True

                # Ошибка открытия позиции + blacklist
                else:
                    logger.error(
                        f"[{crypto}] ❌ КРИТИЧЕСКАЯ ОШИБКА: Не удалось открыть позицию"
                    )
                    logger.error(
                        f"[{crypto}]    Спот: "
                        f"{'SUCCESS' if spot_result['success'] else 'FAILED - ' + spot_result['error']}"
                    )
                    logger.error(
                        f"[{crypto}]    Фьючерс: "
                        f"{'SUCCESS' if futures_result['success'] else 'FAILED - ' + futures_result['error']}"
                    )

                    should_blacklist = False
                    blacklist_reason = None
                    error_code = None

                    # Ошибка спота
                    if not spot_result["success"] and spot_result.get("error"):
                        error_str = spot_result["error"]
                        if "Code" in error_str:
                            try:
                                code_part = (
                                    error_str.split("Code")[1].split(":")[0].strip()
                                )
                                error_code = int(code_part)
                                if blacklist_manager.should_blacklist_error(error_code):
                                    should_blacklist = True
                                    blacklist_reason = f"Spot error: {error_str}"
                            except (ValueError, IndexError):
                                pass

                    # Ошибка фьючерса
                    if not futures_result["success"] and futures_result.get("error"):
                        error_str = futures_result["error"]
                        if "Code" in error_str:
                            try:
                                code_part = (
                                    error_str.split("Code")[1].split(":")[0].strip()
                                )
                                error_code = int(code_part)
                                if blacklist_manager.should_blacklist_error(error_code):
                                    should_blacklist = True
                                    blacklist_reason = f"Futures error: {error_str}"
                            except (ValueError, IndexError):
                                pass

                    # Добавляем в blacklist при критической ошибке
                    if should_blacklist:
                        blacklist_manager.add_to_blacklist(
                            crypto=crypto,
                            reason=blacklist_reason,
                            error_code=error_code,
                        )
                        logger.warning(
                            f"[{crypto}] 🚫 Добавлен в blacklist, больше не будет торговаться"
                        )

                    # Незахеджированные позиции
                    if spot_result["success"] and not futures_result["success"]:
                        logger.critical(
                            f"[{crypto}] ⚠️⚠️⚠️ Спот куплен, фьючерс НЕ продан! Незахеджированная позиция!"
                        )
                    elif not spot_result["success"] and futures_result["success"]:
                        logger.critical(
                            f"[{crypto}] ⚠️⚠️⚠️ Фьючерс продан, спот НЕ куплен! Незахеджированная позиция!"
                        )

                    return False

            # Спред недостаточный, ждем
            logger.debug(
                f"[{crypto}] Спред {spread_pct:.4f}% < {MIN_ENTRY_SPREAD_PCT}%, ждем..."
            )
            time.sleep(5)

        logger.warning(f"[{crypto}] ⏱️ Не удалось открыть позицию за {max_attempts} попыток")
        return False


class PositionCloser:
    @staticmethod
    def close_position(position: dict, crypto: str, position_manager) -> bool:
        """
        Закрывает позицию: спот по актуальному балансу, фьючерс по сохраненному qty
        
        Args:
            position: dict с данными позиции
            crypto: символ криптовалюты
            position_manager: экземпляр MultiPositionManager
        
        Returns:
            bool: True если закрытие успешно
        """
        logger.info(f"[{crypto}] 🔄 Закрытие позиции")
        
        # Получаем актуальный баланс монеты на споте
        actual_spot_balance = get_coin_balance(crypto)
        logger.info(f"[{crypto}] 💰 Актуальный баланс спот: {actual_spot_balance:.4f}")
        
        # КРИТИЧНО: Для фьючерса берем qty из сохраненной позиции!
        futures_qty = position.get('futures_qty', 0)
        logger.info(f"[{crypto}] 💰 Сохраненное qty фьючерс: {futures_qty:.4f}")
        
        if actual_spot_balance <= 0:
            logger.error(f"[{crypto}] ❌ Нулевой баланс спот, невозможно закрыть позицию")
            return False
        
        if futures_qty <= 0:
            logger.error(f"[{crypto}] ❌ Нулевое qty фьючерс в позиции, невозможно закрыть")
            return False
        
        spot_orderbook = PriceFetcher.get_orderbook(crypto, "spot")
        futures_orderbook = PriceFetcher.get_orderbook(crypto, "linear")
        
        if not spot_orderbook or not futures_orderbook:
            logger.error(f"[{crypto}] Не удалось получить цены для закрытия")
            return False
        
        spot_bid = spot_orderbook.get('bid')
        futures_ask = futures_orderbook.get('ask')
        
        logger.info(f"[{crypto}] Цены для закрытия: Спот BID={spot_bid}, Фьюч ASK={futures_ask}")
        
        # Используем actual_spot_balance для спота, futures_qty для фьючерса
        spot_result = OrderExecutor.close_spot_position_qty(crypto, actual_spot_balance)
        futures_result = OrderExecutor.close_futures_position(crypto, futures_ask, futures_qty)
        
        if spot_result["success"] and futures_result["success"]:
            logger.info(f"[{crypto}] ✅ Позиция полностью закрыта")
            logger.info(f"[{crypto}]    Спот закрыт: OrderID {spot_result['order_id']}, qty={spot_result['qty']}")
            logger.info(f"[{crypto}]    Фьючерс закрыт: OrderID {futures_result['order_id']}, qty={futures_result['qty']}")
            
            # Дополнительная проверка
            expected_futures_qty = futures_qty
            actual_closed_qty = futures_result['qty']
            
            if abs(expected_futures_qty - actual_closed_qty) > 0.01:
                logger.warning(f"[{crypto}] ⚠️ Расхождение qty фьючерс: ожидалось {expected_futures_qty}, закрыто {actual_closed_qty}")
            
            return True
        else:
            logger.error(f"[{crypto}] ❌ Ошибка закрытия позиции")
            logger.error(f"[{crypto}]    Спот: {'SUCCESS' if spot_result['success'] else 'FAILED - ' + spot_result['error']}")
            logger.error(f"[{crypto}]    Фьючерс: {'SUCCESS' if futures_result['success'] else 'FAILED - ' + futures_result['error']}")
            
            if spot_result["success"] and not futures_result["success"]:
                logger.critical(f"[{crypto}] ⚠️⚠️⚠️ Спот продан, фьючерс НЕ закрыт!")
                logger.critical(f"[{crypto}]    Необходимо вручную закрыть {futures_qty} {crypto} на фьючерсе!")
            elif not spot_result["success"] and futures_result["success"]:
                logger.critical(f"[{crypto}] ⚠️⚠️⚠️ Фьючерс закрыт, спот НЕ продан!")
                logger.critical(f"[{crypto}]    Необходимо вручную продать {actual_spot_balance} {crypto} на споте!")
            
            return False
