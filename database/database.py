# -*- coding: utf-8 -*-
"""
Настройка подключения к базе данных.
Предоставляет Engine, SessionLocal и Base для моделей.
"""

import logging
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy import text

logger = logging.getLogger(__name__)

# ========================================
# Конфигурация базы данных
# ========================================

# По умолчанию SQLite, но легко заменить на PostgreSQL
DATABASE_URL = "sqlite:///./arbitrage.db"

# Для PostgreSQL используйте:
# DATABASE_URL = "postgresql://user:password@localhost:5432/arbitrage_db"

# ========================================
# Engine и Session
# ========================================

# Создание Engine с настройками для SQLite
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Только для SQLite
    echo=False,  # True для логирования SQL запросов (для отладки)
    pool_pre_ping=True,  # Проверка соединения перед использованием
    pool_recycle=3600,  # Переподключение каждые 60 минут
)


# Включаем foreign keys для SQLite (по умолчанию отключены)
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Включает поддержку foreign keys в SQLite."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# Фабрика сессий
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,  # Объекты остаются доступными после commit
)

# Базовый класс для всех моделей
Base = declarative_base()


# ========================================
# Dependency Injection функции
# ========================================

def get_db() -> Generator[Session, None, None]:
    """
    Генератор для получения сессии БД (используется для DI).
    
    Использование:
        with get_db() as session:
            # работа с БД
            
    Yields:
        Session: SQLAlchemy сессия
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session() -> Session:
    """
    Создает и возвращает новую сессию БД.
    Используется когда нужен прямой доступ к сессии.
    
    ВАЖНО: Вызывающий код ОБЯЗАН закрыть сессию через session.close()
    
    Returns:
        Session: SQLAlchemy сессия
    """
    return SessionLocal()


# ========================================
# Инициализация БД
# ========================================

def init_db() -> None:
    """
    Создает все таблицы в базе данных.
    Вызывается при первом запуске приложения или через Alembic.
    """
    logger.info("🔧 Инициализация базы данных...")
    
    # Импортируем модели чтобы они были зарегистрированы в Base.metadata
    from database.models import Position, ClosedPosition, Blacklist
    
    # Создаем все таблицы
    Base.metadata.create_all(bind=engine)
    
    logger.info("✅ База данных инициализирована")


def drop_all_tables() -> None:
    """
    Удаляет ВСЕ таблицы из базы данных.
    ОСТОРОЖНО: Используйте только для разработки/тестирования!
    """
    logger.warning("⚠️ УДАЛЕНИЕ ВСЕХ ТАБЛИЦ...")
    Base.metadata.drop_all(bind=engine)
    logger.warning("✅ Все таблицы удалены")


# ========================================
# Utility функции
# ========================================

def check_db_connection() -> bool:
    """
    Проверяет работоспособность подключения к БД.
    
    Returns:
        bool: True если подключение работает
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))  # ← ИСПРАВЛЕНИЕ
        logger.info("✅ Подключение к БД успешно")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к БД: {e}")
        return False


if __name__ == "__main__":
    # Тестирование подключения
    logging.basicConfig(level=logging.INFO)
    
    if check_db_connection():
        print("✅ Database connection successful")
        init_db()
    else:
        print("❌ Database connection failed")
