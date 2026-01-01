"""Dependency Injection container for EdgeAI RAG platform.

This module provides a lightweight DI container for managing service lifecycles.
It supports both singleton services (shared across requests) and request-scoped
services (created per request with database sessions).

Usage:
    from src.core.di import DIContainer, get_container

    # Get singleton container
    container = get_container()

    # Register a singleton service
    container.register_singleton("llm_service", LLMService())

    # Register a factory for request-scoped services
    container.register_factory("document_service", lambda session: DocumentService(session))

    # Resolve services
    llm = container.resolve("llm_service")
    doc_service = container.resolve_with_session("document_service", session)
"""

from functools import lru_cache
from typing import Any, Callable, Dict, Optional, TypeVar, Type, cast

from sqlalchemy.ext.asyncio import AsyncSession
import structlog

logger = structlog.get_logger()

T = TypeVar("T")


class DIContainer:
    """Dependency injection container for service management.

    This container manages two types of services:
    - Singletons: Created once and shared across all requests (e.g., LLM clients)
    - Factories: Create new instances per request, optionally with session (e.g., DocumentService)

    The container supports easy testing by allowing services to be overridden
    without changing application code.

    Attributes:
        _singletons: Dictionary of registered singleton instances.
        _factories: Dictionary of registered factory functions.
        _overrides: Dictionary of test overrides for mocking.
    """

    def __init__(self) -> None:
        """Initialize the DI container with empty registries."""
        self._singletons: Dict[str, Any] = {}
        self._factories: Dict[str, Callable[..., Any]] = {}
        self._overrides: Dict[str, Any] = {}

    def register_singleton(self, name: str, instance: Any) -> None:
        """Register a singleton service instance.

        Singleton services are created once and shared across all requests.
        Use for expensive-to-create services like LLM clients, embedding models.

        Args:
            name: Unique identifier for the service.
            instance: The singleton service instance.

        Example:
            container.register_singleton("llm_service", LLMService())
        """
        self._singletons[name] = instance

    def register_factory(
        self,
        name: str,
        factory: Callable[..., T],
    ) -> None:
        """Register a factory function for creating service instances.

        Factory functions are called each time a service is resolved.
        Use for request-scoped services that need database sessions.

        Args:
            name: Unique identifier for the service.
            factory: Callable that creates the service instance.
                    For session-scoped services, factory receives AsyncSession.

        Example:
            container.register_factory(
                "document_service",
                lambda session: DocumentService(session)
            )
        """
        self._factories[name] = factory

    def resolve(self, name: str) -> Any:
        """Resolve a singleton service by name.

        First checks for test overrides, then returns the registered singleton.

        Args:
            name: The service identifier.

        Returns:
            The singleton service instance.

        Raises:
            KeyError: If the service is not registered.

        Example:
            llm = container.resolve("llm_service")
        """
        if name in self._overrides:
            return self._overrides[name]

        if name not in self._singletons:
            raise KeyError(
                f"Service '{name}' not registered as singleton. "
                f"Available singletons: {list(self._singletons.keys())}"
            )

        return self._singletons[name]

    def resolve_with_session(self, name: str, session: AsyncSession) -> Any:
        """Resolve a request-scoped service with a database session.

        Creates a new service instance using the registered factory,
        passing the session for database operations.

        Args:
            name: The service identifier.
            session: The async database session for this request.

        Returns:
            A new service instance.

        Raises:
            KeyError: If the factory is not registered.

        Example:
            doc_service = container.resolve_with_session("document_service", session)
        """
        if name in self._overrides:
            override = self._overrides[name]
            if callable(override):
                return override(session)
            return override

        if name not in self._factories:
            raise KeyError(
                f"Factory '{name}' not registered. "
                f"Available factories: {list(self._factories.keys())}"
            )

        return self._factories[name](session)

    def resolve_factory(self, name: str) -> Any:
        """Resolve a service using its factory without a session.

        Use for factories that don't require database sessions.

        Args:
            name: The service identifier.

        Returns:
            A new service instance.

        Raises:
            KeyError: If the factory is not registered.
        """
        if name in self._overrides:
            override = self._overrides[name]
            if callable(override):
                return override()
            return override

        if name not in self._factories:
            raise KeyError(
                f"Factory '{name}' not registered. "
                f"Available factories: {list(self._factories.keys())}"
            )

        return self._factories[name]()

    def override(self, name: str, mock: Any) -> None:
        """Override a service with a mock for testing.

        This allows tests to inject mock services without modifying
        application code. Overrides take precedence over registered services.

        Args:
            name: The service identifier to override.
            mock: The mock service instance or factory.

        Example:
            container.override("llm_service", MockLLMService())
            container.override("document_service", lambda s: MockDocumentService(s))
        """
        self._overrides[name] = mock

    def clear_overrides(self) -> None:
        """Clear all test overrides.

        Call this in test teardown to reset the container to normal state.
        """
        self._overrides.clear()

    def clear_override(self, name: str) -> None:
        """Clear a specific test override.

        Args:
            name: The service identifier to clear.
        """
        self._overrides.pop(name, None)

    def has_singleton(self, name: str) -> bool:
        """Check if a singleton is registered.

        Args:
            name: The service identifier.

        Returns:
            True if the singleton is registered.
        """
        return name in self._singletons

    def has_factory(self, name: str) -> bool:
        """Check if a factory is registered.

        Args:
            name: The service identifier.

        Returns:
            True if the factory is registered.
        """
        return name in self._factories

    def is_overridden(self, name: str) -> bool:
        """Check if a service is currently overridden.

        Args:
            name: The service identifier.

        Returns:
            True if an override is active for this service.
        """
        return name in self._overrides

    def list_singletons(self) -> list[str]:
        """Get list of registered singleton names.

        Returns:
            List of singleton service identifiers.
        """
        return list(self._singletons.keys())

    def list_factories(self) -> list[str]:
        """Get list of registered factory names.

        Returns:
            List of factory service identifiers.
        """
        return list(self._factories.keys())

    def reset(self) -> None:
        """Reset the container to initial state.

        Clears all registrations and overrides. Use with caution
        as this will require re-registering all services.
        """
        self._singletons.clear()
        self._factories.clear()
        self._overrides.clear()


