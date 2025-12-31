"""Document versioning models for tracking document history.

This module provides:
1. DocumentVersion - Version snapshots of documents
2. DocumentDiff - Diff between versions
3. VersionMetadata - Additional version info
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
import uuid as uuid_lib

from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    DateTime,
    ForeignKey,
    JSON,
    Boolean,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from src.db.base import Base


class VersionType(str, enum.Enum):
    """Type of version change."""
    CREATE = "create"
    UPDATE = "update"
    REPROCESS = "reprocess"
    RESTORE = "restore"
    AUTO_SAVE = "auto_save"


class DocumentVersion(Base):
    """Stores document version snapshots.
    
    Each version captures the complete state of a document at a point in time.
    This enables version history, rollback, and audit trails.
    """
    
    __tablename__ = "document_versions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Version info
    version_number = Column(Integer, nullable=False)
    version_type = Column(SQLEnum(VersionType), nullable=False, default=VersionType.UPDATE)
    
    # Content snapshot
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=True)  # Full content at this version
    content_hash = Column(String(64), nullable=True)  # SHA-256 hash for comparison
    
    # File info snapshot
    file_size = Column(Integer, nullable=True)
    file_type = Column(String(50), nullable=True)
    
    # Metadata snapshot
    version_metadata = Column(JSON, nullable=True, default=dict)
    
    # Change info
    change_summary = Column(Text, nullable=True)  # Description of changes
    changed_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relations
    document = relationship("Document", back_populates="versions")
    user = relationship("User", foreign_keys=[changed_by])
    diffs = relationship(
        "DocumentDiff",
        back_populates="version",
        cascade="all, delete-orphan",
        foreign_keys="DocumentDiff.version_id",
    )
    
    def __repr__(self) -> str:
        return f"<DocumentVersion(id={self.id}, doc={self.document_id}, v{self.version_number})>"


class DocumentDiff(Base):
    """Stores diffs between document versions.
    
    Enables efficient storage and display of changes between versions.
    Uses a unified diff format for text comparison.
    """
    
    __tablename__ = "document_diffs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Diff content
    diff_type = Column(String(20), nullable=False, default="unified")  # unified, json, semantic
    diff_content = Column(Text, nullable=True)  # Unified diff format
    
    # Statistics
    lines_added = Column(Integer, default=0)
    lines_removed = Column(Integer, default=0)
    lines_changed = Column(Integer, default=0)
    
    # Semantic changes (for structured content)
    semantic_changes = Column(JSON, nullable=True)  # List of semantic change descriptions
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relations
    version = relationship(
        "DocumentVersion",
        back_populates="diffs",
        foreign_keys=[version_id],
    )
    from_version = relationship(
        "DocumentVersion",
        foreign_keys=[from_version_id],
    )
    
    def __repr__(self) -> str:
        return f"<DocumentDiff(id={self.id}, version={self.version_id})>"


class DocumentAuditLog(Base):
    """Audit log for document operations.
    
    Tracks all operations performed on documents for compliance
    and debugging purposes.
    """
    
    __tablename__ = "document_audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    # Action info
    action = Column(String(50), nullable=False)  # create, update, delete, view, download, share, etc.
    action_details = Column(JSON, nullable=True)  # Additional context
    
    # Actor info
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(String(500), nullable=True)
    
    # Context
    version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Result
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relations
    document = relationship("Document")
    user = relationship("User")
    version = relationship("DocumentVersion")
    
    def __repr__(self) -> str:
        return f"<DocumentAuditLog(id={self.id}, action={self.action}, doc={self.document_id})>"