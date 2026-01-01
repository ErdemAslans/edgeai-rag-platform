"""Document schemas with enhanced Pydantic validators."""

import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# Valid document processing statuses
VALID_DOCUMENT_STATUSES = frozenset({
    "pending",
    "processing",
    "completed",
    "failed",
    "cancelled",
})

# Valid MIME type pattern
MIME_TYPE_PATTERN = re.compile(r"^[a-z]+/[a-z0-9.+-]+$", re.IGNORECASE)

# Allowed filename characters (alphanumeric, dots, underscores, hyphens, spaces)
FILENAME_PATTERN = re.compile(r"^[\w\s.-]+$", re.UNICODE)


class DocumentBase(BaseModel):
    """Base document schema with validation."""

    filename: str
    content_type: str

    @field_validator("filename", mode="before")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """Validate filename is not empty and has valid characters."""
        if not v or not isinstance(v, str):
            raise ValueError("Filename must be a non-empty string")

        # Strip whitespace
        v = v.strip()

        if not v:
            raise ValueError("Filename cannot be empty or whitespace only")

        if len(v) > 255:
            raise ValueError("Filename must be 255 characters or less")

        # Check for path traversal attempts
        if ".." in v or "/" in v or "\\" in v:
            raise ValueError("Filename cannot contain path separators or '..'")

        # Validate allowed characters
        if not FILENAME_PATTERN.match(v):
            raise ValueError(
                "Filename contains invalid characters. "
                "Only alphanumeric, dots, underscores, hyphens, and spaces are allowed"
            )

        return v

    @field_validator("content_type", mode="before")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        """Validate content type is a valid MIME type format."""
        if not v or not isinstance(v, str):
            raise ValueError("Content type must be a non-empty string")

        v = v.strip().lower()

        if not v:
            raise ValueError("Content type cannot be empty")

        # Basic MIME type format validation
        if not MIME_TYPE_PATTERN.match(v):
            raise ValueError(
                f"Invalid content type format: '{v}'. "
                "Expected format: 'type/subtype' (e.g., 'application/pdf')"
            )

        return v


class DocumentUpload(BaseModel):
    """Schema for document upload request with validation."""

    filename: str
    content_type: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("filename", mode="before")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """Validate filename is not empty and has valid characters."""
        if not v or not isinstance(v, str):
            raise ValueError("Filename must be a non-empty string")

        v = v.strip()

        if not v:
            raise ValueError("Filename cannot be empty or whitespace only")

        if len(v) > 255:
            raise ValueError("Filename must be 255 characters or less")

        # Check for path traversal attempts
        if ".." in v or "/" in v or "\\" in v:
            raise ValueError("Filename cannot contain path separators or '..'")

        # Validate allowed characters
        if not FILENAME_PATTERN.match(v):
            raise ValueError(
                "Filename contains invalid characters. "
                "Only alphanumeric, dots, underscores, hyphens, and spaces are allowed"
            )

        return v

    @field_validator("content_type", mode="before")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        """Validate content type is a valid MIME type format."""
        if not v or not isinstance(v, str):
            raise ValueError("Content type must be a non-empty string")

        v = v.strip().lower()

        if not v:
            raise ValueError("Content type cannot be empty")

        if not MIME_TYPE_PATTERN.match(v):
            raise ValueError(
                f"Invalid content type format: '{v}'. "
                "Expected format: 'type/subtype' (e.g., 'application/pdf')"
            )

        return v

    @field_validator("metadata", mode="before")
    @classmethod
    def validate_metadata(cls, v: Dict[str, Any] | None) -> Dict[str, Any]:
        """Validate metadata is a dictionary."""
        if v is None:
            return {}
        if not isinstance(v, dict):
            raise ValueError("Metadata must be a dictionary")
        return v


