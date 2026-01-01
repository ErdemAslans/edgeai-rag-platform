"""Base repository with common CRUD operations."""

import uuid
from typing import Generic, TypeVar, Type, List, Any, Dict, cast

from sqlalchemy import select, update, delete, func, Column
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.engine import CursorResult

from src.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Base repository class providing common CRUD operations."""

    def __init__(self, model: Type[ModelType], session: AsyncSession):
        """Initialize the repository.

        Args:
            model: The SQLAlchemy model class.
            session: The async database session.
        """
        self.model = model
        self.session = session

    def _get_id_column(self) -> Column[uuid.UUID]:
        """Get the id column from the model."""
        return cast(Column[uuid.UUID], getattr(self.model, "id"))

    async def get_by_id(self, id: uuid.UUID) -> ModelType | None:
        """Get a record by its ID.

        Args:
            id: The UUID of the record.

        Returns:
            The model instance or None if not found.
        """
        id_col = self._get_id_column()
        stmt = select(self.model).where(id_col == id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: str | None = None,
        order_desc: bool = False,
    ) -> List[ModelType]:
        """Get all records with pagination.

        Args:
            skip: Number of records to skip.
            limit: Maximum number of records to return.
            order_by: Column name to order by.
            order_desc: Whether to order descending.

        Returns:
            List of model instances.
        """
        stmt = select(self.model).offset(skip).limit(limit)

        if order_by and hasattr(self.model, order_by):
            order_column = getattr(self.model, order_by)
            stmt = stmt.order_by(order_column.desc() if order_desc else order_column)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_ids(self, ids: List[uuid.UUID]) -> List[ModelType]:
        """Get multiple records by their IDs.

        Args:
            ids: List of UUIDs.

        Returns:
            List of model instances.
        """
        if not ids:
            return []
        id_col = self._get_id_column()
        stmt = select(self.model).where(id_col.in_(ids))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, obj_in: Dict[str, Any]) -> ModelType:
        """Create a new record.

        Args:
            obj_in: Dictionary of field values.

        Returns:
            The created model instance.
        """
        db_obj = self.model(**obj_in)
        self.session.add(db_obj)
        await self.session.flush()
        await self.session.refresh(db_obj)
        return db_obj

    async def create_many(self, objs_in: List[Dict[str, Any]]) -> List[ModelType]:
        """Create multiple records.

        Args:
            objs_in: List of dictionaries with field values.

        Returns:
            List of created model instances.
        """
        db_objs = [self.model(**obj_in) for obj_in in objs_in]
        self.session.add_all(db_objs)
        await self.session.flush()
        for obj in db_objs:
            await self.session.refresh(obj)
        return db_objs

    async def update(
        self,
        id: uuid.UUID,
        obj_in: Dict[str, Any],
    ) -> ModelType | None:
        """Update a record by ID.

        Args:
            id: The UUID of the record.
            obj_in: Dictionary of field values to update.

        Returns:
            The updated model instance or None if not found.
        """
        id_col = self._get_id_column()
        stmt = (
            update(self.model)
            .where(id_col == id)
            .values(**obj_in)
            .returning(self.model)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none()

    async def delete(self, id: uuid.UUID) -> bool:
        """Delete a record by ID.

        Args:
            id: The UUID of the record.

        Returns:
            True if deleted, False if not found.
        """
        id_col = self._get_id_column()
        stmt = delete(self.model).where(id_col == id)
        result = await self.session.execute(stmt)
        await self.session.flush()
        cursor_result = cast(CursorResult[Any], result)
        return bool(cursor_result.rowcount > 0)

    async def delete_many(self, ids: List[uuid.UUID]) -> int:
        """Delete multiple records by their IDs.

        Args:
            ids: List of UUIDs to delete.

        Returns:
            Number of records deleted.
        """
        if not ids:
            return 0
        id_col = self._get_id_column()
        stmt = delete(self.model).where(id_col.in_(ids))
        result = await self.session.execute(stmt)
        await self.session.flush()
        cursor_result = cast(CursorResult[Any], result)
        return int(cursor_result.rowcount)

    async def count(self) -> int:
        """Count total records.

        Returns:
            Total number of records.
        """
        stmt = select(func.count()).select_from(self.model)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def exists(self, id: uuid.UUID) -> bool:
        """Check if a record exists by ID.

        Args:
            id: The UUID to check.

        Returns:
            True if exists, False otherwise.
        """
        id_col = self._get_id_column()
        stmt = select(func.count()).select_from(self.model).where(id_col == id)
        result = await self.session.execute(stmt)
        return result.scalar_one() > 0
