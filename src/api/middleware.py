"""Custom middleware for FastAPI application."""

import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars

logger = structlog.get_logger()

# Header names for request ID propagation
REQUEST_ID_HEADER = "X-Request-ID"
CORRELATION_ID_HEADER = "X-Correlation-ID"


def get_request_id(request: Request) -> str | None:
    """Get the request ID from the current request.

    Args:
        request: The FastAPI request object

    Returns:
        The request ID if set by RequestIDMiddleware, None otherwise
    """
    return getattr(request.state, "request_id", None)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware for request ID generation and correlation tracking.

    This middleware:
    - Generates a unique request ID for each request (or uses incoming X-Request-ID)
    - Binds the request ID to structlog context for automatic inclusion in all logs
    - Stores the request ID in request.state for access by handlers
    - Adds X-Request-ID header to responses for client correlation
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Clear any existing context from previous requests
        clear_contextvars()

        # Get request ID from header or generate new one
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())

        # Store in request state for access by route handlers
        request.state.request_id = request_id

        # Bind to structlog context - all logs will automatically include this
        bind_contextvars(request_id=request_id)

        # Process the request
        response = await call_next(request)

        # Add request ID to response headers for client correlation
        response.headers[REQUEST_ID_HEADER] = request_id

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging all requests with timing information.

    Note: This middleware works best when used with RequestIDMiddleware,
    which provides request_id in request.state and binds it to structlog context.
    The request_id will be automatically included in all log entries via contextvars.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Use request_id from RequestIDMiddleware if available, otherwise generate
        request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())

        # Ensure request_id is in state (for cases where RequestIDMiddleware isn't used)
        if not hasattr(request.state, "request_id"):
            request.state.request_id = request_id
            bind_contextvars(request_id=request_id)

        # Also maintain correlation_id for backward compatibility
        request.state.correlation_id = request_id

        # Start timing
        start_time = time.perf_counter()

        # Log request (request_id is automatically included via contextvars)
        await logger.ainfo(
            "request_started",
            method=request.method,
            path=request.url.path,
            query_params=str(request.query_params),
            client_host=request.client.host if request.client else None,
        )

        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            # Log exception (request_id automatically included)
            process_time = time.perf_counter() - start_time
            await logger.aerror(
                "request_failed",
                method=request.method,
                path=request.url.path,
                process_time_ms=round(process_time * 1000, 2),
                error=str(e),
            )
            raise

        # Calculate processing time
        process_time = time.perf_counter() - start_time

        # Add headers for response correlation
        response.headers[CORRELATION_ID_HEADER] = request_id
        response.headers["X-Process-Time"] = str(round(process_time * 1000, 2))

        # Log response (request_id automatically included)
        await logger.ainfo(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            process_time_ms=round(process_time * 1000, 2),
        )

        return response


class CORSDebugMiddleware(BaseHTTPMiddleware):
    """Middleware for debugging CORS issues in development."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method == "OPTIONS":
            await logger.adebug(
                "cors_preflight",
                origin=request.headers.get("origin"),
                method=request.headers.get("access-control-request-method"),
                headers=request.headers.get("access-control-request-headers"),
            )

        response = await call_next(request)
        return response