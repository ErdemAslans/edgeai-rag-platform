"""Query schemas with enhanced Pydantic validators."""

import uuid
from typing import List, Optional, Any, Dict
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class QueryMode(str, Enum):
    """Query mode options."""
    AUTO = "auto"  # Automatically route to best agent
    RAG = "rag"  # Force RAG-based answer
    SUMMARIZE = "summarize"  # Force summarization
    ANALYZE = "analyze"  # Force document analysis
    SQL = "sql"  # Force SQL generation
    # LangGraph modes
    LG_RESEARCH = "lg_research"  # LangGraph research workflow
    LG_ANALYSIS = "lg_analysis"  # LangGraph analysis workflow
    LG_REASONING = "lg_reasoning"  # LangGraph reasoning workflow
    # CrewAI modes
    CREW_RESEARCH = "crew_research"  # CrewAI research crew
    CREW_QA = "crew_qa"  # CrewAI QA crew
    CREW_CODE_REVIEW = "crew_code_review"  # CrewAI code review crew
    # GenAI modes
    GENAI_CHAT = "genai_chat"  # GenAI conversational agent
    GENAI_TASK = "genai_task"  # GenAI task executor
    GENAI_KNOWLEDGE = "genai_knowledge"  # GenAI knowledge agent
    GENAI_REASONING = "genai_reasoning"  # GenAI reasoning agent
    GENAI_CREATIVE = "genai_creative"  # GenAI creative agent


class AgentFramework(str, Enum):
    """Agent framework types."""
    CUSTOM = "custom"
    LANGGRAPH = "langgraph"
    CREWAI = "crewai"
    GENAI = "genai"


class QueryRequest(BaseModel):
    """Schema for asking a question."""
    query: str = Field(..., min_length=1, max_length=10000, description="The query text")
    document_ids: Optional[List[uuid.UUID]] = Field(
        None,
        description="Optional list of document IDs to search within"
    )
    top_k: int = Field(5, ge=1, le=20, description="Number of results to return")
    mode: QueryMode = Field(QueryMode.AUTO, description="Query processing mode")
    agent_name: Optional[str] = Field(None, description="Specific agent to use (overrides mode)")
    framework: Optional[AgentFramework] = Field(None, description="Specific framework to use")
    use_hybrid: bool = Field(False, description="Use hybrid orchestrator for multi-framework routing")

    @field_validator("query", mode="before")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Strip whitespace and validate query is not empty."""
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("Query cannot be empty or contain only whitespace")
            return stripped
        return v

    @field_validator("document_ids", mode="before")
    @classmethod
    def validate_document_ids(cls, v: List[uuid.UUID] | None) -> List[uuid.UUID] | None:
        """Validate document_ids list is not empty when provided."""
        if v is not None and isinstance(v, list) and len(v) == 0:
            return None  # Convert empty list to None
        return v

    @field_validator("agent_name", mode="before")
    @classmethod
    def validate_agent_name(cls, v: str | None) -> str | None:
        """Strip whitespace from agent_name if provided."""
        if isinstance(v, str):
            stripped = v.strip()
            return stripped if stripped else None
        return v


class SourceChunk(BaseModel):
    """Schema for a source chunk used in response."""
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str = Field(..., min_length=1)
    content: str
    similarity_score: float = Field(..., ge=0.0, le=1.0)

    @field_validator("content", mode="before")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Ensure content is not None."""
        if v is None:
            return ""
        return v

    @field_validator("document_name", mode="before")
    @classmethod
    def validate_document_name(cls, v: str) -> str:
        """Strip whitespace from document name."""
        if isinstance(v, str):
            return v.strip()
        return v


class RoutingInfo(BaseModel):
    """Schema for query routing information."""
    selected_agent: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str
    framework: Optional[str] = None

    @field_validator("selected_agent", mode="before")
    @classmethod
    def validate_selected_agent(cls, v: str) -> str:
        """Strip whitespace and validate agent name."""
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("selected_agent cannot be empty")
            return stripped
        return v

    @field_validator("reason", mode="before")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        """Strip whitespace from reason."""
        if isinstance(v, str):
            return v.strip()
        return v if v is not None else ""


class QueryResponse(BaseModel):
    """Schema for query response."""
    query_id: uuid.UUID
    query: str
    response: str
    sources: List[SourceChunk] = Field(default_factory=list)
    agent_used: str
    framework: Optional[str] = None
    routing: Optional[RoutingInfo] = None
    execution_time_ms: Optional[float] = Field(None, ge=0.0)
    reasoning_trace: Optional[str] = None
    phases: Optional[Dict[str, Any]] = None

    @field_validator("execution_time_ms", mode="before")
    @classmethod
    def validate_execution_time(cls, v: float | None) -> float | None:
        """Validate execution time is non-negative."""
        if v is not None and v < 0:
            raise ValueError("execution_time_ms must be non-negative")
        return v


