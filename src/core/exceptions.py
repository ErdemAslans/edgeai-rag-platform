"""Custom exceptions for the application."""

from typing import Optional, Any, Dict


class EdgeAIException(Exception):
    """Base exception for EdgeAI platform."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


class AuthenticationError(EdgeAIException):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="AUTHENTICATION_ERROR", details=details)


class AuthorizationError(EdgeAIException):
    """Raised when user is not authorized to perform an action."""

    def __init__(self, message: str = "Not authorized", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="AUTHORIZATION_ERROR", details=details)


class NotFoundError(EdgeAIException):
    """Raised when a resource is not found."""

    def __init__(self, resource: str, resource_id: Any = None):
        message = f"{resource} not found"
        if resource_id:
            message = f"{resource} with id '{resource_id}' not found"
        super().__init__(message, code="NOT_FOUND", details={"resource": resource, "id": resource_id})


class ValidationError(EdgeAIException):
    """Raised when validation fails."""

    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if field:
            details["field"] = field
        super().__init__(message, code="VALIDATION_ERROR", details=details)


class DocumentProcessingError(EdgeAIException):
    """Raised when document processing fails."""

    def __init__(self, message: str, document_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if document_id:
            details["document_id"] = document_id
        super().__init__(message, code="DOCUMENT_PROCESSING_ERROR", details=details)


class EmbeddingError(EdgeAIException):
    """Raised when embedding generation fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="EMBEDDING_ERROR", details=details)


class LLMError(EdgeAIException):
    """Raised when LLM operation fails."""

    def __init__(self, message: str, provider: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if provider:
            details["provider"] = provider
        super().__init__(message, code="LLM_ERROR", details=details)


class AgentError(EdgeAIException):
    """Raised when agent execution fails."""

    def __init__(self, message: str, agent_name: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if agent_name:
            details["agent_name"] = agent_name
        super().__init__(message, code="AGENT_ERROR", details=details)


class VectorSearchError(EdgeAIException):
    """Raised when vector search fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="VECTOR_SEARCH_ERROR", details=details)


class RateLimitError(EdgeAIException):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: Optional[int] = None):
        details = {}
        if retry_after:
            details["retry_after"] = retry_after
        super().__init__(message, code="RATE_LIMIT_ERROR", details=details)