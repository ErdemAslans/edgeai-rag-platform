"""Chunk database model with vector embeddings."""

import uuid
from datetime import datetime
from typing import List, Dict, Any, TYPE_CHECKING

from sqlalchemy import String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from src.db.base import Base
from src.config import settings

if TYPE_CHECKING:
    from src.db.models.document import Document
    from src.db.models.query import QueryChunk


class Chunk(Base):
    """Chunk model for document chunks with vector embeddings."""

    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    embedding: Mapped[List[float] | None] = mapped_column(
        Vector(settings.VECTOR_DIMENSION),
        nullable=True,
    )
    chunk_metadata: Mapped[Dict[str, Any]] = mapped_column(
        "metadata",  # Use 'metadata' as column name in DB
        JSONB,
        default=dict,
        nullable=False,
    )
    token_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="chunks",
    )
    query_chunks: Mapped[List["QueryChunk"]] = relationship(
        "QueryChunk",
        back_populates="chunk",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Chunk(id={self.id}, document_id={self.document_id}, index={self.chunk_index})>"