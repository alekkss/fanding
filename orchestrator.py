# -*- coding: utf-8 -*-

"""Оркестратор с поддержкой множественных позиций"""

import logging
import time
import threading
from typing import Set

from position_manager import MultiPositionManager
from price_service import PriceFetcher
from spread_analyzer import SpreadAnalyzer
from funding_rate_service import FundingRateFetcher
from arbitrage_calculator import ArbitrageCalculator
from opportunity_monitor import OpportunityMonitor
from blacklist_manager import blacklist_manager
from logger_config import setup_logging
from config import (
    MIN_SPREAD_PCT, MAX_CONCURRENT_POSITIONS,
    MAX_TRADING_THREADS, SCAN_INTERVAL_SEC
)

logger = setup_logging()

class MultiCryptoOrchestrator:
    """Оркестратор для торговли несколькими криптовалютами одновременно"""
    
    def __init__(self):
        self.position_manager = MultiPositionManager()
        self.active_threads: Set[str] = set()
        self.lock = threading.Lock()
        self.shutdown_event = threading.Event()
    
    def monitor_position(self, crypto: str) -> None:
        """Мониторит открытую позицию в отдельном потоке"""
        try:
            logger.info(f"[{crypto}] 🔍 Начат мониторинг позиции")
            
            while not self.shutdown_event.is_set():
                position = self.position_manager.get_position(crypto)
                if not position:
                    logger.warning(f"[{crypto}] Позиция исчезла, завершаем мониторинг")
                    break
                
                success = OpportunityMonitor.monitor_open_position_single(
                    position, crypto, self.position_manager
                )
                
                if success:
                    logger.info(f"[{crypto}] ✅ Позиция закрыта успешно")
                    break
                
                time.sleep(5)
                
        except Exception as e:
            logger.error(f"[{crypto}] ❌ Ошибка мониторинга: {e}")
            
        finally:
            with self.lock:
                self.active_threads.discard(crypto)
            logger.info(f"[{crypto}] 🛑 Мониторинг завершен")
    
    def try_open_position(self, crypto: str, opportunity_data: dict) -> bool:
        """Пытается открыть позицию для криптовалюты"""
        try:
            logger.info(f"[{crypto}] 🎯 Попытка открыть позицию")
            
            # ✅ НОВОЕ: Дополнительная проверка перед запуском
            if self.position_manager.has_position(crypto):
                logger.warning(f"[{crypto}] ⚠️ Позиция уже открыта (другим потоком), отмена")
                return False
            
            success = OpportunityMonitor.monitor_and_execute(
                crypto, opportunity_data, self.position_manager
            )
            
            if success:
                logger.info(f"[{crypto}] ✅ Позиция успешно открыта")
                
                # Запускаем поток мониторинга
                with self.lock:
                    # ✅ НОВОЕ: Проверяем что мониторинг еще не запущен
                    if crypto in self.active_threads:
                        logger.warning(f"[{crypto}] ⚠️ Мониторинг уже запущен, пропускаем")
                        return True
                    
                    # Добавляем ПЕРЕД запуском потока
                    self.active_threads.add(crypto)
                    logger.debug(f"[{crypto}] ➕ Добавлен в active_threads для мониторинга")
                
                monitor_thread = threading.Thread(
                    target=self.monitor_position,
                    args=(crypto,),
                    name=f"Monitor-{crypto}",
                    daemon=True
                )
                monitor_thread.start()
                return True
            else:
                logger.warning(f"[{crypto}] ⚠️ Не удалось открыть позицию")
                return False
                
        except Exception as e:
            logger.error(f"[{crypto}] ❌ Ошибка открытия позиции: {e}")
            return False
            
        finally:
            # ✅ ОБЯЗАТЕЛЬНО: Удаляем из active_threads в любом случае
            with self.lock:
                self.active_threads.discard(f"open_{crypto}")
                logger.debug(f"[{crypto}] ➖ Поток открытия завершен, удален из active_threads")
    
    def restore_monitoring(self) -> None:
        """
        Восстанавливает мониторинг для существующих позиций
        Вызывается при старте программы
        """
        open_positions = self.position_manager.get_open_cryptos()
        
        if not open_positions:
            logger.info("📍 Нет открытых позиций для восстановления")
            return
        
        logger.info(f"🔄 Восстановление мониторинга для {len(open_positions)} позиций...")
        
        for crypto in open_positions:
            position = self.position_manager.get_position(crypto)
            if not position:
                logger.warning(f"[{crypto}] Позиция в списке, но не найдена в менеджере")
                continue
            
            logger.info(f"[{crypto}] 🔄 Восстановление мониторинга...")
            logger.info(f"[{crypto}]    Вход: Спот={position['spot_entry_price']:.6f}, "
                       f"Фьюч={position['futures_entry_price']:.6f}")
            logger.info(f"[{crypto}]    Qty: Спот={position['spot_qty']:.4f}, "
                       f"Фьюч={position['futures_qty']:.4f}")
            
            # Добавляем в активные потоки
            with self.lock:
                if crypto in self.active_threads:
                    logger.warning(f"[{crypto}] ⚠️ Уже в active_threads, пропускаем")
                    continue
                self.active_threads.add(crypto)
            
            # Запускаем поток мониторинга
            monitor_thread = threading.Thread(
                target=self.monitor_position,
                args=(crypto,),
                name=f"Monitor-{crypto}",
                daemon=True
            )
            monitor_thread.start()
            logger.info(f"[{crypto}] ✅ Мониторинг восстановлен")
        
        logger.info(f"✅ Мониторинг восстановлен для {len(open_positions)} позиций")
    
    def scan_opportunities(self) -> None:
        """Сканирует рынок на возможности и открывает позиции"""
        try:
            # Получаем открытые позиции
            open_positions = self.position_manager.get_open_cryptos()
            open_count = len(open_positions)
            
            # ✅ НОВОЕ: Логируем активные потоки
            with self.lock:
                active_count = len(self.active_threads)
                if active_count > 0:
                    active_list = ", ".join(sorted(self.active_threads))
                    logger.info(f"🔄 Активные потоки ({active_count}): {active_list}")
            
            logger.info(f"📊 Открытых позиций: {open_count}/{MAX_CONCURRENT_POSITIONS}")
            
            if open_count >= MAX_CONCURRENT_POSITIONS:
                logger.info(f"⏸️ Достигнут лимит позиций ({MAX_CONCURRENT_POSITIONS}), ждем закрытия")
                return
            
            # Получение символов
            symbols = PriceFetcher.get_all_symbols()
            if not symbols:
                logger.error("Не удалось получить символы")
                return
            
            # Фильтрация blacklist
            blacklisted = blacklist_manager.get_blacklist()
            symbols_before = len(symbols)
            symbols = [s for s in symbols if s not in blacklisted]
            
            if blacklisted:
                filtered_count = symbols_before - len(symbols)
                if filtered_count > 0:
                    logger.info(f"🚫 Исключено из blacklist: {filtered_count} пар ({', '.join(sorted(blacklisted))})")
            
            # Фильтрация открытых позиций
            available_symbols = [s for s in symbols if s not in open_positions]
            logger.info(f"📈 Доступно для торговли: {len(available_symbols)} пар")
            
            if not available_symbols:
                logger.info("Все доступные пары уже в торговле или в blacklist")
                return
            
            # Получение и анализ данных
            orderbooks = PriceFetcher.get_orderbook_batch(available_symbols)
            if not orderbooks:
                logger.error("Не удалось получить orderbook")
                return
            
            filtered_pairs = SpreadAnalyzer.filter_and_display(orderbooks)
            if not filtered_pairs:
                logger.info(f"Нет пар с спредом >= {MIN_SPREAD_PCT}%")
                return
            
            crypto_list = [p['crypto'] for p in filtered_pairs]
            funding_rates = FundingRateFetcher.get_batch_funding_rates(crypto_list)
            
            opportunities = ArbitrageCalculator.find_top_opportunities(
                filtered_pairs, funding_rates,
                limit=MAX_CONCURRENT_POSITIONS - open_count
            )
            
            if not opportunities:
                logger.info("Нет прибыльных возможностей")
                return
            
            # Обработка возможностей
            for opp in opportunities:
                crypto = opp['crypto']
                
                # ✅ УЛУЧШЕННЫЕ ПРОВЕРКИ
                with self.lock:
                    # Проверка 1: blacklist
                    if blacklist_manager.is_blacklisted(crypto):
                        logger.info(f"[{crypto}] ⏭️ Пропуск: в blacklist")
                        continue
                    
                    # Проверка 2: позиция уже открыта
                    if self.position_manager.has_position(crypto):
                        logger.info(f"[{crypto}] ⏭️ Пропуск: позиция уже открыта")
                        continue
                    
                    # Проверка 3: поток открытия уже активен
                    if f"open_{crypto}" in self.active_threads:
                        logger.info(f"[{crypto}] ⏭️ Пропуск: поток открытия активен")
                        continue
                    
                    # Проверка 4: поток мониторинга уже активен
                    if crypto in self.active_threads:
                        logger.info(f"[{crypto}] ⏭️ Пропуск: поток мониторинга активен")
                        continue
                    
                    # Проверка 5: лимит позиций
                    if self.position_manager.get_positions_count() >= MAX_CONCURRENT_POSITIONS:
                        logger.info(f"⏸️ Достигнут лимит позиций при обработке {crypto}")
                        break
                    
                    # ✅ ВСЕ ПРОВЕРКИ ПРОШЛИ - добавляем в active_threads
                    self.active_threads.add(f"open_{crypto}")
                    logger.debug(f"[{crypto}] ➕ Добавлен в active_threads: open_{crypto}")
                
                # Запуск потока ВНЕ lock (чтобы не блокировать)
                open_thread = threading.Thread(
                    target=self.try_open_position,
                    args=(crypto, opp),
                    name=f"Open-{crypto}",
                    daemon=True
                )
                open_thread.start()
                logger.info(f"[{crypto}] 🚀 Запущен поток открытия позиции")
                time.sleep(1)  # Небольшая задержка между запусками
                
        except Exception as e:
            logger.error(f"❌ Ошибка сканирования: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def run(self) -> None:
        """Главный цикл оркестратора"""
        logger.info("="*60)
        logger.info("🚀 START MULTI-CRYPTO ARBITRAGE TRADER v3.1")
        logger.info(f"📊 Макс. одновременных позиций: {MAX_CONCURRENT_POSITIONS}")
        logger.info(f"⏱️  Интервал сканирования: {SCAN_INTERVAL_SEC}s")
        logger.info("="*60)
        
        # Восстанавливаем мониторинг существующих позиций
        self.restore_monitoring()
        
        try:
            while not self.shutdown_event.is_set():
                try:
                    self.scan_opportunities()
                    logger.info(f"⏸️ Ожидание {SCAN_INTERVAL_SEC}s до следующего сканирования...")
                    time.sleep(SCAN_INTERVAL_SEC)
                    
                except KeyboardInterrupt:
                    logger.info("👋 Получен сигнал остановки (Ctrl+C)")
                    self.shutdown()
                    break
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка в главном цикле: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    time.sleep(30)
                    
        finally:
            logger.info("🛑 Оркестратор остановлен")
    
    def shutdown(self) -> None:
        """Корректная остановка всех потоков"""
        logger.info("🛑 Инициирована остановка...")
        self.shutdown_event.set()
        
        # Ждем завершения всех потоков
        for i in range(30):
            with self.lock:
                active_count = len(self.active_threads)
                if active_count == 0:
                    break
                
                active_list = ", ".join(sorted(self.active_threads))
                logger.info(f"⏳ Ожидание завершения {active_count} потоков: {active_list}")
            
            time.sleep(1)
        
        with self.lock:
            if len(self.active_threads) > 0:
                logger.warning(f"⚠️ Остались активные потоки: {', '.join(self.active_threads)}")
            else:
                logger.info("✅ Все потоки завершены")

def main():
    orchestrator = MultiCryptoOrchestrator()
    orchestrator.run()

if __name__ == "__main__":
    main()
