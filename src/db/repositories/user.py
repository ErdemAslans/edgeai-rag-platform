"""User repository for user-specific database operations."""

import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.user import User
from src.db.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User model operations."""

    def __init__(self, session: AsyncSession):
        """Initialize the user repository.

        Args:
            session: The async database session.
        """
        super().__init__(User, session)

    async def get_by_email(self, email: str) -> User | None:
        """Get a user by email address.

        Args:
            email: The email address to search for.

        Returns:
            The user instance or None if not found.
        """
        stmt = select(User).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


    async def get_active_users(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> List[User]:
        """Get all active users.

        Args:
            skip: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of active user instances.
        """
        stmt = (
            select(User)
            .where(User.is_active == True)
            .offset(skip)
            .limit(limit)
            .order_by(User.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def email_exists(self, email: str) -> bool:
        """Check if an email already exists.

        Args:
            email: The email to check.

        Returns:
            True if email exists, False otherwise.
        """
        user = await self.get_by_email(email)
        return user is not None

    async def update_last_login(self, user_id: uuid.UUID) -> User | None:
        """Update the last login timestamp for a user.

        Args:
            user_id: The UUID of the user.

        Returns:
            The updated user instance or None if not found.
        """
        from datetime import datetime

        return await self.update(user_id, {"updated_at": datetime.utcnow()})

    async def deactivate_user(self, user_id: uuid.UUID) -> User | None:
        """Deactivate a user account.

        Args:
            user_id: The UUID of the user.

        Returns:
            The updated user instance or None if not found.
        """
        return await self.update(user_id, {"is_active": False})

    async def activate_user(self, user_id: uuid.UUID) -> User | None:
        """Activate a user account.

        Args:
            user_id: The UUID of the user.

        Returns:
            The updated user instance or None if not found.
        """
        return await self.update(user_id, {"is_active": True})