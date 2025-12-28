"""Authentication service for user management and JWT handling."""

import uuid
from datetime import datetime
from typing import Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import verify_password, get_password_hash, create_access_token
from src.core.exceptions import (
    AuthenticationError,
    UserNotFoundError,
    UserAlreadyExistsError,
    ValidationError,
)
from src.db.repositories.user import UserRepository
from src.db.models.user import User


class AuthService:
    """Service for authentication and user management."""

    def __init__(self, session: AsyncSession):
        """Initialize the auth service.

        Args:
            session: The async database session.
        """
        self.session = session
        self.user_repo = UserRepository(session)

    async def register_user(
        self,
        email: str,
        password: str,
        full_name: str | None = None,
    ) -> User:
        """Register a new user.

        Args:
            email: User's email address.
            password: User's password (will be hashed).
            full_name: User's full name (optional).

        Returns:
            The created user instance.

        Raises:
            UserAlreadyExistsError: If email already exists.
            ValidationError: If validation fails.
        """
        # Check if email exists
        if await self.user_repo.email_exists(email):
            raise UserAlreadyExistsError(f"Email '{email}' is already registered")

        # Validate password strength
        self._validate_password(password)

        # Create user
        hashed_password = get_password_hash(password)
        user = await self.user_repo.create({
            "email": email,
            "hashed_password": hashed_password,
            "full_name": full_name,
            "is_active": True,
        })

        await self.session.commit()
        return user

    async def authenticate_user(
        self,
        email: str,
        password: str,
    ) -> Tuple[User, str]:
        """Authenticate a user and return access token.

        Args:
            email: User's email address.
            password: User's password.

        Returns:
            Tuple of (user, access_token).

        Raises:
            AuthenticationError: If authentication fails.
        """
        user = await self.user_repo.get_by_email(email)
        
        if not user:
            raise AuthenticationError("Invalid email or password")

        if not verify_password(password, user.hashed_password):
            raise AuthenticationError("Invalid email or password")

        if not user.is_active:
            raise AuthenticationError("User account is deactivated")

        # Update last login
        await self.user_repo.update_last_login(user.id)
        await self.session.commit()

        # Create access token
        access_token = create_access_token(
            subject=str(user.id),
            additional_claims={
                "email": user.email,
            },
        )

        return user, access_token

    async def get_user_by_id(self, user_id: uuid.UUID) -> User:
        """Get a user by ID.

        Args:
            user_id: The user's UUID.

        Returns:
            The user instance.

        Raises:
            UserNotFoundError: If user not found.
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User with ID '{user_id}' not found")
        return user

    async def get_user_by_email(self, email: str) -> User:
        """Get a user by email.

        Args:
            email: The user's email.

        Returns:
            The user instance.

        Raises:
            UserNotFoundError: If user not found.
        """
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise UserNotFoundError(f"User with email '{email}' not found")
        return user

    async def update_password(
        self,
        user_id: uuid.UUID,
        current_password: str,
        new_password: str,
    ) -> User:
        """Update a user's password.

        Args:
            user_id: The user's UUID.
            current_password: Current password for verification.
            new_password: New password to set.

        Returns:
            The updated user instance.

        Raises:
            UserNotFoundError: If user not found.
            AuthenticationError: If current password is wrong.
            ValidationError: If new password validation fails.
        """
        user = await self.get_user_by_id(user_id)

        if not verify_password(current_password, user.hashed_password):
            raise AuthenticationError("Current password is incorrect")

        self._validate_password(new_password)

        hashed_password = get_password_hash(new_password)
        updated_user = await self.user_repo.update(
            user_id,
            {"hashed_password": hashed_password},
        )
        await self.session.commit()

        return updated_user

    async def update_profile(
        self,
        user_id: uuid.UUID,
        full_name: str | None = None,
        email: str | None = None,
    ) -> User:
        """Update user profile information.

        Args:
            user_id: The user's UUID.
            full_name: New full name (optional).
            email: New email (optional).

        Returns:
            The updated user instance.

        Raises:
            UserNotFoundError: If user not found.
            UserAlreadyExistsError: If new email already exists.
        """
        user = await self.get_user_by_id(user_id)

        update_data = {}

        if full_name is not None:
            update_data["full_name"] = full_name

        if email is not None and email != user.email:
            if await self.user_repo.email_exists(email):
                raise UserAlreadyExistsError(f"Email '{email}' is already registered")
            update_data["email"] = email

        if update_data:
            user = await self.user_repo.update(user_id, update_data)
            await self.session.commit()

        return user

    async def deactivate_user(self, user_id: uuid.UUID) -> User:
        """Deactivate a user account.

        Args:
            user_id: The user's UUID.

        Returns:
            The updated user instance.

        Raises:
            UserNotFoundError: If user not found.
        """
        await self.get_user_by_id(user_id)  # Verify user exists
        user = await self.user_repo.deactivate_user(user_id)
        await self.session.commit()
        return user

    async def activate_user(self, user_id: uuid.UUID) -> User:
        """Activate a user account.

        Args:
            user_id: The user's UUID.

        Returns:
            The updated user instance.

        Raises:
            UserNotFoundError: If user not found.
        """
        await self.get_user_by_id(user_id)  # Verify user exists
        user = await self.user_repo.activate_user(user_id)
        await self.session.commit()
        return user

    def _validate_password(self, password: str) -> None:
        """Validate password strength.

        Args:
            password: The password to validate.

        Raises:
            ValidationError: If password doesn't meet requirements.
        """
        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters long")

        if not any(c.isupper() for c in password):
            raise ValidationError("Password must contain at least one uppercase letter")

        if not any(c.islower() for c in password):
            raise ValidationError("Password must contain at least one lowercase letter")

        if not any(c.isdigit() for c in password):
            raise ValidationError("Password must contain at least one digit")