"""Logging configuration using structlog.

This module provides comprehensive structured logging for the EdgeAI RAG Platform
with JSON output format for production and console format for development.

Features:
- JSON-formatted logs with timestamp, level, service, request_id
- Correlation ID tracking across request lifecycle
- Call site information (file, function, line) for debugging
- Environment and service metadata in every log entry
- Configurable log levels via environment variable
"""

import logging
import socket
import sys
from typing import Any, Dict, Optional

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars, get_contextvars

from src.config import settings


def _add_service_context(
    logger: logging.Logger,
    method_name: str,
    event_dict: Dict[str, Any],
) -> Dict[str, Any]:
    """Add service-level context to every log entry.

    This processor adds:
    - service: Application name from settings
    - environment: Current environment (development/production)
    - hostname: Machine hostname for distributed tracing

    Args:
        logger: The wrapped logger object
        method_name: Name of the log method called
        event_dict: Current log event dictionary

    Returns:
        Updated event dictionary with service context
    """
    event_dict["service"] = settings.APP_NAME
    event_dict["environment"] = settings.APP_ENV
    # Add hostname for distributed system debugging
    if "hostname" not in event_dict:
        event_dict["hostname"] = socket.gethostname()
    return event_dict


def _add_call_site_info(
    logger: logging.Logger,
    method_name: str,
    event_dict: Dict[str, Any],
) -> Dict[str, Any]:
    """Add call site information for debugging.

    Adds file, function, and line number to log entries when
    running in JSON mode for easier debugging in production.

    Args:
        logger: The wrapped logger object
        method_name: Name of the log method called
        event_dict: Current log event dictionary

    Returns:
        Updated event dictionary with call site info
    """
    # Call site info is added by CallsiteParameterAdder processor
    # This processor just ensures the format is consistent
    return event_dict


def setup_logging() -> None:
    """Configure structured logging for the application.

    Sets up structlog with:
    - JSON or console renderer based on LOG_FORMAT setting
    - Request ID and correlation tracking via contextvars
    - Service metadata (name, environment, hostname)
    - Configurable log level from settings
    - Call site information for debugging
    - Exception formatting for production logs
    """
    # Determine log level from settings (default: INFO)
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
        force=True,  # Override any existing configuration
    )

    # Shared processors for all logging
    shared_processors: list[Any] = [
        # Merge context variables (request_id, correlation_id, etc.)
        structlog.contextvars.merge_contextvars,
        # Add standard log metadata
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        # Add service-level context
        _add_service_context,
        # Add ISO format timestamp
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
        # Render stack info for debugging
        structlog.processors.StackInfoRenderer(),
        # Decode unicode strings
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.LOG_FORMAT == "json":
        # JSON format for production
        # Add call site information (file, function, line)
        shared_processors.insert(
            -2,  # Insert before StackInfoRenderer
            structlog.processors.CallsiteParameterAdder(
                parameters=[
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                ]
            ),
        )
        # Format exception info as string for JSON serialization
        shared_processors.append(structlog.processors.format_exc_info)
        # Configure JSONRenderer with production-friendly options
        renderer: Any = structlog.processors.JSONRenderer(
            ensure_ascii=False,  # Allow unicode characters
            sort_keys=True,  # Consistent key ordering for log parsing
        )
    else:
        # Console format for development
        # Use colored console output for better readability
        renderer = structlog.dev.ConsoleRenderer(
            colors=True,
            exception_formatter=structlog.dev.RichTracebackFormatter(
                show_locals=settings.DEBUG,
            ) if settings.DEBUG else structlog.dev.plain_traceback,
        )

    # Configure structlog
    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure formatter for stdlib logging integration
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    # Apply formatter to root logger
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.setFormatter(formatter)

    # Set log levels for noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name, typically __name__ of the calling module

    Returns:
        A BoundLogger instance with the given name
    """
    return structlog.get_logger(name)


def bind_context(**kwargs: Any) -> None:
    """Bind context variables to the current logging context.

    Bound variables will be included in all subsequent log entries
    within the current async context (request lifecycle).

    Example:
        bind_context(user_id="123", document_id="doc-456")
        logger.info("Processing document")  # Will include user_id and document_id

    Args:
        **kwargs: Key-value pairs to bind to the logging context
    """
    bind_contextvars(**kwargs)


def clear_context() -> None:
    """Clear all context variables from the current logging context.

    Call this at the end of a request or when starting a new
    operation that shouldn't inherit previous context.
    """
    clear_contextvars()


def get_current_context() -> Dict[str, Any]:
    """Get the current logging context variables.

    Returns:
        Dictionary of currently bound context variables
    """
    return get_contextvars()


def with_context(logger: structlog.stdlib.BoundLogger, **kwargs: Any) -> structlog.stdlib.BoundLogger:
    """Create a new logger with additional bound context.

    Unlike bind_context(), this returns a new logger instance
    with the context bound locally, not affecting the global context.

    Example:
        doc_logger = with_context(logger, document_id="doc-456")
        doc_logger.info("Processing")  # Includes document_id
        logger.info("Other log")  # Does NOT include document_id

    Args:
        logger: The logger to bind context to
        **kwargs: Key-value pairs to bind

    Returns:
        New BoundLogger with the additional context
    """
    return logger.bind(**kwargs)