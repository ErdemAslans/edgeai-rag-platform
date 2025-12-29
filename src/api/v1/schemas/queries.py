"""Query schemas."""

import uuid
from typing import List, Optional, Any, Dict
from enum import Enum

from pydantic import BaseModel, Field


class QueryMode(str, Enum):
    """Query mode options."""
    AUTO = "auto"  # Automatically route to best agent
    RAG = "rag"  # Force RAG-based answer
    SUMMARIZE = "summarize"  # Force summarization
    ANALYZE = "analyze"  # Force document analysis
    SQL = "sql"  # Force SQL generation


class QueryRequest(BaseModel):
    """Schema for asking a question."""
    query: str = Field(..., min_length=1, max_length=10000)
    document_ids: Optional[List[uuid.UUID]] = None
    top_k: int = Field(5, ge=1, le=20)
    mode: QueryMode = Field(QueryMode.AUTO, description="Query processing mode")
    agent_name: Optional[str] = Field(None, description="Specific agent to use (overrides mode)")


class SourceChunk(BaseModel):
    """Schema for a source chunk used in response."""
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    content: str
    similarity_score: float


class RoutingInfo(BaseModel):
    """Schema for query routing information."""
    selected_agent: str
    confidence: float
    reason: str


class QueryResponse(BaseModel):
    """Schema for query response."""
    query_id: uuid.UUID
    query: str
    response: str
    sources: List[SourceChunk] = []
    agent_used: str
    routing: Optional[RoutingInfo] = None
    execution_time_ms: Optional[float] = None


class ChatMessage(BaseModel):
    """Schema for a chat message."""
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    """Schema for chat request."""
    message: str = Field(..., min_length=1, max_length=10000)
    conversation_history: List[ChatMessage] = []
    document_ids: Optional[List[uuid.UUID]] = None
    mode: QueryMode = Field(QueryMode.AUTO, description="Query processing mode")


class ChatResponse(BaseModel):
    """Schema for chat response."""
    message_id: uuid.UUID
    response: str
    context_used: List[SourceChunk] = []
    agent_used: str = "rag_query"
    routing: Optional[RoutingInfo] = None


class SQLQueryRequest(BaseModel):
    """Schema for natural language to SQL request."""
    query: str = Field(..., min_length=1, max_length=5000)
    execute: bool = False
    schema_context: Optional[str] = None


class SQLQueryResponse(BaseModel):
    """Schema for SQL query response."""
    query_id: uuid.UUID
    natural_language: str
    generated_sql: str
    explanation: str
    executed: bool
    results: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None


class QueryHistoryResponse(BaseModel):
    """Schema for paginated query history."""
    queries: List[QueryResponse]
    total: int
    skip: int
    limit: int