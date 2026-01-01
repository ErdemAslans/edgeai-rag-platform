"""Custom exceptions for the EdgeAI RAG platform.

This module provides a comprehensive exception hierarchy for domain-specific
error handling. All exceptions include error codes, user-friendly messages,
HTTP status codes, and optional detailed context.

Exception Hierarchy:
    EdgeAIException (base)
    ├── AuthError
    │   ├── AuthenticationError
    │   └── AuthorizationError
    ├── ValidationError
    ├── NotFoundError
    │   ├── UserNotFoundError
    │   └── DocumentNotFoundError
    ├── DatabaseError
    ├── LLMError
    │   └── EmbeddingError
    ├── DocumentProcessingError
    ├── AgentError
    ├── VectorSearchError
    ├── StorageError
    └── RateLimitError
"""

from typing import Any, Dict, Optional


class EdgeAIException(Exception):
    """Base exception for EdgeAI platform.

    All custom exceptions inherit from this class, providing consistent
    error handling with codes, messages, HTTP status, and additional details.

    Attributes:
        message: Human-readable error message.
        code: Machine-readable error code for programmatic handling.
        details: Additional context about the error.
        http_status: HTTP status code for API responses.
        retryable: Whether the operation can be retried.
    """

    http_status: int = 500
    retryable: bool = False

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to a dictionary for API responses."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


# =============================================================================
# Authentication & Authorization Errors
# =============================================================================