class DocumentResponse(DocumentBase):
    """Schema for document response with validation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    file_path: str
    file_size: int
    status: str
    chunk_count: int = 0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="doc_metadata")
    created_at: datetime
    updated_at: Optional[datetime] = None

    @field_validator("file_size", mode="before")
    @classmethod
    def validate_file_size(cls, v: int) -> int:
        """Validate file size is non-negative."""
        if not isinstance(v, int):
            try:
                v = int(v)
            except (TypeError, ValueError):
                raise ValueError("File size must be an integer")

        if v < 0:
            raise ValueError("File size cannot be negative")

        return v

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status is one of the allowed values."""
        if not v or not isinstance(v, str):
            raise ValueError("Status must be a non-empty string")

        v = v.strip().lower()

        if v not in VALID_DOCUMENT_STATUSES:
            raise ValueError(
                f"Invalid status: '{v}'. "
                f"Must be one of: {', '.join(sorted(VALID_DOCUMENT_STATUSES))}"
            )

        return v

    @field_validator("chunk_count", mode="before")
    @classmethod
    def validate_chunk_count(cls, v: int) -> int:
        """Validate chunk count is non-negative."""
        if v is None:
            return 0

        if not isinstance(v, int):
            try:
                v = int(v)
            except (TypeError, ValueError):
                raise ValueError("Chunk count must be an integer")

        if v < 0:
            raise ValueError("Chunk count cannot be negative")

        return v


class DocumentListResponse(BaseModel):
    """Schema for paginated document list with validation."""

    documents: List[DocumentResponse]
    total: int
    skip: int
    limit: int

    @field_validator("total", mode="before")
    @classmethod
    def validate_total(cls, v: int) -> int:
        """Validate total is non-negative."""
        if not isinstance(v, int):
            try:
                v = int(v)
            except (TypeError, ValueError):
                raise ValueError("Total must be an integer")

        if v < 0:
            raise ValueError("Total count cannot be negative")

        return v

    @field_validator("skip", mode="before")
    @classmethod
    def validate_skip(cls, v: int) -> int:
        """Validate skip is non-negative."""
        if not isinstance(v, int):
            try:
                v = int(v)
            except (TypeError, ValueError):
                raise ValueError("Skip must be an integer")

        if v < 0:
            raise ValueError("Skip cannot be negative")

        return v

    @field_validator("limit", mode="before")
    @classmethod
    def validate_limit(cls, v: int) -> int:
        """Validate limit is positive."""
        if not isinstance(v, int):
            try:
                v = int(v)
            except (TypeError, ValueError):
                raise ValueError("Limit must be an integer")

        if v <= 0:
            raise ValueError("Limit must be a positive integer")

        if v > 1000:
            raise ValueError("Limit cannot exceed 1000")

        return v


class DocumentStatusResponse(BaseModel):
    """Schema for document status response with validation."""

    document_id: uuid.UUID
    status: str
    message: str

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status is one of the allowed values."""
        if not v or not isinstance(v, str):
            raise ValueError("Status must be a non-empty string")

        v = v.strip().lower()

        if v not in VALID_DOCUMENT_STATUSES:
            raise ValueError(
                f"Invalid status: '{v}'. "
                f"Must be one of: {', '.join(sorted(VALID_DOCUMENT_STATUSES))}"
            )

        return v

    @field_validator("message", mode="before")
    @classmethod
    def validate_message(cls, v: str) -> str:
        """Validate message is not empty."""
        if not v or not isinstance(v, str):
            raise ValueError("Message must be a non-empty string")

        v = v.strip()

        if not v:
            raise ValueError("Message cannot be empty or whitespace only")

        return v


class ChunkBase(BaseModel):
    """Base chunk schema with validation."""

    content: str
    chunk_index: int
    token_count: Optional[int] = None

    @field_validator("content", mode="before")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate content is not empty."""
        if not v or not isinstance(v, str):
            raise ValueError("Content must be a non-empty string")

        # Don't strip content - preserve whitespace in document chunks
        if not v.strip():
            raise ValueError("Content cannot be empty or whitespace only")

        return v

    @field_validator("chunk_index", mode="before")
    @classmethod
    def validate_chunk_index(cls, v: int) -> int:
        """Validate chunk index is non-negative."""
        if not isinstance(v, int):
            try:
                v = int(v)
            except (TypeError, ValueError):
                raise ValueError("Chunk index must be an integer")

        if v < 0:
            raise ValueError("Chunk index cannot be negative")

        return v

    @field_validator("token_count", mode="before")
    @classmethod
    def validate_token_count(cls, v: int | None) -> int | None:
        """Validate token count is non-negative if provided."""
        if v is None:
            return None

        if not isinstance(v, int):
            try:
                v = int(v)
            except (TypeError, ValueError):
                raise ValueError("Token count must be an integer")

        if v < 0:
            raise ValueError("Token count cannot be negative")

        return v


class ChunkResponse(ChunkBase):
    """Schema for chunk response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class DocumentWithChunks(DocumentResponse):
    """Document response with chunks included."""

    chunks: List[ChunkResponse] = Field(default_factory=list)
