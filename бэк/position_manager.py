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
            position = {
                "crypto": crypto,
                "spot_entry_price": spot_price,
                "futures_entry_price": futures_price,
                "spot_qty": spot_qty,
                "futures_qty": futures_qty,
                "entry_spread_pct": spread_pct,
                "addition_buy_spreads": add_buys,
                "entry_timestamp": datetime.now().isoformat(),
                "target_close_spread_pct": 0.15,
                "avg_funding_rate": 0.0,
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
    
    def add_funding(self, crypto: str, funding_amount: float) -> bool:
        """Добавляет фандинг к открытой позиции"""
        with self.lock:
            if crypto not in self.positions:
                logger.error(f"Позиция {crypto} не найдена для добавления фандинга")
                return False
            
            position = self.positions[crypto]
            
            # Инициализируем total_funding если его еще нет
            if "total_funding" not in position:
                position["total_funding"] = 0.0
            
            position["total_funding"] += funding_amount
            
            logger.info(f"Добавлен фандинг {funding_amount} USDT для {crypto}. Всего: {position['total_funding']}")
            
            # Сохраняем позицию напрямую в файл
            filename = f"{crypto}.json"
            filepath = os.path.join(self.positions_dir, filename)
            
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(position, f, indent=2, ensure_ascii=False)
                return True
            except Exception as e:
                logger.error(f"Ошибка сохранения фандинга для {crypto}: {e}")
                return False
    
    def _save_raw_position(self, position: dict) -> None:
        """Сохраняет уже сформированный dict позиции в соответствующий JSON-файл."""
        crypto = position["crypto"]
        filename = f"{crypto}.json"
        filepath = os.path.join(self.positions_dir, filename)
        with self.lock:
            self.positions[crypto] = position
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(position, f, indent=2, ensure_ascii=False)
                logger.info(f"[SAVE] Обновлена позиция: {crypto}")
            except Exception as e:
                logger.error(f"Ошибка сохранения позиции {crypto}: {e}")

    def close_position_with_pnl(
        self,
        crypto: str,
        close_spot_price: float,
        close_futures_price: float,
        spread: float
    ) -> Optional[dict]:
        """Закрывает позицию и рассчитывает PnL с учётом фандинга."""
        with self.lock:
            if crypto not in self.positions:
                logger.error(f"Позиция {crypto} не найдена для закрытия")
                return None

            position = self.positions[crypto]

            from pnl_calculator import PnLCalculator
            calculator = PnLCalculator(commission_rate=0.004)  # 0.4%

            # Средняя цена входа/выхода
            avg_entry_price = (position["spot_entry_price"] + position["futures_entry_price"]) / 2
            avg_exit_price = (close_spot_price + close_futures_price) / 2

            # Номинал позиции в USDT (среднее между спотом и фьючем)
            position_size = (
                position["spot_qty"] * position["spot_entry_price"] +
                position["futures_qty"] * position["futures_entry_price"]
            ) / 2

            # ===== ФАНДИНГ ПО ВРЕМЕНИ УДЕРЖАНИЯ =====
            entry_time_str = position.get("entry_timestamp")
            avg_funding_rate = position.get("avg_funding_rate", 0.0)  # % за 8 часов

            time_based_funding = 0.0
            if entry_time_str and avg_funding_rate != 0.0:
                try:
                    entry_time = datetime.fromisoformat(entry_time_str)
                    hold_hours = (datetime.now() - entry_time).total_seconds() / 3600.0
                    funding_periods = hold_hours / 8.0  # если период фандинга 8 часов
                    time_based_funding = position_size * (avg_funding_rate / 100.0) * funding_periods
                except Exception as e:
                    logger.error(f"{crypto}: ошибка расчёта фандинга по времени: {e}")
                    time_based_funding = 0.0

            # если вдруг когда-то будешь накапливать фандинг инкрементально — он тоже учтётся
            stored_funding = position.get("total_funding", 0.0)
            total_funding = stored_funding + time_based_funding

            # ===== PnL через калькулятор =====
            pnl_result = calculator.calculate_pnl(
                entry_price=avg_entry_price,
                exit_price=avg_exit_price,
                position_size=position_size,
                spread=spread,
                total_funding_received=total_funding,
            )

            # Сохраняем закрытую позицию в историю
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
                "entry_spread_pct": position["entry_spread_pct"],
                "close_spread": spread,
                "pnl": pnl_result,
            }

            self._save_closed_position(closed_position)

            logger.info(
                f"Закрыта позиция {crypto}. "
                f"Net PnL: {pnl_result['net_pnl']:.4f} USDT, "
                f"Price PnL: {pnl_result['price_pnl']:.4f}, "
                f"Funding: {pnl_result['funding']:.4f}, "
                f"Commission: {pnl_result['commission']:.4f}, "
                f"SpreadCost: {pnl_result['spread_cost']:.4f}"
            )

            # Удаляем открытую позицию
            self.clear_position(crypto)

            return pnl_result

    def _save_closed_position(self, closed_position: dict) -> None:
        """Сохраняет закрытую позицию в файл истории"""
        history_file = os.path.join(self.positions_dir, "closed_positions_history.json")  # ИСПРАВЛЕНО
        
        try:
            # Загружаем существующую историю
            if os.path.exists(history_file):
                with open(history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
            else:
                history = []
            
            # Добавляем новую закрытую позицию
            history.append(closed_position)
            
            # Сохраняем обновленную историю
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
            
            logger.info(f"История закрытой позиции {closed_position['crypto']} сохранена")
        except Exception as e:
            logger.error(f"Ошибка сохранения истории: {e}")

    def get_closed_positions_history(self) -> List[dict]:
        """Возвращает историю закрытых позиций"""
        history_file = os.path.join(self.positions_dir, "closed_positions_history.json")  # ИСПРАВЛЕНО
        
        try:
            if os.path.exists(history_file):
                with open(history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"Ошибка загрузки истории: {e}")
            return []