class ChatMessage(BaseModel):
    """Schema for a chat message."""
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str = Field(..., min_length=1)

    @field_validator("content", mode="before")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Strip whitespace and validate content is not empty."""
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("Message content cannot be empty")
            return stripped
        return v


# Maximum number of messages in conversation history
MAX_CONVERSATION_HISTORY_LENGTH = 100


class ChatRequest(BaseModel):
    """Schema for chat request."""
    message: str = Field(..., min_length=1, max_length=10000, description="The chat message")
    conversation_history: List[ChatMessage] = Field(
        default_factory=list,
        description="Previous conversation messages"
    )
    document_ids: Optional[List[uuid.UUID]] = Field(
        None,
        description="Optional list of document IDs to search within"
    )
    mode: QueryMode = Field(QueryMode.AUTO, description="Query processing mode")

    @field_validator("message", mode="before")
    @classmethod
    def validate_message(cls, v: str) -> str:
        """Strip whitespace and validate message is not empty."""
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("Message cannot be empty or contain only whitespace")
            return stripped
        return v

    @field_validator("conversation_history", mode="before")
    @classmethod
    def validate_conversation_history(cls, v: List[ChatMessage]) -> List[ChatMessage]:
        """Validate conversation history length."""
        if isinstance(v, list) and len(v) > MAX_CONVERSATION_HISTORY_LENGTH:
            raise ValueError(
                f"Conversation history exceeds maximum length of {MAX_CONVERSATION_HISTORY_LENGTH} messages"
            )
        return v

    @field_validator("document_ids", mode="before")
    @classmethod
    def validate_document_ids(cls, v: List[uuid.UUID] | None) -> List[uuid.UUID] | None:
        """Validate document_ids list is not empty when provided."""
        if v is not None and isinstance(v, list) and len(v) == 0:
            return None  # Convert empty list to None
        return v


class ChatResponse(BaseModel):
    """Schema for chat response."""
    message_id: uuid.UUID
    response: str
    context_used: List[SourceChunk] = Field(default_factory=list)
    agent_used: str = "rag_query"
    framework: Optional[str] = None
    routing: Optional[RoutingInfo] = None
    execution_time_ms: Optional[float] = Field(None, ge=0.0)

    @field_validator("execution_time_ms", mode="before")
    @classmethod
    def validate_execution_time(cls, v: float | None) -> float | None:
        """Validate execution time is non-negative."""
        if v is not None and v < 0:
            raise ValueError("execution_time_ms must be non-negative")
        return v


class SQLQueryRequest(BaseModel):
    """Schema for natural language to SQL request."""
    query: str = Field(..., min_length=1, max_length=5000, description="Natural language query")
    execute: bool = Field(False, description="Whether to execute the generated SQL")
    schema_context: Optional[str] = Field(None, description="Optional database schema context")

    @field_validator("query", mode="before")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Strip whitespace and validate query is not empty."""
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("Query cannot be empty or contain only whitespace")
            return stripped
        return v

    @field_validator("schema_context", mode="before")
    @classmethod
    def validate_schema_context(cls, v: str | None) -> str | None:
        """Strip whitespace from schema_context if provided."""
        if isinstance(v, str):
            stripped = v.strip()
            return stripped if stripped else None
        return v


class SQLQueryResponse(BaseModel):
    """Schema for SQL query response."""
    query_id: uuid.UUID
    natural_language: str
    generated_sql: str
    explanation: str
    executed: bool
    results: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None

    @field_validator("generated_sql", mode="before")
    @classmethod
    def validate_generated_sql(cls, v: str) -> str:
        """Strip whitespace from generated SQL."""
        if isinstance(v, str):
            return v.strip()
        return v


class QueryHistoryResponse(BaseModel):
    """Schema for paginated query history."""
    queries: List[QueryResponse] = Field(default_factory=list)
    total: int = Field(..., ge=0)
    skip: int = Field(..., ge=0)
    limit: int = Field(..., ge=1, le=100)

    @field_validator("total", "skip", mode="before")
    @classmethod
    def validate_non_negative(cls, v: int) -> int:
        """Validate non-negative integers."""
        if isinstance(v, int) and v < 0:
            raise ValueError("Value must be non-negative")
        return v
