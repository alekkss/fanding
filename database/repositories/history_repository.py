# -*- coding: utf-8 -*-
"""
Репозиторий для работы с историей закрытых позиций.
Управляет сохранением и анализом PnL данных.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from sqlalchemy import func, desc
from sqlalchemy.exc import SQLAlchemyError

from database.models import ClosedPosition
from database.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class HistoryRepository(BaseRepository[ClosedPosition]):
    """
    Репозиторий для работы с историей закрытых позиций.
    
    Предоставляет методы:
    - Сохранение закрытой позиции с PnL
    - Получение истории по фильтрам
    - Расчет статистики (total PnL, win rate, etc.)
    - Получение последних закрытых позиций
    """
    
    def __init__(self):
        """Инициализация репозитория с моделью ClosedPosition."""
        super().__init__(model=ClosedPosition)
    
    def save_closed_position(
        self,
        crypto: str,
        entry_timestamp: datetime,
        close_timestamp: datetime,
        spot_entry_price: float,
        futures_entry_price: float,
        spot_exit_price: float,
        futures_exit_price: float,
        spot_qty: float,
        futures_qty: float,
        entry_spread_pct: float,
        close_spread_pct: float,
        pnl_data: Dict[str, float],
        funding_payments_count: int = 0
    ) -> Optional[ClosedPosition]:
        """
        Сохранить закрытую позицию с PnL данными.
        
        Args:
            crypto: Символ криптовалюты
            entry_timestamp: Время открытия позиции
            close_timestamp: Время закрытия позиции
            spot_entry_price: Цена входа спот
            futures_entry_price: Цена входа фьючерс
            spot_exit_price: Цена выхода спот
            futures_exit_price: Цена выхода фьючерс
            spot_qty: Количество спот
            futures_qty: Количество фьючерс
            entry_spread_pct: Спред при входе (%)
            close_spread_pct: Спред при закрытии (%)
            pnl_data: Словарь с PnL компонентами
            funding_payments_count: Количество выплат фандинга
            
        Returns:
            ClosedPosition | None: Сохраненная позиция или None при ошибке
        """
        try:
            closed_position = ClosedPosition(
                crypto=crypto,
                entry_timestamp=entry_timestamp,
                close_timestamp=close_timestamp,
                spot_entry_price=spot_entry_price,
                futures_entry_price=futures_entry_price,
                spot_exit_price=spot_exit_price,
                futures_exit_price=futures_exit_price,
                spot_qty=spot_qty,
                futures_qty=futures_qty,
                entry_spread_pct=entry_spread_pct,
                close_spread_pct=close_spread_pct,
                net_pnl=pnl_data.get('net_pnl', 0.0),
                price_pnl=pnl_data.get('price_pnl', 0.0),
                spot_pnl=pnl_data.get('spot_pnl'),
                futures_pnl=pnl_data.get('futures_pnl'),
                funding_pnl=pnl_data.get('funding', 0.0),
                commission=pnl_data.get('commission', 0.0),
                funding_payments_count=funding_payments_count
            )
            
            saved = self.save(closed_position)
            
            pnl_sign = "✅" if saved.net_pnl > 0 else "❌"
            logger.info(
                f"[HISTORY REPO] {pnl_sign} Сохранена закрытая позиция: {crypto} | "
                f"Net PnL: {saved.net_pnl:+.4f} USDT | ID={saved.id}"
            )
            
            return saved
            
        except SQLAlchemyError as e:
            logger.error(f"[HISTORY REPO] ❌ Ошибка сохранения истории {crypto}: {e}")
            return None
    
    def get_history_by_crypto(
        self,
        crypto: str,
        limit: Optional[int] = None
    ) -> List[ClosedPosition]:
        """
        Получить историю закрытых позиций для конкретной криптовалюты.
        
        Args:
            crypto: Символ криптовалюты
            limit: Максимальное количество записей
            
        Returns:
            List[ClosedPosition]: Список закрытых позиций
        """
        try:
            with self._get_session() as session:
                query = session.query(ClosedPosition).filter(
                    ClosedPosition.crypto == crypto
                ).order_by(desc(ClosedPosition.close_timestamp))
                
                if limit:
                    query = query.limit(limit)
                
                positions = query.all()
                logger.debug(f"[HISTORY REPO] Найдено {len(positions)} закрытых позиций для {crypto}")
                return positions
                
        except SQLAlchemyError as e:
            logger.error(f"[HISTORY REPO] Ошибка получения истории {crypto}: {e}")
            return []
    
    def get_recent_history(self, limit: int = 10) -> List[ClosedPosition]:
        """
        Получить последние закрытые позиции.
        
        Args:
            limit: Количество последних записей
            
        Returns:
            List[ClosedPosition]: Список последних закрытых позиций
        """
        try:
            with self._get_session() as session:
                positions = session.query(ClosedPosition).order_by(
                    desc(ClosedPosition.close_timestamp)
                ).limit(limit).all()
                
                logger.debug(f"[HISTORY REPO] Получено {len(positions)} последних позиций")
                return positions
                
        except SQLAlchemyError as e:
            logger.error(f"[HISTORY REPO] Ошибка получения последних позиций: {e}")
            return []
    
    def get_history_by_date_range(
        self,
        start_date: datetime,
        end_date: Optional[datetime] = None
    ) -> List[ClosedPosition]:
        """
        Получить историю за период времени.
        
        Args:
            start_date: Начало периода
            end_date: Конец периода (опционально, по умолчанию текущее время)
            
        Returns:
            List[ClosedPosition]: Список закрытых позиций
        """
        try:
            if end_date is None:
                end_date = datetime.now()
            
            with self._get_session() as session:
                positions = session.query(ClosedPosition).filter(
                    ClosedPosition.close_timestamp >= start_date,
                    ClosedPosition.close_timestamp <= end_date
                ).order_by(desc(ClosedPosition.close_timestamp)).all()
                
                logger.debug(
                    f"[HISTORY REPO] Найдено {len(positions)} позиций за период "
                    f"{start_date.date()} - {end_date.date()}"
                )
                return positions
                
        except SQLAlchemyError as e:
            logger.error(f"[HISTORY REPO] Ошибка получения истории за период: {e}")
            return []
    
    def get_all_history(self) -> List[ClosedPosition]:
        """
        Получить всю историю закрытых позиций.
        
        Returns:
            List[ClosedPosition]: Список всех закрытых позиций
        """
        try:
            with self._get_session() as session:
                positions = session.query(ClosedPosition).order_by(
                    desc(ClosedPosition.close_timestamp)
                ).all()
                
                logger.info(f"[HISTORY REPO] Всего закрытых позиций: {len(positions)}")
                return positions
                
        except SQLAlchemyError as e:
            logger.error(f"[HISTORY REPO] Ошибка получения всей истории: {e}")
            return []
    
    def calculate_total_pnl(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> float:
        """
        Рассчитать общий PnL за период.
        
        Args:
            start_date: Начало периода (опционально)
            end_date: Конец периода (опционально)
            
        Returns:
            float: Общий PnL в USDT
        """
        try:
            with self._get_session() as session:
                query = session.query(func.sum(ClosedPosition.net_pnl))
                
                if start_date:
                    query = query.filter(ClosedPosition.close_timestamp >= start_date)
                if end_date:
                    query = query.filter(ClosedPosition.close_timestamp <= end_date)
                
                total = query.scalar()
                total_pnl = float(total) if total else 0.0
                
                logger.debug(f"[HISTORY REPO] Общий PnL: {total_pnl:.4f} USDT")
                return total_pnl
                
        except SQLAlchemyError as e:
            logger.error(f"[HISTORY REPO] Ошибка расчета total PnL: {e}")
            return 0.0
    
    def calculate_statistics(self) -> Dict[str, Any]:
        """
        Рассчитать статистику по всей истории.
        
        Returns:
            Dict: Статистика {
                total_trades, total_pnl, avg_pnl, 
                win_count, loss_count, win_rate,
                best_trade, worst_trade
            }
        """
        try:
            with self._get_session() as session:
                # Общее количество сделок
                total_trades = session.query(func.count(ClosedPosition.id)).scalar() or 0
                
                if total_trades == 0:
                    logger.info("[HISTORY REPO] Нет закрытых позиций для статистики")
                    return self._empty_statistics()
                
                # Общий и средний PnL
                total_pnl = session.query(func.sum(ClosedPosition.net_pnl)).scalar() or 0.0
                avg_pnl = total_pnl / total_trades
                
                # Количество прибыльных и убыточных
                win_count = session.query(func.count(ClosedPosition.id)).filter(
                    ClosedPosition.net_pnl > 0
                ).scalar() or 0
                
                loss_count = session.query(func.count(ClosedPosition.id)).filter(
                    ClosedPosition.net_pnl <= 0
                ).scalar() or 0
                
                win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0.0
                
                # Лучшая и худшая сделки
                best_trade = session.query(func.max(ClosedPosition.net_pnl)).scalar() or 0.0
                worst_trade = session.query(func.min(ClosedPosition.net_pnl)).scalar() or 0.0
                
                stats = {
                    "total_trades": total_trades,
                    "total_pnl": float(total_pnl),
                    "avg_pnl": float(avg_pnl),
                    "win_count": win_count,
                    "loss_count": loss_count,
                    "win_rate": float(win_rate),
                    "best_trade": float(best_trade),
                    "worst_trade": float(worst_trade)
                }
                
                logger.info(f"[HISTORY REPO] 📊 Статистика: {total_trades} сделок, "
                           f"Total PnL: {total_pnl:+.4f} USDT, Win rate: {win_rate:.2f}%")
                
                return stats
                
        except SQLAlchemyError as e:
            logger.error(f"[HISTORY REPO] Ошибка расчета статистики: {e}")
            return self._empty_statistics()
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Алиас для calculate_statistics().
        Используется в Telegram handlers.
        
        Returns:
            Dict: Статистика торговли
        """
        return self.calculate_statistics()
    
    def get_profitable_cryptos(self, min_trades: int = 3) -> List[Dict[str, Any]]:
        """
        Получить список криптовалют с положительным PnL.
        
        Args:
            min_trades: Минимальное количество сделок для включения
            
        Returns:
            List[Dict]: Список [{crypto, total_pnl, trade_count, avg_pnl}]
        """
        try:
            with self._get_session() as session:
                results = session.query(
                    ClosedPosition.crypto,
                    func.sum(ClosedPosition.net_pnl).label('total_pnl'),
                    func.count(ClosedPosition.id).label('trade_count'),
                    func.avg(ClosedPosition.net_pnl).label('avg_pnl')
                ).group_by(
                    ClosedPosition.crypto
                ).having(
                    func.count(ClosedPosition.id) >= min_trades
                ).order_by(
                    desc('total_pnl')
                ).all()
                
                profitable = [
                    {
                        "crypto": row.crypto,
                        "total_pnl": float(row.total_pnl),
                        "trade_count": row.trade_count,
                        "avg_pnl": float(row.avg_pnl)
                    }
                    for row in results if row.total_pnl > 0
                ]
                
                logger.debug(f"[HISTORY REPO] Найдено {len(profitable)} прибыльных криптовалют")
                return profitable
                
        except SQLAlchemyError as e:
            logger.error(f"[HISTORY REPO] Ошибка получения прибыльных криптовалют: {e}")
            return []
    
    def get_history_count(self) -> int:
        """
        Получить общее количество закрытых позиций.
        
        Returns:
            int: Количество записей
        """
        return self.count()
    
    @staticmethod
    def _empty_statistics() -> Dict[str, Any]:
        """Возвращает пустую статистику."""
        return {
            "total_trades": 0,
            "total_pnl": 0.0,
            "avg_pnl": 0.0,
            "win_count": 0,
            "loss_count": 0,
            "win_rate": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0
        }
    
