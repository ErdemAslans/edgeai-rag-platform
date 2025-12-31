"""Document database model."""

import uuid
from datetime import datetime
from typing import List, Dict, Any, TYPE_CHECKING

from sqlalchemy import String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base

if TYPE_CHECKING:
    from src.db.models.user import User
    from src.db.models.chunk import Chunk
    from src.db.models.document_version import DocumentVersion


class Document(Base):
    """Document model for uploaded files."""

    __tablename__ = "documents"

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
    filename: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    content_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )
    file_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        nullable=False,
        index=True,
    )
    chunk_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    doc_metadata: Mapped[Dict[str, Any]] = mapped_column(
        "metadata",  # Use 'metadata' as column name in DB
        JSONB,
        default=dict,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        onupdate=datetime.utcnow,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="documents",
    )
    chunks: Mapped[List["Chunk"]] = relationship(
        "Chunk",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    versions: Mapped[List["DocumentVersion"]] = relationship(
        "DocumentVersion",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="desc(DocumentVersion.version_number)",
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, filename={self.filename}, status={self.status})>"