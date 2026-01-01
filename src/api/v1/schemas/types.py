"""TypedDict definitions for API response structures.

This module provides TypedDict type hints for API responses,
enabling strict type checking for dictionary-based operations
while maintaining compatibility with Pydantic models.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict


class SourceChunkDict(TypedDict):
    """TypedDict for source chunk data in query responses."""
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    content: str
    similarity_score: float


class RoutingInfoDict(TypedDict, total=False):
    """TypedDict for query routing information."""
    selected_agent: str
    confidence: float
    reason: str
    framework: Optional[str]


class DocumentResponse(TypedDict, total=False):
    """TypedDict for document response structure.

    Provides type hints for document API responses,
    compatible with both Pydantic serialization and raw dict operations.
    """
    id: uuid.UUID
    user_id: uuid.UUID
    filename: str
    content_type: str
    file_path: str
    file_size: int
    status: str
    chunk_count: int
    error_message: Optional[str]
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime]


class DocumentResponseRequired(TypedDict):
    """TypedDict with required fields for document response."""
    id: uuid.UUID
    user_id: uuid.UUID
    filename: str
    content_type: str
    file_path: str
    file_size: int
    status: str
    created_at: datetime


class QueryResponse(TypedDict, total=False):
    """TypedDict for query response structure.

    Provides type hints for query API responses,
    enabling strict type checking for response dictionary operations.
    """
    query_id: uuid.UUID
    query: str
    response: str
    sources: List[SourceChunkDict]
    agent_used: str
    framework: Optional[str]
    routing: Optional[RoutingInfoDict]
    execution_time_ms: Optional[float]
    reasoning_trace: Optional[str]
    phases: Optional[Dict[str, Any]]


class QueryResponseRequired(TypedDict):
    """TypedDict with required fields for query response."""
    query_id: uuid.UUID
    query: str
    response: str
    agent_used: str


class ChunkResponse(TypedDict, total=False):
    """TypedDict for chunk response structure."""
    id: uuid.UUID
    document_id: uuid.UUID
    content: str
    chunk_index: int
    token_count: Optional[int]
    metadata: Dict[str, Any]
    created_at: datetime


class DocumentListResponse(TypedDict):
    """TypedDict for paginated document list response."""
    documents: List[DocumentResponse]
    total: int
    skip: int
    limit: int


class QueryHistoryResponse(TypedDict):
    """TypedDict for paginated query history response."""
    queries: List[QueryResponse]
    total: int
    skip: int
    limit: int


class ChatResponse(TypedDict, total=False):
    """TypedDict for chat response structure."""
    message_id: uuid.UUID
    response: str
    context_used: List[SourceChunkDict]
    agent_used: str
    framework: Optional[str]
    routing: Optional[RoutingInfoDict]
    execution_time_ms: Optional[float]


class ErrorResponse(TypedDict):
    """TypedDict for standardized error response structure."""
    error_code: str
    message: str
    detail: Optional[str]


class PaginationParams(TypedDict, total=False):
    """TypedDict for pagination parameters."""
    skip: int
    limit: int
    total: int


class HealthCheckResponse(TypedDict):
    """TypedDict for health check response."""
    status: str
    version: str
    timestamp: datetime


class TokenResponse(TypedDict, total=False):
    """TypedDict for token response structure."""
    access_token: str
    refresh_token: str
    token_type: str
    requires_2fa: bool
