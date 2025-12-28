"""Query and QueryChunk database models."""

import uuid
from datetime import datetime
from typing import List, Dict, Any, TYPE_CHECKING

from sqlalchemy import String, Float, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base

if TYPE_CHECKING:
    from src.db.models.user import User
    from src.db.models.chunk import Chunk
    from src.db.models.agent_log import AgentLog


class Query(Base):
    """Query model for storing user queries and responses."""

    __tablename__ = "queries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    query_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    response_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    agent_used: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    context_used: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    response_time_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="queries",
    )
    query_chunks: Mapped[List["QueryChunk"]] = relationship(
        "QueryChunk",
        back_populates="query",
        cascade="all, delete-orphan",
    )
    agent_logs: Mapped[List["AgentLog"]] = relationship(
        "AgentLog",
        back_populates="query",
    )

    def __repr__(self) -> str:
        return f"<Query(id={self.id}, agent={self.agent_used})>"


class QueryChunk(Base):
    """QueryChunk model for tracking which chunks were used in a query response."""

    __tablename__ = "query_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    query_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("queries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chunks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    similarity_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    # Relationships
    query: Mapped["Query"] = relationship(
        "Query",
        back_populates="query_chunks",
    )
    chunk: Mapped["Chunk"] = relationship(
        "Chunk",
        back_populates="query_chunks",
    )

    def __repr__(self) -> str:
        return f"<QueryChunk(query_id={self.query_id}, chunk_id={self.chunk_id}, score={self.similarity_score})>"