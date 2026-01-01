"""Main FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from src.config import settings
from src.api.middleware import RequestLoggingMiddleware
from src.api.v1.router import api_router
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

    # Global exception handler to ensure CORS headers are always sent
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle all unhandled exceptions with proper CORS headers."""
        logger.error(
            "Unhandled exception",
            error=str(exc),
            path=request.url.path,
            method=request.method,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
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