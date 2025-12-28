"""Custom middleware for FastAPI application."""

import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

import structlog

logger = structlog.get_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging all requests with timing and correlation IDs."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate correlation ID
        correlation_id = str(uuid.uuid4())
        request.state.correlation_id = correlation_id

        # Start timing
        start_time = time.perf_counter()

        # Log request
        await logger.ainfo(
            "request_started",
            correlation_id=correlation_id,
            method=request.method,
            path=request.url.path,
            query_params=str(request.query_params),
            client_host=request.client.host if request.client else None,
        )

        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            # Log exception
            process_time = time.perf_counter() - start_time
            await logger.aerror(
                "request_failed",
                correlation_id=correlation_id,
                method=request.method,
                path=request.url.path,
                process_time_ms=round(process_time * 1000, 2),
                error=str(e),
            )
            raise

        # Calculate processing time
        process_time = time.perf_counter() - start_time

        # Add headers
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Process-Time"] = str(round(process_time * 1000, 2))

        # Log response
        await logger.ainfo(
            "request_completed",
            correlation_id=correlation_id,
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