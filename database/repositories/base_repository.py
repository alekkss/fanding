# -*- coding: utf-8 -*-
"""
Базовый репозиторий с интерфейсом для всех репозиториев.
Реализует Repository Pattern и Dependency Inversion Principle.
"""

import logging
from abc import ABC, abstractmethod
from typing import TypeVar, Generic, List, Optional, Type, Dict, Any
from contextlib import contextmanager

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from database.database import get_db_session, Base

logger = logging.getLogger(__name__)

# Дженерик тип для моделей
ModelType = TypeVar("ModelType", bound=Base)


class IRepository(ABC, Generic[ModelType]):
    """
    Интерфейс репозитория (Dependency Inversion Principle).
    
    Определяет контракт для всех репозиториев.
    Позволяет легко подменять реализации (например, для тестов).
    """
    
    @abstractmethod
    def get_by_id(self, entity_id: int) -> Optional[ModelType]:
        """Получить сущность по ID."""
        pass
    
    @abstractmethod
    def get_all(self) -> List[ModelType]:
        """Получить все сущности."""
        pass
    
    @abstractmethod
    def save(self, entity: ModelType) -> ModelType:
        """Сохранить сущность (создать или обновить)."""
        pass
    
    @abstractmethod
    def delete(self, entity_id: int) -> bool:
        """Удалить сущность по ID."""
        pass
    
    @abstractmethod
    def exists(self, **filters) -> bool:
        """Проверить существование сущности по фильтрам."""
        pass