# Global container instance
_container: Optional[DIContainer] = None


@lru_cache(maxsize=1)
def get_container() -> DIContainer:
    """Get the global singleton DI container.

    This function returns the same container instance across all calls,
    making it safe to use in dependency injection without state issues.

    Returns:
        The global DIContainer instance.

    Example:
        container = get_container()
        llm = container.resolve("llm_service")
    """
    global _container
    if _container is None:
        _container = DIContainer()
    return _container


def reset_container() -> None:
    """Reset the global container for testing purposes.

    This clears the container cache and resets all registrations.
    Should only be used in tests.
    """
    global _container
    get_container.cache_clear()
    _container = None


def register_services() -> DIContainer:
    """Register all application services in the DI container.

    This function initializes and registers both singleton services
    (LLM, embedding) and request-scoped factories (document service).

    Should be called once during application startup.

    Returns:
        The configured DIContainer instance.

    Example:
        # In application lifespan:
        container = register_services()
    """
    container = get_container()

    # Register singleton services (expensive to create, shared across requests)
    _register_singleton_services(container)

    # Register request-scoped factories (created per request with session)
    _register_factory_services(container)

    logger.info(
        "Services registered in DI container",
        singletons=container.list_singletons(),
        factories=container.list_factories(),
    )

    return container


def _register_singleton_services(container: DIContainer) -> None:
    """Register singleton services that are shared across all requests.

    These services are created once and reused. They include:
    - LLM service (Groq/Ollama client)
    - Embedding service (sentence-transformers model)

    Args:
        container: The DI container instance.
    """
    # Import services lazily to avoid circular imports
    from src.services.llm_service import LLMService
    from src.services.embedding_service import EmbeddingService

    # LLM service - creates and maintains LLM client connection
    try:
        llm_service = LLMService()
        container.register_singleton("llm_service", llm_service)
        logger.info(
            "LLM service registered",
            provider=llm_service.get_provider(),
            model=llm_service.get_model(),
        )
    except Exception as e:
        logger.warning(
            "LLM service registration failed - service will be unavailable",
            error=str(e),
        )

    # Embedding service - loads and manages embedding model
    try:
        embedding_service = EmbeddingService()
        container.register_singleton("embedding_service", embedding_service)
        logger.info(
            "Embedding service registered",
            model=embedding_service.get_model_name(),
            dimension=embedding_service.get_embedding_dimension(),
        )
    except Exception as e:
        logger.warning(
            "Embedding service registration failed - service will be unavailable",
            error=str(e),
        )


def _register_factory_services(container: DIContainer) -> None:
    """Register factory functions for request-scoped services.

    These services are created per request and require a database session.
    They include:
    - Document service (document CRUD operations)

    Args:
        container: The DI container instance.
    """
    # Import services lazily to avoid circular imports
    from src.services.document_service import DocumentService

    # Document service - requires session for database operations
    container.register_factory(
        "document_service",
        lambda session: DocumentService(session),
    )
    logger.debug("Document service factory registered")
