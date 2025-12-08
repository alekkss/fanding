# -*- coding: utf-8 -*-

"""Управление множественных позиций: сохранение, загрузка, очистка"""

import os
import json
import logging
import threading
from datetime import datetime
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)


class MultiPositionManager:
    """Менеджер для управления несколькими позициями одновременно"""
    
    def __init__(self, positions_dir: str = "positions"):
        self.positions_dir = positions_dir
        self.positions: Dict[str, dict] = {}
        
        # ✅ ИСПРАВЛЕНИЕ: RLock вместо Lock
        self.lock = threading.RLock()  # <-- ИЗМЕНЕНО!
        
        os.makedirs(self.positions_dir, exist_ok=True)
        self.load_all_positions()
    
    def load_all_positions(self) -> None:
        """Загружает все позиции из директории"""
        try:
            if not os.path.exists(self.positions_dir):
                return
            
            for filename in os.listdir(self.positions_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(self.positions_dir, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            position = json.load(f)
                            crypto = position.get('crypto')
                            if crypto:
                                self.positions[crypto] = position
                                logger.info(f"[LOAD] Позиция загружена: {crypto}")
                    except Exception as e:
                        logger.error(f"Ошибка загрузки {filename}: {e}")
            
            if self.positions:
                logger.info(f"✅ Загружено позиций: {len(self.positions)}")
        except Exception as e:
            logger.error(f"Ошибка загрузки позиций: {e}")
    
    def save_position(self, crypto: str, spot_price: float, futures_price: float,
                  spot_qty: float, futures_qty: float, spread_pct: float,
                  add_buys: List[float] = None) -> bool:
        """Сохраняет позицию для конкретной криптовалюты"""
        if add_buys is None:
            add_buys = []
        
        with self.lock:
            # Сохраняем существующие данные о фандинге если позиция уже существует
            existing_position = self.positions.get(crypto, {})
            
            position = {
                "crypto": crypto,
                "spot_entry_price": spot_price,
                "futures_entry_price": futures_price,
                "spot_qty": spot_qty,
                "futures_qty": futures_qty,
                "entry_spread_pct": spread_pct,
                "addition_buy_spreads": add_buys,
                "entry_timestamp": existing_position.get("entry_timestamp", datetime.now().isoformat()),
                "target_close_spread_pct": 0.15,
                # НОВОЕ: отслеживание фандинга
                "funding_payments_count": existing_position.get("funding_payments_count", 0),
                "last_funding_check_time": existing_position.get("last_funding_check_time", datetime.now().isoformat()),
                "low_fr_count": existing_position.get("low_fr_count", 0),  # Счетчик раундов с FR <= 0.005%
                "consecutive_low_fr": existing_position.get("consecutive_low_fr", False)  # Флаг 2 подряд
            }
            
            self.positions[crypto] = position
            filename = f"{crypto}.json"
            filepath = os.path.join(self.positions_dir, filename)
            
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(position, f, indent=2, ensure_ascii=False)
                logger.info(f"[SAVE] Позиция сохранена: {crypto}")
                return True
            except Exception as e:
                logger.error(f"Ошибка сохранения позиции {crypto}: {e}")
                return False
    
    def increment_funding_count(self, crypto: str, current_fr: float) -> bool:
        """
        Увеличивает счетчик выплат фандинга и отслеживает низкий FR
        
        Args:
            crypto: символ криптовалюты
            current_fr: текущий funding rate
        
        Returns:
            bool: True если обновление успешно
        """
        from config import LOW_FR_TRACKING_THRESHOLD, MIN_FUNDING_PAYMENTS_FOR_CLOSE
        
        with self.lock:
            if crypto not in self.positions:
                return False
            
            position = self.positions[crypto]
            position['funding_payments_count'] = position.get('funding_payments_count', 0) + 1
            position['last_funding_check_time'] = datetime.now().isoformat()
            
            # Отслеживаем низкий FR
            if current_fr <= LOW_FR_TRACKING_THRESHOLD:
                position['low_fr_count'] = position.get('low_fr_count', 0) + 1
                logger.info(f"[{crypto}] 📉 FR {current_fr:.4f}% <= {LOW_FR_TRACKING_THRESHOLD}%, счетчик низкого FR: {position['low_fr_count']}")
            else:
                # FR поднялся выше порога - сбрасываем счетчик
                position['low_fr_count'] = 0
                logger.info(f"[{crypto}] 📈 FR {current_fr:.4f}% > {LOW_FR_TRACKING_THRESHOLD}%, счетчик низкого FR сброшен")
            
            # Проверяем достигли ли 2 раундов подряд с низким FR
            if position['low_fr_count'] >= MIN_FUNDING_PAYMENTS_FOR_CLOSE:
                position['consecutive_low_fr'] = True
                logger.info(f"[{crypto}] ✅ FR был <= {LOW_FR_TRACKING_THRESHOLD}% в течение {position['low_fr_count']} раундов - активированы мягкие условия закрытия")
            
            # Сохраняем обновленную позицию
            return self._update_position_file(crypto, position)
    
    def _update_position_file(self, crypto: str, position: dict) -> bool:
        """Обновляет файл позиции"""
        filename = f"{crypto}.json"
        filepath = os.path.join(self.positions_dir, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(position, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления позиции {crypto}: {e}")
            return False
    
    def get_position(self, crypto: str) -> Optional[dict]:
        """Получает позицию для конкретной криптовалюты"""
        with self.lock:
            return self.positions.get(crypto)
    
    def has_position(self, crypto: str) -> bool:
        """Проверяет есть ли открытая позиция для криптовалюты"""
        with self.lock:
            return crypto in self.positions
    
    def get_all_positions(self) -> Dict[str, dict]:
        """Возвращает все открытые позиции"""
        with self.lock:
            return self.positions.copy()
    
    def get_open_cryptos(self) -> List[str]:
        """Возвращает список криптовалют с открытыми позициями"""
        with self.lock:
            return list(self.positions.keys())
    
    def clear_position(self, crypto: str) -> bool:
        """Удаляет позицию для конкретной криптовалюты"""
        with self.lock:
            if crypto in self.positions:
                del self.positions[crypto]
            
            filename = f"{crypto}.json"
            filepath = os.path.join(self.positions_dir, filename)
            
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                logger.info(f"[CLEAR] Позиция очищена: {crypto}")
                return True
            except Exception as e:
                logger.error(f"Ошибка очистки позиции {crypto}: {e}")
                return False
    
    def update_quantities(self, crypto: str, additional_spot_qty: float, 
                         additional_futures_qty: float) -> bool:
        """Обновляет количество монет после докупки"""
        with self.lock:
            if crypto not in self.positions:
                logger.error(f"Позиция {crypto} не найдена для обновления")
                return False
            
            position = self.positions[crypto]
            position['spot_qty'] += additional_spot_qty
            position['futures_qty'] += additional_futures_qty
            
            # ✅ ТЕПЕРЬ БЕЗОПАСНО: RLock позволяет повторный захват
            return self.save_position(
                crypto=crypto,
                spot_price=position['spot_entry_price'],
                futures_price=position['futures_entry_price'],
                spot_qty=position['spot_qty'],
                futures_qty=position['futures_qty'],
                spread_pct=position['entry_spread_pct'],
                add_buys=position.get('addition_buy_spreads', [])
            )
    
    def add_additional_buy(self, crypto: str, spread_level: float) -> bool:
        """Добавляет уровень докупки"""
        with self.lock:
            if crypto not in self.positions:
                return False
            
            position = self.positions[crypto]
            
            if "addition_buy_spreads" not in position:
                position["addition_buy_spreads"] = []
            
            if spread_level not in position["addition_buy_spreads"]:
                position["addition_buy_spreads"].append(spread_level)
                
                # ✅ ТЕПЕРЬ БЕЗОПАСНО: RLock позволяет повторный захват
                return self.save_position(
                    crypto=crypto,
                    spot_price=position['spot_entry_price'],
                    futures_price=position['futures_entry_price'],
                    spot_qty=position['spot_qty'],
                    futures_qty=position['futures_qty'],
                    spread_pct=position['entry_spread_pct'],
                    add_buys=position["addition_buy_spreads"]
                )
            
            return True
    
    def get_positions_count(self) -> int:
        """Возвращает количество открытых позиций"""
        with self.lock:
            return len(self.positions)
    
    def close_position_with_pnl(
        self,
        crypto: str,
        close_spot_price: float,
        close_futures_price: float
    ) -> Optional[dict]:
        """
        Закрывает позицию, считает PnL и сохраняет в историю.
        Использует PnLCalculator для расчетов.
        """
        with self.lock:
            if crypto not in self.positions:
                logger.error(f"Позиция {crypto} не найдена для закрытия")
                return None

            position = self.positions[crypto]
            
            # 1. Импорты внутри метода (чтобы избежать циклических зависимостей)
            from pnl_calculator import PnLCalculator
            from config import COMMISSION_PCT
            
            # 2. Подготовка данных
            avg_entry_price = (position["spot_entry_price"] + position["futures_entry_price"]) / 2
            avg_exit_price = (close_spot_price + close_futures_price) / 2
            
            # Размер позиции в USDT (среднее)
            position_size = (
                (position["spot_qty"] * position["spot_entry_price"]) + 
                (position["futures_qty"] * position["futures_entry_price"])
            ) / 2

            # Комиссия: 0.2% -> 0.002
            commission_rate = COMMISSION_PCT / 100.0
            
            # Накопленный фандинг (если он есть в данных позиции, иначе 0)
            # В твоем коде я не вижу поля total_funding, но возможно оно там появится
            # или мы можем передать 0, если пока не считаем накопление
            total_funding = position.get("total_funding", 0.0)

            # 3. Вызов калькулятора (stateless)
            pnl_result = PnLCalculator.calculate_pnl(
                entry_price=avg_entry_price,
                exit_price=avg_exit_price,
                position_size=position_size,
                commission_rate=commission_rate,
                total_funding_received=total_funding
            )

            # 4. Формирование записи для истории
            closed_position = {
                "crypto": crypto,
                "entry_time": position.get("entry_timestamp"),
                "close_time": datetime.now().isoformat(),
                "spot_entry_price": position["spot_entry_price"],
                "futures_entry_price": position["futures_entry_price"],
                "spot_close_price": close_spot_price,
                "futures_close_price": close_futures_price,
                "spot_qty": position["spot_qty"],
                "futures_qty": position["futures_qty"],
                "position_size_usdt": position_size,
                "entry_spread_pct": position.get("entry_spread_pct", 0),
                # Считаем спред выхода для статистики
                "close_spread_pct": (close_futures_price - close_spot_price) / close_spot_price * 100,
                "pnl": pnl_result
            }

            # 5. Сохранение и очистка
            self._save_closed_position(closed_position)
            
            logger.info(
                f"💰 Закрыта позиция {crypto}. "
                f"Net PnL: {pnl_result['net_pnl']} USDT "
                f"(Price: {pnl_result['price_pnl']}, Funding: {pnl_result['funding']})"
            )

            # Удаляем открытую позицию (и файл json)
            self.clear_position(crypto)

            return pnl_result

    def _save_closed_position(self, closed_position: dict) -> None:
        """Сохраняет закрытую позицию в общий файл истории (append)"""
        history_file = os.path.join(self.positions_dir, "closed_positions_history.json")
        try:
            history = []
            if os.path.exists(history_file):
                with open(history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
            
            history.append(closed_position)
            
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"Ошибка сохранения истории позиций: {e}")