class BaseRepository(IRepository[ModelType], Generic[ModelType]):
    """
    Базовая реализация репозитория с общими CRUD операциями.
    
    Все конкретные репозитории наследуются от этого класса.
    Обеспечивает:
    - Thread-safety через контекстные менеджеры сессий
    - Автоматический rollback при ошибках
    - Логирование операций
    - Единообразие работы с БД
    """
    
    def __init__(self, model: Type[ModelType], session: Optional[Session] = None):
        """
        Args:
            model: SQLAlchemy модель (класс)
            session: SQLAlchemy сессия (опционально, создается автоматически)
        """
        self.model = model
        self._session = session
    
    @contextmanager
    def _get_session(self):
        """
        Контекстный менеджер для получения сессии.
        Обеспечивает thread-safety и автоматический commit/rollback.
        
        Yields:
            Session: SQLAlchemy сессия
        """
        if self._session:
            # Используем переданную сессию (для транзакций)
            yield self._session
        else:
            # Создаем новую сессию
            session = get_db_session()
            try:
                yield session
                session.commit()
            except Exception as e:
                session.rollback()
                logger.error(f"Database error in {self.__class__.__name__}: {e}")
                raise
            finally:
                session.close()
    
    def get_by_id(self, entity_id: int) -> Optional[ModelType]:
        """
        Получить сущность по ID.
        
        Args:
            entity_id: Первичный ключ
            
        Returns:
            ModelType | None: Найденная сущность или None
        """
        try:
            with self._get_session() as session:
                entity = session.query(self.model).filter(
                    self.model.id == entity_id
                ).first()
                
                if entity:
                    logger.debug(f"{self.model.__name__} found: ID={entity_id}")
                else:
                    logger.debug(f"{self.model.__name__} not found: ID={entity_id}")
                
                return entity
        except SQLAlchemyError as e:
            logger.error(f"Error getting {self.model.__name__} by ID {entity_id}: {e}")
            return None
    
    def get_all(self, limit: Optional[int] = None, offset: int = 0) -> List[ModelType]:
        """
        Получить все сущности с опциональной пагинацией.
        
        Args:
            limit: Максимальное количество записей
            offset: Смещение для пагинации
            
        Returns:
            List[ModelType]: Список сущностей
        """
        try:
            with self._get_session() as session:
                query = session.query(self.model)
                
                if limit:
                    query = query.limit(limit).offset(offset)
                
                entities = query.all()
                logger.debug(f"Retrieved {len(entities)} {self.model.__name__} entities")
                return entities
        except SQLAlchemyError as e:
            logger.error(f"Error getting all {self.model.__name__}: {e}")
            return []
    
    def save(self, entity: ModelType) -> ModelType:
        """
        Сохранить сущность (создать новую или обновить существующую).
        
        Args:
            entity: Экземпляр модели
            
        Returns:
            ModelType: Сохраненная сущность с обновленными полями (id, timestamps)
        """
        try:
            with self._get_session() as session:
                # Добавляем или мержим сущность
                if entity.id is None:
                    session.add(entity)
                    logger.debug(f"Creating new {self.model.__name__}")
                else:
                    entity = session.merge(entity)
                    logger.debug(f"Updating {self.model.__name__} ID={entity.id}")
                
                session.flush()  # Получаем ID до commit
                session.refresh(entity)  # Обновляем timestamps
                
                return entity
        except SQLAlchemyError as e:
            logger.error(f"Error saving {self.model.__name__}: {e}")
            raise
    
    def delete(self, entity_id: int) -> bool:
        """
        Удалить сущность по ID.
        
        Args:
            entity_id: Первичный ключ
            
        Returns:
            bool: True если удалено успешно, False если не найдено
        """
        try:
            with self._get_session() as session:
                entity = session.query(self.model).filter(
                    self.model.id == entity_id
                ).first()
                
                if entity:
                    session.delete(entity)
                    logger.info(f"Deleted {self.model.__name__} ID={entity_id}")
                    return True
                else:
                    logger.warning(f"{self.model.__name__} not found for deletion: ID={entity_id}")
                    return False
        except SQLAlchemyError as e:
            logger.error(f"Error deleting {self.model.__name__} ID={entity_id}: {e}")
            return False
    
    def exists(self, **filters) -> bool:
        """
        Проверить существование сущности по фильтрам.
        
        Args:
            **filters: Фильтры в формате column_name=value
            
        Returns:
            bool: True если сущность существует
            
        Example:
            repo.exists(crypto="BTC", active=True)
        """
        try:
            with self._get_session() as session:
                query = session.query(self.model)
                
                for key, value in filters.items():
                    if hasattr(self.model, key):
                        query = query.filter(getattr(self.model, key) == value)
                
                exists = query.first() is not None
                logger.debug(f"{self.model.__name__} exists={exists} with filters {filters}")
                return exists
        except SQLAlchemyError as e:
            logger.error(f"Error checking existence of {self.model.__name__}: {e}")
            return False
    
    def find_one(self, **filters) -> Optional[ModelType]:
        """
        Найти одну сущность по фильтрам.
        
        Args:
            **filters: Фильтры в формате column_name=value
            
        Returns:
            ModelType | None: Найденная сущность или None
        """
        try:
            with self._get_session() as session:
                query = session.query(self.model)
                
                for key, value in filters.items():
                    if hasattr(self.model, key):
                        query = query.filter(getattr(self.model, key) == value)
                
                entity = query.first()
                
                if entity:
                    logger.debug(f"{self.model.__name__} found with filters {filters}")
                else:
                    logger.debug(f"{self.model.__name__} not found with filters {filters}")
                
                return entity
        except SQLAlchemyError as e:
            logger.error(f"Error finding {self.model.__name__}: {e}")
            return None
    
    def find_all(self, **filters) -> List[ModelType]:
        """
        Найти все сущности по фильтрам.
        
        Args:
            **filters: Фильтры в формате column_name=value
            
        Returns:
            List[ModelType]: Список найденных сущностей
        """
        try:
            with self._get_session() as session:
                query = session.query(self.model)
                
                for key, value in filters.items():
                    if hasattr(self.model, key):
                        query = query.filter(getattr(self.model, key) == value)
                
                entities = query.all()
                logger.debug(f"Found {len(entities)} {self.model.__name__} with filters {filters}")
                return entities
        except SQLAlchemyError as e:
            logger.error(f"Error finding all {self.model.__name__}: {e}")
            return []
    
    def count(self, **filters) -> int:
        """
        Подсчитать количество сущностей по фильтрам.
        
        Args:
            **filters: Фильтры в формате column_name=value
            
        Returns:
            int: Количество записей
        """
        try:
            with self._get_session() as session:
                query = session.query(self.model)
                
                for key, value in filters.items():
                    if hasattr(self.model, key):
                        query = query.filter(getattr(self.model, key) == value)
                
                count = query.count()
                logger.debug(f"Count {self.model.__name__}: {count} with filters {filters}")
                return count
        except SQLAlchemyError as e:
            logger.error(f"Error counting {self.model.__name__}: {e}")
            return 0
