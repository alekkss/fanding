# -*- coding: utf-8 -*-
"""
Alembic environment configuration.
Настраивает окружение для миграций базы данных.
"""

import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# ========================================
# Добавляем корневую директорию в sys.path
# ========================================
# Это позволяет импортировать модули из корня проекта
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# ========================================
# Импортируем наши модели и настройки
# ========================================
from database.database import Base, engine
from database.models import Position, ClosedPosition, Blacklist
from config import DATABASE_URL

# Alembic Config объект
config = context.config

# Настройка логирования из alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ========================================
# Metadata для автогенерации миграций
# ========================================
# Alembic будет использовать metadata из наших моделей
# для определения изменений в структуре БД
target_metadata = Base.metadata

# Переопределяем sqlalchemy.url из alembic.ini значением из config.py
config.set_main_option("sqlalchemy.url", DATABASE_URL)


# ========================================
# Функции для offline и online миграций
# ========================================

def run_migrations_offline() -> None:
    """
    Запуск миграций в 'offline' режиме.
    
    В этом режиме миграции выполняются без подключения к БД.
    Генерируется SQL скрипт вместо прямого применения изменений.
    
    Используется командой: alembic upgrade --sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,  # Сравнивать типы колонок
        compare_server_default=True,  # Сравнивать default значения
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Запуск миграций в 'online' режиме.
    
    В этом режиме миграции применяются напрямую к базе данных.
    Используется существующий engine из database.py для подключения.
    
    Используется командой: alembic upgrade head
    """
    # Используем наш существующий engine вместо создания нового
    connectable = engine

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # Автоматически определять изменения типов
            compare_server_default=True,  # Автоматически определять изменения default
            render_as_batch=True,  # Для SQLite (поддержка ALTER TABLE)
        )

        with context.begin_transaction():
            context.run_migrations()


# ========================================
# Точка входа
# ========================================
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
