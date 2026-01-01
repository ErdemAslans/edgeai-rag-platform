"""Prometheus metrics for monitoring."""

import time
from typing import Any, Callable, Optional, TypeVar, cast, Tuple
from functools import wraps

import structlog

logger = structlog.get_logger()

# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])

# Try to import prometheus_client, make it optional
try:
    from prometheus_client import (
        Counter,
        Histogram,
        Gauge,
        Info,
        generate_latest,
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        multiprocess,
        REGISTRY,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    Counter = None
    Histogram = None
    Gauge = None
    Info = None


class MetricsCollector:
    """Prometheus metrics collector for the application."""

    _instance: Optional["MetricsCollector"] = None

    def __new__(cls) -> "MetricsCollector":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not PROMETHEUS_AVAILABLE:
            logger.warning("prometheus_client not installed, metrics disabled")
            self._enabled = False
            return

        if hasattr(self, "_initialized"):
            return

        self._initialized = True
        self._enabled = True

        # Request metrics
        self.http_requests_total = Counter(
            "http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status"],
        )

        self.http_request_duration_seconds = Histogram(
            "http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "endpoint"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
        )

        # Database metrics
        self.db_query_duration_seconds = Histogram(
            "db_query_duration_seconds",
            "Database query duration in seconds",
            ["operation"],
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
        )

        self.db_connections_active = Gauge(
            "db_connections_active",
            "Number of active database connections",
        )

        # LLM metrics
        self.llm_requests_total = Counter(
            "llm_requests_total",
            "Total LLM API requests",
            ["provider", "model", "status"],
        )

        self.llm_request_duration_seconds = Histogram(
            "llm_request_duration_seconds",
            "LLM request duration in seconds",
            ["provider", "model"],
            buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
        )

        self.llm_tokens_total = Counter(
            "llm_tokens_total",
            "Total tokens processed",
            ["provider", "model", "type"],  # values: input/output
        )

        # Document processing metrics
        self.documents_processed_total = Counter(
            "documents_processed_total",
            "Total documents processed",
            ["status"],  # values: success/failed
        )

        self.document_processing_duration_seconds = Histogram(
            "document_processing_duration_seconds",
            "Document processing duration in seconds",
            ["file_type"],
            buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
        )

        self.chunks_created_total = Counter(
            "chunks_created_total",
            "Total document chunks created",
        )

        # Agent metrics
        self.agent_executions_total = Counter(
            "agent_executions_total",
            "Total agent executions",
            ["agent", "framework", "status"],
        )

        self.agent_execution_duration_seconds = Histogram(
            "agent_execution_duration_seconds",
            "Agent execution duration in seconds",
            ["agent", "framework"],
            buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
        )

        # Cache metrics
        self.cache_hits_total = Counter(
            "cache_hits_total",
            "Total cache hits",
        )

        self.cache_misses_total = Counter(
            "cache_misses_total",
            "Total cache misses",
        )

        # Vector search metrics
        self.vector_searches_total = Counter(
            "vector_searches_total",
            "Total vector similarity searches",
        )

        self.vector_search_duration_seconds = Histogram(
            "vector_search_duration_seconds",
            "Vector search duration in seconds",
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0],
        )

        # Application info
        self.app_info = Info(
            "app",
            "Application information",
        )
        self.app_info.info({
            "name": "edgeai-rag-platform",
            "version": "1.0.0",
        })

        logger.info("Prometheus metrics initialized")

    @property
    def enabled(self) -> bool:
        return self._enabled

    def record_http_request(
        self,
        method: str,
        endpoint: str,
        status: int,
        duration: float,
    ) -> None:
        """Record an HTTP request."""
        if not self._enabled:
            return

        self.http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status=str(status),
        ).inc()

        self.http_request_duration_seconds.labels(
            method=method,
            endpoint=endpoint,
        ).observe(duration)

    def record_db_query(self, operation: str, duration: float) -> None:
        """Record a database query."""
        if not self._enabled:
            return

        self.db_query_duration_seconds.labels(operation=operation).observe(duration)

    def record_llm_request(
        self,
        provider: str,
        model: str,
        status: str,
        duration: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        """Record an LLM request."""
        if not self._enabled:
            return

        self.llm_requests_total.labels(
            provider=provider,
            model=model,
            status=status,
        ).inc()

        self.llm_request_duration_seconds.labels(
            provider=provider,
            model=model,
        ).observe(duration)

        if input_tokens > 0:
            self.llm_tokens_total.labels(
                provider=provider,
                model=model,
                type="input",
            ).inc(input_tokens)

        if output_tokens > 0:
            self.llm_tokens_total.labels(
                provider=provider,
                model=model,
                type="output",
            ).inc(output_tokens)

    def record_document_processed(
        self,
        status: str,
        file_type: str,
        duration: float,
        chunks: int = 0,
    ) -> None:
        """Record document processing."""
        if not self._enabled:
            return

        self.documents_processed_total.labels(status=status).inc()
        self.document_processing_duration_seconds.labels(file_type=file_type).observe(duration)

        if chunks > 0:
            self.chunks_created_total.inc(chunks)

    def record_agent_execution(
        self,
        agent: str,
        framework: str,
        status: str,
        duration: float,
    ) -> None:
        """Record agent execution."""
        if not self._enabled:
            return

        self.agent_executions_total.labels(
            agent=agent,
            framework=framework,
            status=status,
        ).inc()

        self.agent_execution_duration_seconds.labels(
            agent=agent,
            framework=framework,
        ).observe(duration)

    def record_cache_hit(self) -> None:
        """Record a cache hit."""
        if not self._enabled:
            return
        self.cache_hits_total.inc()

    def record_cache_miss(self) -> None:
        """Record a cache miss."""
        if not self._enabled:
            return
        self.cache_misses_total.inc()

    def record_vector_search(self, duration: float) -> None:
        """Record a vector search."""
        if not self._enabled:
            return
        self.vector_searches_total.inc()
        self.vector_search_duration_seconds.observe(duration)


# Singleton instance
_metrics: Optional[MetricsCollector] = None


def get_metrics() -> MetricsCollector:
    """Get the metrics collector singleton."""
    global _metrics
    if _metrics is None:
        _metrics = MetricsCollector()
    return _metrics


def get_metrics_response() -> Tuple[bytes | str, str]:
    """Generate Prometheus metrics response."""
    if not PROMETHEUS_AVAILABLE:
        return "# Prometheus client not installed\n", "text/plain"

    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST


# Decorator for timing functions
def timed_operation(operation_type: str, **labels: str) -> Callable[[F], F]:
    """Decorator to time operations and record metrics."""
    def decorator(func: F) -> F:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            metrics = get_metrics()
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                duration = time.perf_counter() - start
                if operation_type == "db":
                    metrics.record_db_query(labels.get("operation", "unknown"), duration)
                elif operation_type == "vector_search":
                    metrics.record_vector_search(duration)
                return result
            except Exception:
                raise

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            metrics = get_metrics()
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                duration = time.perf_counter() - start
                if operation_type == "db":
                    metrics.record_db_query(labels.get("operation", "unknown"), duration)
                return result
            except Exception:
                raise

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        return cast(F, sync_wrapper)
    return decorator
