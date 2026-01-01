"""Database session management.

Provides async database session context managers with proper error handling,
automatic commit/rollback, and structured logging.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings
from src.core.exceptions import DatabaseError, TransactionError

logger = structlog.get_logger(__name__)

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=settings.DATABASE_POOL_SIZE,
    pool_pre_ping=True,
)

# Create async session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session with proper error handling.

    This context manager provides:
    - Automatic commit on successful completion
    - Automatic rollback on any exception
    - Structured logging for errors
    - Proper handling of rollback failures

    Yields:
        AsyncSession: The database session.

    Raises:
        TransactionError: When commit or rollback fails.
        DatabaseError: When a database operation fails.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
            logger.debug("database_session_committed")
        except SQLAlchemyError as e:
            logger.error(
                "database_error",
                error_type=type(e).__name__,
                error_message=str(e),
            )
            try:
                await session.rollback()
                logger.info("database_session_rolled_back")
            except SQLAlchemyError as rollback_error:
                # Handle rare case where rollback itself fails
                logger.critical(
                    "database_rollback_failed",
                    original_error=str(e),
                    rollback_error=str(rollback_error),
                )
                raise TransactionError(
                    message="Transaction rollback failed",
                    details={
                        "original_error": str(e),
                        "rollback_error": str(rollback_error),
                    },
                ) from rollback_error
            raise DatabaseError(
                message="Database operation failed",
                operation="transaction",
                details={"error": str(e)},
            ) from e
        except Exception as e:
            # Handle non-SQLAlchemy exceptions (e.g., business logic errors)
            logger.warning(
                "session_exception",
                error_type=type(e).__name__,
                error_message=str(e),
            )
            try:
                await session.rollback()
                logger.info("database_session_rolled_back")
            except SQLAlchemyError as rollback_error:
                logger.critical(
                    "database_rollback_failed",
                    original_error=str(e),
                    rollback_error=str(rollback_error),
                )
                raise TransactionError(
                    message="Transaction rollback failed",
                    details={
                        "original_error": str(e),
                        "rollback_error": str(rollback_error),
                    },
                ) from rollback_error
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Alternative context manager for direct usage with async with.

    Use this when you need explicit control over the session lifecycle,
    such as in background tasks or non-FastAPI code.

    Example:
        async with get_db_session() as session:
            result = await session.execute(select(User))
            users = result.scalars().all()

    Yields:
        AsyncSession: The database session.

    Raises:
        TransactionError: When commit or rollback fails.
        DatabaseError: When a database operation fails.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
            logger.debug("database_session_committed")
        except SQLAlchemyError as e:
            logger.error(
                "database_error",
                error_type=type(e).__name__,
                error_message=str(e),
            )
            try:
                await session.rollback()
                logger.info("database_session_rolled_back")
            except SQLAlchemyError as rollback_error:
                logger.critical(
                    "database_rollback_failed",
                    original_error=str(e),
                    rollback_error=str(rollback_error),
                )
                raise TransactionError(
                    message="Transaction rollback failed",
                    details={
                        "original_error": str(e),
                        "rollback_error": str(rollback_error),
                    },
                ) from rollback_error
            raise DatabaseError(
                message="Database operation failed",
                operation="transaction",
                details={"error": str(e)},
            ) from e
        except Exception as e:
            logger.warning(
                "session_exception",
                error_type=type(e).__name__,
                error_message=str(e),
            )
            try:
                await session.rollback()
                logger.info("database_session_rolled_back")
            except SQLAlchemyError as rollback_error:
                logger.critical(
                    "database_rollback_failed",
                    original_error=str(e),
                    rollback_error=str(rollback_error),
                )
                raise TransactionError(
                    message="Transaction rollback failed",
                    details={
                        "original_error": str(e),
                        "rollback_error": str(rollback_error),
                    },
                ) from rollback_error
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database (create tables if they don't exist).

    Raises:
        DatabaseError: When database initialization fails.
    """
    from src.db.base import Base
    from src.db.models import user, document, chunk, query, agent_log  # noqa: F401

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("database_initialized")
    except SQLAlchemyError as e:
        logger.error(
            "database_init_failed",
            error_type=type(e).__name__,
            error_message=str(e),
        )
        raise DatabaseError(
            message="Failed to initialize database",
            operation="init",
            details={"error": str(e)},
        ) from e


async def close_db() -> None:
    """Close database connection pool.

    Raises:
        DatabaseError: When closing the connection pool fails.
    """
    try:
        await engine.dispose()
        logger.info("database_connection_closed")
    except SQLAlchemyError as e:
        logger.error(
            "database_close_failed",
            error_type=type(e).__name__,
            error_message=str(e),
        )
        raise DatabaseError(
            message="Failed to close database connection",
            operation="close",
            details={"error": str(e)},
        ) from e