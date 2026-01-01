"""Retry logic configuration using tenacity library.

This module provides configurable retry decorators for resilient LLM and
external service calls. Uses exponential backoff with jitter for optimal
retry behavior.

Usage:
    from src.core.retry import llm_retry, embedding_retry

    @llm_retry
    async def call_llm_api():
        # LLM API call that may fail transiently
        pass

    @embedding_retry
    async def generate_embeddings():
        # Embedding generation that may fail
        pass
"""

import asyncio
from typing import Any, Callable, TypeVar, ParamSpec, Awaitable

import structlog
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
    before_sleep_log,
    after_log,
)

from src.core.exceptions import (
    LLMError,
    LLMTimeoutError,
    LLMRateLimitError,
    EmbeddingError,
    VectorSearchError,
    ServiceUnavailableError,
)

logger = structlog.get_logger(__name__)


# Type variables for generic decorator typing
P = ParamSpec("P")
T = TypeVar("T")


# =============================================================================
# Retry Configuration Constants
# =============================================================================


class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        MAX_ATTEMPTS: Maximum number of retry attempts (including initial).
        MIN_WAIT: Minimum wait time in seconds between retries.
        MAX_WAIT: Maximum wait time in seconds between retries.
        JITTER: Maximum jitter in seconds to add to wait time.
        EXPONENTIAL_BASE: Base for exponential backoff calculation.
    """

    MAX_ATTEMPTS: int = 3
    MIN_WAIT: float = 1.0
    MAX_WAIT: float = 30.0
    JITTER: float = 1.0
    EXPONENTIAL_BASE: int = 2


# =============================================================================
# Retryable Exception Types
# =============================================================================

# Exceptions that indicate transient failures and should be retried
LLM_RETRYABLE_EXCEPTIONS = (
    LLMError,
    LLMTimeoutError,
    LLMRateLimitError,
    TimeoutError,
    ConnectionError,
    asyncio.TimeoutError,
    OSError,  # Includes network-related errors
)

# Exceptions for embedding service retries
EMBEDDING_RETRYABLE_EXCEPTIONS = (
    EmbeddingError,
    VectorSearchError,
    TimeoutError,
    ConnectionError,
    asyncio.TimeoutError,
    OSError,
)

# Exceptions for external service retries
SERVICE_RETRYABLE_EXCEPTIONS = (
    ServiceUnavailableError,
    TimeoutError,
    ConnectionError,
    asyncio.TimeoutError,
    OSError,
)


# =============================================================================
# Logging Callbacks
# =============================================================================


def log_retry_attempt(retry_state: Any) -> None:
    """Log retry attempt with structured logging.

    Args:
        retry_state: Tenacity retry state containing attempt information.
    """
    exception = retry_state.outcome.exception() if retry_state.outcome else None
    exception_type = type(exception).__name__ if exception else "Unknown"
    exception_msg = str(exception) if exception else "No exception"

    logger.warning(
        "Retry attempt",
        attempt=retry_state.attempt_number,
        exception_type=exception_type,
        exception_message=exception_msg,
        wait_time=getattr(retry_state, "next_action", None),
        function=getattr(retry_state.fn, "__name__", "unknown") if retry_state.fn else "unknown",
    )


def log_retry_exhausted(retry_state: Any) -> None:
    """Log when all retry attempts are exhausted.

    Args:
        retry_state: Tenacity retry state containing attempt information.
    """
    exception = retry_state.outcome.exception() if retry_state.outcome else None
    exception_type = type(exception).__name__ if exception else "Unknown"
    exception_msg = str(exception) if exception else "No exception"

    logger.error(
        "All retry attempts exhausted",
        total_attempts=retry_state.attempt_number,
        exception_type=exception_type,
        exception_message=exception_msg,
        function=getattr(retry_state.fn, "__name__", "unknown") if retry_state.fn else "unknown",
    )


# =============================================================================
# Retry Decorators
# =============================================================================


def create_retry_decorator(
    retryable_exceptions: tuple[type[Exception], ...],
    max_attempts: int = RetryConfig.MAX_ATTEMPTS,
    min_wait: float = RetryConfig.MIN_WAIT,
    max_wait: float = RetryConfig.MAX_WAIT,
    jitter: float = RetryConfig.JITTER,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Create a custom retry decorator with specified configuration.

    Args:
        retryable_exceptions: Tuple of exception types to retry on.
        max_attempts: Maximum number of attempts.
        min_wait: Minimum wait time between retries.
        max_wait: Maximum wait time between retries.
        jitter: Maximum jitter to add to wait time.

    Returns:
        A retry decorator configured with the specified parameters.
    """
    return retry(
        retry=retry_if_exception_type(retryable_exceptions),
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential_jitter(
            initial=min_wait,
            max=max_wait,
            jitter=jitter,
        ),
        before_sleep=log_retry_attempt,
        reraise=True,
    )


