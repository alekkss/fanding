# -*- coding: utf-8 -*-
"""
Скрипт миграции blacklist.json в базу данных.
Запускается один раз после создания БД.

Usage:
    python scripts/migrate_blacklist_to_db.py
"""

import os
import sys
import json
import logging
from pathlib import Path

# Добавляем корневую директорию в путь для импортов
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.database import check_db_connection, init_db
from database.repositories.blacklist_repository import BlacklistRepository
from config import BLACKLIST_FILE

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_blacklist_json(filepath: str) -> dict:
    """
    Загрузить данные из blacklist.json.
    
    Args:
        filepath: Путь к JSON файлу
        
    Returns:
        dict: Данные blacklist в формате {crypto: {reason, error_code, timestamp}}
    """
    if not os.path.exists(filepath):
        logger.warning(f"⚠️ Файл {filepath} не найден")
        return {}
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.info(f"✅ Загружено {len(data)} записей из {filepath}")
        return data
    except json.JSONDecodeError as e:
        logger.error(f"❌ Ошибка парсинга JSON файла: {e}")
        return {}
    except Exception as e:
        logger.error(f"❌ Ошибка чтения файла {filepath}: {e}")
        return {}


def migrate_blacklist_to_db(blacklist_data: dict) -> int:
    """
    Мигрировать данные blacklist в базу данных.
    
    Args:
        blacklist_data: Словарь с данными blacklist
        
    Returns:
        int: Количество успешно добавленных записей
    """
    if not blacklist_data:
        logger.info("ℹ️ Нет данных для миграции")
        return 0
    
    repo = BlacklistRepository()
    
    logger.info(f"🔄 Начинаем миграцию {len(blacklist_data)} записей...")
    
    # Используем bulk_add метод из репозитория
    added_count = repo.bulk_add(blacklist_data)
    
    logger.info(f"✅ Миграция завершена: {added_count}/{len(blacklist_data)} записей добавлено")
    
    return added_count


def backup_json_file(filepath: str) -> bool:
    """
    Создать бэкап JSON файла перед миграцией.
    
    Args:
        filepath: Путь к оригинальному файлу
        
    Returns:
        bool: True если бэкап создан успешно
    """
    if not os.path.exists(filepath):
        return False
    
    backup_path = f"{filepath}.backup"
    
    try:
        import shutil
        shutil.copy2(filepath, backup_path)
        logger.info(f"💾 Создан бэкап: {backup_path}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка создания бэкапа: {e}")
        return False


def verify_migration(blacklist_data: dict) -> bool:
    """
    Проверить что все данные успешно мигрированы.
    
    Args:
        blacklist_data: Оригинальные данные из JSON
        
    Returns:
        bool: True если все данные в БД
    """
    repo = BlacklistRepository()
    
    logger.info("🔍 Проверка миграции...")
    
    all_blacklisted = repo.get_all_blacklisted()
    
    missing = set(blacklist_data.keys()) - all_blacklisted
    
    if missing:
        logger.warning(f"⚠️ Не найдены в БД: {missing}")
        return False
    
    logger.info(f"✅ Все {len(blacklist_data)} записей успешно мигрированы")
    return True


def main():
    """Главная функция скрипта миграции."""
    
    logger.info("=" * 60)
    logger.info("🚀 МИГРАЦИЯ BLACKLIST.JSON → DATABASE")
    logger.info("=" * 60)
    
    # Проверка подключения к БД
    if not check_db_connection():
        logger.error("❌ Не удалось подключиться к базе данных")
        logger.error("💡 Убедитесь что БД инициализирована: alembic upgrade head")
        sys.exit(1)
    
    # Путь к JSON файлу
    json_path = BLACKLIST_FILE
    
    logger.info(f"📂 Путь к blacklist.json: {json_path}")
    
    # Проверка существования файла
    if not os.path.exists(json_path):
        logger.warning(f"⚠️ Файл {json_path} не найден")
        logger.info("ℹ️ Нечего мигрировать. База данных готова к использованию.")
        sys.exit(0)
    
    # Создание бэкапа
    backup_json_file(json_path)
    
    # Загрузка данных из JSON
    blacklist_data = load_blacklist_json(json_path)
    
    if not blacklist_data:
        logger.info("ℹ️ Blacklist пуст. Нечего мигрировать.")
        sys.exit(0)
    
    # Показываем что будет мигрировано
    logger.info(f"📋 Записи для миграции:")
    for crypto, details in list(blacklist_data.items())[:5]:
        logger.info(f"   • {crypto}: {details.get('reason', 'N/A')[:50]}...")
    
    if len(blacklist_data) > 5:
        logger.info(f"   ... и еще {len(blacklist_data) - 5} записей")
    
    # Запрос подтверждения
    try:
        response = input("\n❓ Продолжить миграцию? (yes/no): ").strip().lower()
        if response not in ['yes', 'y', 'да']:
            logger.info("❌ Миграция отменена пользователем")
            sys.exit(0)
    except (KeyboardInterrupt, EOFError):
        logger.info("\n❌ Миграция отменена")
        sys.exit(0)
    
    # Миграция данных
    added_count = migrate_blacklist_to_db(blacklist_data)
    
    # Проверка миграции
    if verify_migration(blacklist_data):
        logger.info("=" * 60)
        logger.info(f"✅ МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО")
        logger.info(f"📊 Добавлено записей: {added_count}/{len(blacklist_data)}")
        logger.info("=" * 60)
        logger.info(f"💡 Теперь можно удалить {json_path} (бэкап сохранен)")
    else:
        logger.error("=" * 60)
        logger.error("⚠️ МИГРАЦИЯ ЗАВЕРШЕНА С ПРЕДУПРЕЖДЕНИЯМИ")
        logger.error("📊 Проверьте логи выше")
        logger.error("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n❌ Миграция прервана пользователем")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)
