"""Dependency injection for FastAPI endpoints."""

from typing import AsyncGenerator, Annotated, Callable, List

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_async_session
from src.core.security import verify_token
from src.db.models.user import User
from src.db.repositories.user import UserRepository

security = HTTPBearer()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    async for session in get_async_session():
        yield session


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Get current authenticated user from JWT token."""
    token = credentials.credentials
    
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )
    
    return user


async def get_current_active_superuser(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Get current user and verify they are a superuser."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return current_user


async def get_verified_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Get current user and verify their email is verified."""
    if not current_user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required",
        )
    return current_user


def require_permission(permission: str) -> Callable:
    """Create a dependency that requires a specific permission."""
    async def permission_checker(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if not current_user.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required",
            )
        return current_user
    return permission_checker


def require_role(role_name: str) -> Callable:
    """Create a dependency that requires a specific role."""
    async def role_checker(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if not current_user.has_role(role_name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role_name}' required",
            )
        return current_user
    return role_checker


def require_any_permission(permissions: List[str]) -> Callable:
    """Create a dependency that requires any of the given permissions."""
    async def permission_checker(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        for permission in permissions:
            if current_user.has_permission(permission):
                return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"One of permissions {permissions} required",
        )
    return permission_checker


DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentSuperuser = Annotated[User, Depends(get_current_active_superuser)]
VerifiedUser = Annotated[User, Depends(get_verified_user)]


# =============================================================================
# Service Dependencies from DI Container
# =============================================================================


def get_llm_service() -> "LLMService":
    """Get LLM service singleton from DI container.

    Returns the singleton LLM service instance for generating text,
    chat completions, and other LLM operations.

    Returns:
        LLMService: The LLM service instance.

    Raises:
        HTTPException: If LLM service is not available.
    """
    from src.core.di import get_container
    from src.services.llm_service import LLMService

    try:
        container = get_container()
        return container.resolve("llm_service")
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM service is not available",
        )


def get_embedding_service() -> "EmbeddingService":
    """Get embedding service singleton from DI container.

    Returns the singleton embedding service instance for generating
    text embeddings for vector search.

    Returns:
        EmbeddingService: The embedding service instance.

    Raises:
        HTTPException: If embedding service is not available.
    """
    from src.core.di import get_container
    from src.services.embedding_service import EmbeddingService

    try:
        container = get_container()
        return container.resolve("embedding_service")
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding service is not available",
        )


def get_document_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> "DocumentService":
    """Get document service factory from DI container with database session.

    Creates a new document service instance for each request,
    injecting the current database session.

    Args:
        db: The async database session for this request.

    Returns:
        DocumentService: A new document service instance.

    Raises:
        HTTPException: If document service factory is not available.
    """
    from src.core.di import get_container
    from src.services.document_service import DocumentService

    try:
        container = get_container()
        return container.resolve_with_session("document_service", db)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document service is not available",
        )


# Forward references for type hints
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.services.llm_service import LLMService
    from src.services.embedding_service import EmbeddingService
    from src.services.document_service import DocumentService


# Type aliases for DI dependencies
LLMServiceDep = Annotated["LLMService", Depends(get_llm_service)]
EmbeddingServiceDep = Annotated["EmbeddingService", Depends(get_embedding_service)]
DocumentServiceDep = Annotated["DocumentService", Depends(get_document_service)]