# -*- coding: utf-8 -*-
"""
SQLAlchemy модели для арбитражного бота.
Определяет структуру таблиц: positions, closed_positions, blacklist.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, 
    DateTime, Text, Index
)
from database.database import Base


class Position(Base):
    """
    Модель открытой арбитражной позиции.
    
    Соответствует структуре из JSON файлов positions/*.json
    """
    __tablename__ = "positions"
    
    # Первичный ключ
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Криптовалюта (уникальная - одна позиция на символ)
    crypto = Column(String(20), unique=True, nullable=False, index=True)
    
    # Цены входа
    spot_entry_price = Column(Float, nullable=False)
    futures_entry_price = Column(Float, nullable=False)
    
    # Количество монет
    spot_qty = Column(Float, nullable=False)
    futures_qty = Column(Float, nullable=False)
    
    # Спред при входе
    entry_spread_pct = Column(Float, nullable=False)
    
    # Временные метки
    entry_timestamp = Column(DateTime, nullable=False)
    last_funding_check_time = Column(DateTime, nullable=True)
    
    # Отслеживание funding rate
    funding_payments_count = Column(Integer, default=0, nullable=False)
    low_fr_count = Column(Integer, default=0, nullable=False)
    consecutive_low_fr = Column(Boolean, default=False, nullable=False)
    
    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self) -> str:
        return (
            f"<Position(crypto={self.crypto}, "
            f"spot_entry={self.spot_entry_price:.6f}, "
            f"futures_entry={self.futures_entry_price:.6f}, "
            f"qty={self.spot_qty:.4f})>"
        )
    
    def to_dict(self) -> dict:
        """
        Преобразует модель в словарь (совместимость с JSON форматом).
        
        Returns:
            dict: Словарь с данными позиции
        """
        return {
            "crypto": self.crypto,
            "spot_entry_price": self.spot_entry_price,
            "futures_entry_price": self.futures_entry_price,
            "spot_qty": self.spot_qty,
            "futures_qty": self.futures_qty,
            "entry_spread_pct": self.entry_spread_pct,
            "entry_timestamp": self.entry_timestamp.isoformat(),
            "funding_payments_count": self.funding_payments_count,
            "last_funding_check_time": (
                self.last_funding_check_time.isoformat() 
                if self.last_funding_check_time else None
            ),
            "low_fr_count": self.low_fr_count,
            "consecutive_low_fr": self.consecutive_low_fr,
        }


class ClosedPosition(Base):
    """
    Модель закрытой позиции с расчетом PnL.
    
    Соответствует структуре из closed_positions_history.json
    """
    __tablename__ = "closed_positions"
    
    # Первичный ключ
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Криптовалюта
    crypto = Column(String(20), nullable=False, index=True)
    
    # Временные метки
    entry_timestamp = Column(DateTime, nullable=False)
    close_timestamp = Column(DateTime, nullable=False)
    
    # Цены входа
    spot_entry_price = Column(Float, nullable=False)
    futures_entry_price = Column(Float, nullable=False)
    
    # Цены выхода
    spot_exit_price = Column(Float, nullable=False)
    futures_exit_price = Column(Float, nullable=False)
    
    # Количество монет
    spot_qty = Column(Float, nullable=False)
    futures_qty = Column(Float, nullable=False)
    
    # Спреды
    entry_spread_pct = Column(Float, nullable=False)
    close_spread_pct = Column(Float, nullable=False)
    
    # PnL компоненты
    net_pnl = Column(Float, nullable=False)  # Чистая прибыль/убыток
    price_pnl = Column(Float, nullable=False)  # PnL от изменения цены
    spot_pnl = Column(Float, nullable=True)  # PnL спот позиции
    futures_pnl = Column(Float, nullable=True)  # PnL фьючерс позиции
    funding_pnl = Column(Float, nullable=False)  # Полученный фандинг
    commission = Column(Float, nullable=False)  # Комиссии
    
    # Дополнительная информация
    funding_payments_count = Column(Integer, default=0, nullable=False)
    
    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self) -> str:
        return (
            f"<ClosedPosition(crypto={self.crypto}, "
            f"net_pnl={self.net_pnl:.4f} USDT, "
            f"closed_at={self.close_timestamp})>"
        )
    
    def to_dict(self) -> dict:
        """
        Преобразует модель в словарь.
        
        Returns:
            dict: Словарь с данными закрытой позиции
        """
        return {
            "crypto": self.crypto,
            "entry_timestamp": self.entry_timestamp.isoformat(),
            "close_timestamp": self.close_timestamp.isoformat(),
            "spot_entry_price": self.spot_entry_price,
            "futures_entry_price": self.futures_entry_price,
            "spot_exit_price": self.spot_exit_price,
            "futures_exit_price": self.futures_exit_price,
            "spot_qty": self.spot_qty,
            "futures_qty": self.futures_qty,
            "entry_spread_pct": self.entry_spread_pct,
            "close_spread_pct": self.close_spread_pct,
            "pnl": {
                "net_pnl": self.net_pnl,
                "price_pnl": self.price_pnl,
                "spot_pnl": self.spot_pnl,
                "futures_pnl": self.futures_pnl,
                "funding": self.funding_pnl,
                "commission": self.commission,
            },
            "funding_payments_count": self.funding_payments_count,
        }


class Blacklist(Base):
    """
    Модель для исключенных криптовалют.
    
    Соответствует структуре из blacklist.json
    """
    __tablename__ = "blacklist"
    
    # Первичный ключ
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Криптовалюта (уникальная)
    crypto = Column(String(20), unique=True, nullable=False, index=True)
    
    # Причина добавления в blacklist
    reason = Column(Text, nullable=False)
    
    # Код ошибки (если есть)
    error_code = Column(Integer, nullable=True)
    
    # Временная метка добавления
    timestamp = Column(DateTime, nullable=False)
    
    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self) -> str:
        return (
            f"<Blacklist(crypto={self.crypto}, "
            f"reason={self.reason[:50]}..., "
            f"error_code={self.error_code})>"
        )
    
    def to_dict(self) -> dict:
        """
        Преобразует модель в словарь (совместимость с JSON форматом).
        
        Returns:
            dict: Словарь с данными blacklist
        """
        return {
            "crypto": self.crypto,
            "reason": self.reason,
            "error_code": self.error_code,
            "timestamp": self.timestamp.isoformat(),
        }


# ========================================
# Индексы для оптимизации запросов
# ========================================

# Составные индексы для частых запросов
Index('idx_closed_positions_crypto_date', ClosedPosition.crypto, ClosedPosition.close_timestamp)
Index('idx_closed_positions_date', ClosedPosition.close_timestamp)
Index('idx_positions_created', Position.created_at)
