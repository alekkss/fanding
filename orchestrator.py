# -*- coding: utf-8 -*-
"""Оркестратор с поддержкой множественных позиций и работой с БД"""

import logging
import time
import threading
from typing import Set

from managers.position_manager import MultiPositionManager
from managers.blacklist_manager import BlacklistManager
from services.price_service import PriceFetcher
from services.spread_analyzer import SpreadAnalyzer
from services.funding_rate_service import FundingRateFetcher
from services.arbitrage_calculator import ArbitrageCalculator
from services.opportunity_monitor import OpportunityMonitor
from utils.logger_config import setup_logging
from config import (
    MIN_SPREAD_PCT, MAX_CONCURRENT_POSITIONS,
    MAX_TRADING_THREADS, SCAN_INTERVAL_SEC
)

# Новые импорты для работы с БД
from database.database import check_db_connection
from database.repositories.position_repository import PositionRepository
from database.repositories.history_repository import HistoryRepository
from database.repositories.blacklist_repository import BlacklistRepository

# 🆕 Импорт Telegram интеграции
from integration.telegram_integration import initialize_telegram_integration

logger = setup_logging()


class MultiCryptoOrchestrator:
    """
    Оркестратор для торговли несколькими криптовалютами одновременно.
    Обновленная версия с использованием Repository Pattern и БД.
    """
    
    def __init__(self):
        """
        Инициализация оркестратора с репозиториями и менеджерами.
        Применяет Dependency Injection для всех компонентов.
        """
        logger.info("🔧 Инициализация оркестратора...")
        
        # Проверка подключения к БД
        if not check_db_connection():
            logger.error("❌ Не удалось подключиться к базе данных!")
            logger.error("💡 Убедитесь что БД инициализирована: alembic upgrade head")
            raise RuntimeError("Database connection failed")
        
        logger.info("✅ Подключение к БД успешно")
        
        # Создаем репозитории (слой доступа к данным)
        self.position_repo = PositionRepository()
        self.history_repo = HistoryRepository()
        self.blacklist_repo = BlacklistRepository()
        
        # Создаем менеджеры с Dependency Injection
        self.position_manager = MultiPositionManager(
            position_repo=self.position_repo,
            history_repo=self.history_repo
        )
        
        self.blacklist_manager = BlacklistManager(
            blacklist_repo=self.blacklist_repo
        )
        
        # 🆕 Инициализация Telegram интеграции
        try:
            self.telegram = initialize_telegram_integration(
                position_repo=self.position_repo,
                history_repo=self.history_repo,
                blacklist_repo=self.blacklist_repo
            )
            logger.info("✅ Telegram интеграция инициализирована")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось инициализировать Telegram: {e}")
            self.telegram = None
        
        # Управление потоками
        self.active_threads: Set[str] = set()
        self.lock = threading.Lock()
        self.shutdown_event = threading.Event()
        
        logger.info("✅ Оркестратор инициализирован")
    
    def monitor_position(self, crypto: str) -> None:
        """
        Мониторит открытую позицию в отдельном потоке.
        
        Args:
            crypto: Символ криптовалюты
        """
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
        """
        Пытается открыть позицию для криптовалюты.
        
        Args:
            crypto: Символ криптовалюты
            opportunity_data: Данные о возможности арбитража
            
        Returns:
            bool: True если позиция открыта успешно
        """
        try:
            logger.info(f"[{crypto}] 🎯 Попытка открыть позицию")
            
            success = OpportunityMonitor.monitor_and_execute(
                crypto, opportunity_data, self.position_manager
            )
            
            if success:
                logger.info(f"[{crypto}] ✅ Позиция успешно открыта")
                
                # Запускаем поток мониторинга
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
            with self.lock:
                self.active_threads.discard(f"open_{crypto}")
    
    def restore_monitoring(self) -> None:
        """
        Восстанавливает мониторинг для существующих позиций.
        Вызывается при старте программы.
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
            logger.info(
                f"[{crypto}] Вход: Спот={position['spot_entry_price']:.6f}, "
                f"Фьюч={position['futures_entry_price']:.6f}"
            )
            logger.info(
                f"[{crypto}] Qty: Спот={position['spot_qty']:.4f}, "
                f"Фьюч={position['futures_qty']:.4f}"
            )
            
            # Добавляем в активные потоки
            with self.lock:
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
        """Сканирует рынок на возможности и открывает позиции."""
        try:
            open_positions = self.position_manager.get_open_cryptos()
            open_count = len(open_positions)
            logger.info(f"📊 Открытых позиций: {open_count}/{MAX_CONCURRENT_POSITIONS}")
            
            if open_count >= MAX_CONCURRENT_POSITIONS:
                logger.info(
                    f"⏸️ Достигнут лимит позиций ({MAX_CONCURRENT_POSITIONS}), "
                    f"ждем закрытия"
                )
                return
            
            # Получаем все символы
            symbols = PriceFetcher.get_all_symbols()
            if not symbols:
                logger.error("Не удалось получить символы")
                return
            
            # Фильтруем blacklist
            blacklisted = self.blacklist_manager.get_blacklist()
            symbols_before = len(symbols)
            symbols = [s for s in symbols if s not in blacklisted]
            
            if blacklisted:
                filtered_count = symbols_before - len(symbols)
                if filtered_count > 0:
                    logger.info(
                        f"🚫 Исключено из blacklist: {filtered_count} пар "
                        f"({', '.join(sorted(blacklisted))})"
                    )
            
            # Исключаем пары с открытыми позициями
            available_symbols = [s for s in symbols if s not in open_positions]
            logger.info(f"📈 Доступно для торговли: {len(available_symbols)} пар")
            
            if not available_symbols:
                logger.info("Все доступные пары уже в торговле или в blacklist")
                return
            
            # Получаем orderbook
            orderbooks = PriceFetcher.get_orderbook_batch(available_symbols)
            if not orderbooks:
                logger.error("Не удалось получить orderbook")
                return
            
            # Фильтруем по спреду
            filtered_pairs = SpreadAnalyzer.filter_and_display(orderbooks)
            if not filtered_pairs:
                logger.info(f"Нет пар с спредом >= {MIN_SPREAD_PCT}%")
                return
            
            # Получаем funding rates
            crypto_list = [p['crypto'] for p in filtered_pairs]
            funding_rates = FundingRateFetcher.get_batch_funding_rates(crypto_list)
            
            # Находим возможности
            opportunities = ArbitrageCalculator.find_top_opportunities(
                filtered_pairs, funding_rates,
                limit=MAX_CONCURRENT_POSITIONS - open_count
            )
            
            if not opportunities:
                logger.info("Нет прибыльных возможностей")
                return
            
            # Пытаемся открыть позиции
            for opp in opportunities:
                crypto = opp['crypto']
                
                # Дополнительная проверка blacklist
                if self.blacklist_manager.is_blacklisted(crypto):
                    logger.warning(f"[{crypto}] 🚫 В blacklist, пропускаем")
                    continue
                
                with self.lock:
                    # Проверяем открытые позиции
                    if self.position_manager.has_position(crypto):
                        logger.debug(f"[{crypto}] Позиция уже открыта, пропускаем")
                        continue
                    
                    # Проверяем активные потоки открытия
                    if f"open_{crypto}" in self.active_threads:
                        logger.warning(
                            f"[{crypto}] ⚠️ Уже запущен поток открытия, пропускаем"
                        )
                        continue
                    
                    # Проверяем лимит позиций
                    if self.position_manager.get_positions_count() >= MAX_CONCURRENT_POSITIONS:
                        logger.info("Достигнут лимит позиций, прерываем цикл")
                        break
                    
                    # Добавляем в активные потоки
                    self.active_threads.add(f"open_{crypto}")
                    logger.debug(f"[{crypto}] Добавлен в активные потоки открытия")
                
                # Запускаем поток открытия позиции
                open_thread = threading.Thread(
                    target=self.try_open_position,
                    args=(crypto, opp),
                    name=f"Open-{crypto}",
                    daemon=True
                )
                open_thread.start()
                logger.info(f"[{crypto}] 🚀 Запущен поток открытия позиции")
                
                time.sleep(2)  # Задержка между запуском потоков
                
        except Exception as e:
            logger.error(f"❌ Ошибка сканирования: {e}", exc_info=True)
    
    def run(self) -> None:
        """Главный цикл оркестратора."""
        logger.info("=" * 60)
        logger.info("🚀 START MULTI-CRYPTO ARBITRAGE TRADER v4.0 (DB Edition)")
        logger.info(f"📊 Макс. одновременных позиций: {MAX_CONCURRENT_POSITIONS}")
        logger.info(f"⏱️ Интервал сканирования: {SCAN_INTERVAL_SEC}s")
        logger.info(f"💾 База данных: SQLite (arbitrage.db)")
        logger.info("=" * 60)
        
        # 🆕 Запуск Telegram бота
        if self.telegram:
            if self.telegram.start():
                logger.info("✅ Telegram бот запущен")
            else:
                logger.warning("⚠️ Не удалось запустить Telegram бота")
        
        # Восстанавливаем мониторинг существующих позиций
        self.restore_monitoring()
        
        try:
            while not self.shutdown_event.is_set():
                try:
                    self.scan_opportunities()
                    logger.info(
                        f"⏸️ Ожидание {SCAN_INTERVAL_SEC}s до следующего сканирования..."
                    )
                    time.sleep(SCAN_INTERVAL_SEC)
                    
                except KeyboardInterrupt:
                    logger.info("👋 Получен сигнал остановки (Ctrl+C)")
                    self.shutdown()
                    break
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка в главном цикле: {e}", exc_info=True)
                    time.sleep(30)
        finally:
            logger.info("🛑 Оркестратор остановлен")
    
    def shutdown(self) -> None:
        """Корректная остановка всех потоков."""
        logger.info("🛑 Инициирована остановка...")
        self.shutdown_event.set()
        
        # 🆕 Остановка Telegram бота
        if self.telegram:
            self.telegram.stop()
            logger.info("✅ Telegram бот остановлен")
        
        # Ждем завершения активных потоков
        for i in range(30):
            with self.lock:
                active_count = len(self.active_threads)
            if active_count == 0:
                break
            logger.info(f"⏳ Ожидание завершения {active_count} потоков...")
            time.sleep(1)
        
        logger.info("✅ Все потоки завершены")


def main():
    """Точка входа приложения."""
    orchestrator = MultiCryptoOrchestrator()
    orchestrator.run()


if __name__ == "__main__":
    main()
