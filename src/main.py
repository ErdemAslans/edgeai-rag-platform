"""Main FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import structlog

from src.config import settings
from src.api.middleware import RequestLoggingMiddleware
from src.api.v1.router import api_router
from src.core.exceptions import EdgeAIException, RateLimitError
from src.core.logging import setup_logging
from src.db.session import init_db, close_db

logger = structlog.get_logger()

# Global cache service instance
_cache_service: Optional[Any] = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup and shutdown events."""
    global _cache_service
    
    # Startup
    setup_logging()
    logger.info(
        "Starting EdgeAI RAG Platform",
        environment=settings.ENVIRONMENT,
        debug=settings.DEBUG,
    )
    
    # Initialize database connection pool
    await init_db()
    logger.info("Database connection pool initialized")
    
    # Initialize Redis cache if enabled
    if settings.REDIS_ENABLED:
        from src.services.cache_service import get_cache_service
        _cache_service = await get_cache_service()
        await _cache_service.connect(settings.REDIS_URL)
        logger.info("Redis cache service initialized")
    
    # Initialize storage service
    from src.services.storage_service import get_storage_service
    storage = get_storage_service()
    if settings.STORAGE_BACKEND == "s3" and settings.S3_BUCKET_NAME:
        storage.configure(
            backend="s3",
            bucket_name=settings.S3_BUCKET_NAME,
            region=settings.S3_REGION,
            access_key=settings.S3_ACCESS_KEY,
            secret_key=settings.S3_SECRET_KEY,
            endpoint_url=settings.S3_ENDPOINT_URL,
        )
    elif settings.STORAGE_BACKEND == "gcs" and settings.GCS_BUCKET_NAME:
        storage.configure(
            backend="gcs",
            bucket_name=settings.GCS_BUCKET_NAME,
            credentials_path=settings.GCS_CREDENTIALS_PATH,
        )
    else:
        storage.configure(backend="local", base_dir=settings.UPLOAD_DIR)
    
    logger.info("Storage service initialized", backend=settings.STORAGE_BACKEND)
    
    yield
    
    # Shutdown
    logger.info("Shutting down EdgeAI RAG Platform")
    
    # Disconnect Redis
    if _cache_service:
        await _cache_service.disconnect()
        logger.info("Redis cache service disconnected")
    
    await close_db()
    logger.info("Database connections closed")


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description="""
EdgeAI - Multi-Agent RAG Platform

A hybrid edge-cloud platform for:
- Document processing with RAG (Retrieval Augmented Generation)
- Multiple AI agents (Summarizer, SQL Generator, Document Analyzer)
- Vector similarity search using pgvector
- JWT-based authentication

## Features

- **Document Management**: Upload, process, and search documents
- **Vector Search**: Semantic search using sentence-transformers embeddings
- **Multi-Agent System**: Specialized agents for different tasks
- **RAG Pipeline**: Context-aware responses using retrieved documents
- **Rate Limiting**: Configurable rate limiting per endpoint
- **Metrics**: Prometheus metrics for monitoring
        """,
        version="1.0.0",
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        docs_url=f"{settings.API_V1_PREFIX}/docs",
        redoc_url=f"{settings.API_V1_PREFIX}/redoc",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add request logging middleware
    app.add_middleware(RequestLoggingMiddleware)
    
    # Add rate limiting middleware if enabled
    if settings.RATE_LIMIT_ENABLED:
        from src.api.rate_limiter import RateLimitMiddleware
        app.add_middleware(RateLimitMiddleware, cache_service=_cache_service)
        logger.info("Rate limiting middleware enabled")

    # Include API routes
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    
    # Metrics endpoint
    if settings.METRICS_ENABLED:
        from src.core.metrics import get_metrics_response

        @app.get(settings.METRICS_PATH, tags=["Monitoring"])
        async def metrics() -> Response:
            """Prometheus metrics endpoint."""
            content, content_type = get_metrics_response()
            return Response(content=content, media_type=content_type)

        logger.info("Metrics endpoint enabled", path=settings.METRICS_PATH)

    # ==========================================================================
    # Exception Handlers
    # ==========================================================================

    @app.exception_handler(EdgeAIException)
    async def edgeai_exception_handler(
        request: Request, exc: EdgeAIException
    ) -> JSONResponse:
        """Handle all EdgeAI custom exceptions with proper error format.

        Uses the exception's http_status and to_dict() for consistent responses.
        Logs the error with context and includes retryable hint in response.
        """
        logger.warning(
            "EdgeAI exception",
            error_code=exc.code,
            error_message=exc.message,
            http_status=exc.http_status,
            retryable=exc.retryable,
            path=request.url.path,
            method=request.method,
            details=exc.details,
        )
        response_content = exc.to_dict()
        # Add retryable hint for clients
        response_content["error"]["retryable"] = exc.retryable

        headers = {}
        # Add Retry-After header for rate limit errors
        if isinstance(exc, RateLimitError) and exc.details.get("retry_after"):
            headers["Retry-After"] = str(exc.details["retry_after"])

        return JSONResponse(
            status_code=exc.http_status,
            content=response_content,
            headers=headers if headers else None,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Handle Pydantic/FastAPI request validation errors.

        Converts validation errors to our standard error format for consistency.
        """
        errors = exc.errors()
        logger.warning(
            "Request validation error",
            path=request.url.path,
            method=request.method,
            errors=errors,
        )
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": {"validation_errors": errors},
                    "retryable": False,
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """Handle Starlette HTTP exceptions with our standard format.

        Ensures HTTP exceptions from FastAPI/Starlette use consistent error format.
        """
        logger.warning(
            "HTTP exception",
            status_code=exc.status_code,
            detail=exc.detail,
            path=request.url.path,
            method=request.method,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": "HTTP_ERROR",
                    "message": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
                    "details": {},
                    "retryable": exc.status_code >= 500,
                }
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Handle all unhandled exceptions with proper error format.

        This is the fallback handler for unexpected errors. It logs the full
        exception for debugging while returning a safe error message to clients.
        """
        logger.error(
            "Unhandled exception",
            error=str(exc),
            error_type=type(exc).__name__,
            path=request.url.path,
            method=request.method,
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                    "details": {},
                    "retryable": True,
                }
            },
        )

    return app


# Create application instance
app = create_application()


@app.get("/", tags=["Root"])
async def root() -> Dict[str, str]:
    """Root endpoint - basic API info."""
    return {
        "name": settings.PROJECT_NAME,
        "version": "1.0.0",
        "status": "running",
        "docs": f"{settings.API_V1_PREFIX}/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info",
    )