# Pre-configured LLM retry decorator
llm_retry = create_retry_decorator(
    retryable_exceptions=LLM_RETRYABLE_EXCEPTIONS,
    max_attempts=RetryConfig.MAX_ATTEMPTS,
    min_wait=RetryConfig.MIN_WAIT,
    max_wait=RetryConfig.MAX_WAIT,
)
"""Retry decorator for LLM API calls.

Retries on transient errors with exponential backoff.
- Max attempts: 3
- Wait: 1-30 seconds with jitter
- Retries on: LLMError, TimeoutError, ConnectionError, etc.

Usage:
    @llm_retry
    async def call_llm():
        ...
"""


# Pre-configured embedding retry decorator
embedding_retry = create_retry_decorator(
    retryable_exceptions=EMBEDDING_RETRYABLE_EXCEPTIONS,
    max_attempts=RetryConfig.MAX_ATTEMPTS,
    min_wait=RetryConfig.MIN_WAIT,
    max_wait=RetryConfig.MAX_WAIT,
)
"""Retry decorator for embedding generation calls.

Retries on transient errors with exponential backoff.
- Max attempts: 3
- Wait: 1-30 seconds with jitter
- Retries on: EmbeddingError, VectorSearchError, TimeoutError, etc.

Usage:
    @embedding_retry
    async def generate_embedding():
        ...
"""


# Pre-configured service retry decorator
service_retry = create_retry_decorator(
    retryable_exceptions=SERVICE_RETRYABLE_EXCEPTIONS,
    max_attempts=RetryConfig.MAX_ATTEMPTS,
    min_wait=RetryConfig.MIN_WAIT,
    max_wait=RetryConfig.MAX_WAIT,
)
"""Retry decorator for external service calls.

Retries on transient errors with exponential backoff.
- Max attempts: 3
- Wait: 1-30 seconds with jitter
- Retries on: ServiceUnavailableError, TimeoutError, ConnectionError, etc.

Usage:
    @service_retry
    async def call_external_service():
        ...
"""


# =============================================================================
# Context Manager for Programmatic Retry
# =============================================================================


class RetryContext:
    """Context manager for programmatic retry control.

    Use this when you need more control over retry behavior than
    a decorator provides.

    Usage:
        async with RetryContext(
            retryable_exceptions=(TimeoutError,),
            max_attempts=5,
        ) as retry:
            async for attempt in retry:
                with attempt:
                    await some_operation()

    Attributes:
        retryable_exceptions: Tuple of exception types to retry on.
        max_attempts: Maximum number of attempts.
        min_wait: Minimum wait time between retries.
        max_wait: Maximum wait time between retries.
    """

    def __init__(
        self,
        retryable_exceptions: tuple[type[Exception], ...] = LLM_RETRYABLE_EXCEPTIONS,
        max_attempts: int = RetryConfig.MAX_ATTEMPTS,
        min_wait: float = RetryConfig.MIN_WAIT,
        max_wait: float = RetryConfig.MAX_WAIT,
        jitter: float = RetryConfig.JITTER,
    ) -> None:
        self.retryable_exceptions = retryable_exceptions
        self.max_attempts = max_attempts
        self.min_wait = min_wait
        self.max_wait = max_wait
        self.jitter = jitter
        self._retrying: AsyncRetrying | None = None

    async def __aenter__(self) -> "AsyncRetrying":
        """Enter the retry context."""
        self._retrying = AsyncRetrying(
            retry=retry_if_exception_type(self.retryable_exceptions),
            stop=stop_after_attempt(self.max_attempts),
            wait=wait_exponential_jitter(
                initial=self.min_wait,
                max=self.max_wait,
                jitter=self.jitter,
            ),
            before_sleep=log_retry_attempt,
            reraise=True,
        )
        return self._retrying

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        """Exit the retry context."""
        return False


# =============================================================================
# Utility Functions
# =============================================================================


def is_retryable_exception(exception: Exception) -> bool:
    """Check if an exception is retryable.

    Args:
        exception: The exception to check.

    Returns:
        True if the exception type is in the retryable list.
    """
    return isinstance(exception, LLM_RETRYABLE_EXCEPTIONS)


def get_retry_config() -> dict[str, Any]:
    """Get the current retry configuration as a dictionary.

    Returns:
        Dictionary containing retry configuration values.
    """
    return {
        "max_attempts": RetryConfig.MAX_ATTEMPTS,
        "min_wait": RetryConfig.MIN_WAIT,
        "max_wait": RetryConfig.MAX_WAIT,
        "jitter": RetryConfig.JITTER,
        "exponential_base": RetryConfig.EXPONENTIAL_BASE,
    }


# Export public interface
__all__ = [
    "llm_retry",
    "embedding_retry",
    "service_retry",
    "create_retry_decorator",
    "RetryConfig",
    "RetryContext",
    "is_retryable_exception",
    "get_retry_config",
    "LLM_RETRYABLE_EXCEPTIONS",
    "EMBEDDING_RETRYABLE_EXCEPTIONS",
    "SERVICE_RETRYABLE_EXCEPTIONS",
]