class AuthError(EdgeAIException):
    """Base class for authentication and authorization errors."""

    http_status: int = 401

    def __init__(
        self,
        message: str = "Authentication or authorization error",
        code: str = "AUTH_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, code=code, details=details)


class AuthenticationError(AuthError):
    """Raised when authentication fails (invalid credentials, expired token, etc.)."""

    http_status: int = 401

    def __init__(
        self,
        message: str = "Authentication failed",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, code="AUTHENTICATION_ERROR", details=details)


class AuthorizationError(AuthError):
    """Raised when user is not authorized to perform an action."""

    http_status: int = 403

    def __init__(
        self,
        message: str = "Not authorized",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, code="AUTHORIZATION_ERROR", details=details)


# =============================================================================
# Validation Errors
# =============================================================================


class ValidationError(EdgeAIException):
    """Raised when input validation fails.

    Use for business rule violations, invalid data formats, constraint failures, etc.
    """

    http_status: int = 422

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        details = details or {}
        if field:
            details["field"] = field
        super().__init__(message, code="VALIDATION_ERROR", details=details)


# =============================================================================
# Resource Not Found Errors
# =============================================================================


class NotFoundError(EdgeAIException):
    """Raised when a resource is not found."""

    http_status: int = 404

    def __init__(
        self,
        resource: str,
        resource_id: Any = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        message = f"{resource} not found"
        if resource_id:
            message = f"{resource} with id '{resource_id}' not found"
        base_details = {"resource": resource, "id": resource_id}
        if details:
            base_details.update(details)
        super().__init__(message, code="NOT_FOUND", details=base_details)


class UserNotFoundError(NotFoundError):
    """Raised when a user is not found."""

    def __init__(
        self,
        message: str = "User not found",
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        # Call EdgeAIException directly to use custom message format
        details = details or {}
        if user_id:
            details["user_id"] = user_id
        EdgeAIException.__init__(
            self, message, code="USER_NOT_FOUND", details=details
        )


class DocumentNotFoundError(NotFoundError):
    """Raised when a document is not found."""

    def __init__(
        self,
        message: str = "Document not found",
        document_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        details = details or {}
        if document_id:
            details["document_id"] = document_id
        EdgeAIException.__init__(
            self, message, code="DOCUMENT_NOT_FOUND", details=details
        )


class UserAlreadyExistsError(EdgeAIException):
    """Raised when trying to create a user that already exists."""

    http_status: int = 409

    def __init__(
        self,
        message: str = "User already exists",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, code="USER_ALREADY_EXISTS", details=details)


# =============================================================================
# Database Errors
# =============================================================================


class DatabaseError(EdgeAIException):
    """Raised when database operations fail.

    Includes connection errors, query failures, constraint violations, etc.
    """

    http_status: int = 500
    retryable: bool = True  # Connection issues may be transient

    def __init__(
        self,
        message: str = "Database operation failed",
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        details = details or {}
        if operation:
            details["operation"] = operation
        super().__init__(message, code="DATABASE_ERROR", details=details)


class ConnectionError(DatabaseError):
    """Raised when database connection fails."""

    def __init__(
        self,
        message: str = "Database connection failed",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, operation="connect", details=details)
        self.code = "DATABASE_CONNECTION_ERROR"


class TransactionError(DatabaseError):
    """Raised when a database transaction fails."""

    def __init__(
        self,
        message: str = "Transaction failed",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, operation="transaction", details=details)
        self.code = "DATABASE_TRANSACTION_ERROR"


# =============================================================================
# LLM & AI Service Errors
# =============================================================================


class LLMError(EdgeAIException):
    """Raised when LLM operation fails.

    Covers errors from Groq, Ollama, or other LLM providers.
    """

    http_status: int = 503
    retryable: bool = True  # LLM errors are often transient

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        details = details or {}
        if provider:
            details["provider"] = provider
        super().__init__(message, code="LLM_ERROR", details=details)


class LLMTimeoutError(LLMError):
    """Raised when LLM request times out."""

    retryable: bool = True

    def __init__(
        self,
        message: str = "LLM request timed out",
        provider: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        details = details or {}
        if timeout_seconds:
            details["timeout_seconds"] = timeout_seconds
        super().__init__(message, provider=provider, details=details)
        self.code = "LLM_TIMEOUT_ERROR"


class LLMRateLimitError(LLMError):
    """Raised when LLM provider rate limit is exceeded."""

    http_status: int = 429
    retryable: bool = True

    def __init__(
        self,
        message: str = "LLM rate limit exceeded",
        provider: Optional[str] = None,
        retry_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        details = details or {}
        if retry_after:
            details["retry_after"] = retry_after
        super().__init__(message, provider=provider, details=details)
        self.code = "LLM_RATE_LIMIT_ERROR"


class EmbeddingError(LLMError):
    """Raised when embedding generation fails."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, provider=provider, details=details)
        self.code = "EMBEDDING_ERROR"


# =============================================================================
# Document & Processing Errors
# =============================================================================


class DocumentProcessingError(EdgeAIException):
    """Raised when document processing fails."""

    http_status: int = 422

    def __init__(
        self,
        message: str,
        document_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        details = details or {}
        if document_id:
            details["document_id"] = document_id
        super().__init__(message, code="DOCUMENT_PROCESSING_ERROR", details=details)


class UnsupportedFileTypeError(DocumentProcessingError):
    """Raised when an unsupported file type is uploaded."""

    def __init__(
        self,
        file_type: str,
        supported_types: Optional[list[str]] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        message = f"Unsupported file type: {file_type}"
        details = details or {}
        details["file_type"] = file_type
        if supported_types:
            details["supported_types"] = supported_types
            message += f". Supported types: {', '.join(supported_types)}"
        super().__init__(message, details=details)
        self.code = "UNSUPPORTED_FILE_TYPE"


class FileTooLargeError(DocumentProcessingError):
    """Raised when an uploaded file exceeds size limits."""

    def __init__(
        self,
        file_size: int,
        max_size: int,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        message = f"File size ({file_size} bytes) exceeds maximum allowed ({max_size} bytes)"
        details = details or {}
        details["file_size"] = file_size
        details["max_size"] = max_size
        super().__init__(message, details=details)
        self.code = "FILE_TOO_LARGE"


# =============================================================================
# Agent & Orchestration Errors
# =============================================================================


class AgentError(EdgeAIException):
    """Raised when agent execution fails."""

    http_status: int = 500

    def __init__(
        self,
        message: str,
        agent_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        details = details or {}
        if agent_name:
            details["agent_name"] = agent_name
        super().__init__(message, code="AGENT_ERROR", details=details)


# =============================================================================
# Search & Vector Errors
# =============================================================================


class VectorSearchError(EdgeAIException):
    """Raised when vector search fails."""

    http_status: int = 500
    retryable: bool = True

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, code="VECTOR_SEARCH_ERROR", details=details)


# =============================================================================
# Storage Errors
# =============================================================================


class StorageError(EdgeAIException):
    """Raised when storage operations fail."""

    http_status: int = 500
    retryable: bool = True

    def __init__(
        self,
        message: str = "Storage operation failed",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, code="STORAGE_ERROR", details=details)


# =============================================================================
# Rate Limiting Errors
# =============================================================================


class RateLimitError(EdgeAIException):
    """Raised when rate limit is exceeded."""

    http_status: int = 429
    retryable: bool = True

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        details = details or {}
        if retry_after:
            details["retry_after"] = retry_after
        super().__init__(message, code="RATE_LIMIT_ERROR", details=details)


# =============================================================================
# Configuration Errors
# =============================================================================


class ConfigurationError(EdgeAIException):
    """Raised when there's a configuration problem."""

    http_status: int = 500
    retryable: bool = False

    def __init__(
        self,
        message: str = "Configuration error",
        config_key: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        details = details or {}
        if config_key:
            details["config_key"] = config_key
        super().__init__(message, code="CONFIGURATION_ERROR", details=details)


# =============================================================================
# Service Errors
# =============================================================================


class ServiceUnavailableError(EdgeAIException):
    """Raised when an external service is unavailable."""

    http_status: int = 503
    retryable: bool = True

    def __init__(
        self,
        service_name: str,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        if message is None:
            message = f"Service '{service_name}' is unavailable"
        details = details or {}
        details["service_name"] = service_name
        super().__init__(message, code="SERVICE_UNAVAILABLE", details=details)
