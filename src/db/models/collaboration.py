"""Real-time collaboration models for document sharing and sessions.

This module provides:
1. DocumentShare - Document sharing permissions
2. CollaborationSession - Active collaboration sessions
3. DocumentComment - Comments on documents
4. CollaborativeEdit - Real-time edit tracking

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
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from src.db.base import Base


class SharePermission(str, enum.Enum):
    """Permission levels for document sharing."""
    VIEW = "view"
    COMMENT = "comment"
    EDIT = "edit"
    ADMIN = "admin"


class ShareType(str, enum.Enum):
    """Type of share recipient."""
    USER = "user"
    TEAM = "team"
    PUBLIC = "public"
    LINK = "link"


class DocumentShare(Base):
    """Tracks document sharing permissions.
    
    Enables sharing documents with specific users, teams,
    or via public/private links.
    """
    
    __tablename__ = "document_shares"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Share type and recipient
    share_type = Column(SQLEnum(ShareType), nullable=False, default=ShareType.USER)
    shared_with_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    shared_with_team_id = Column(
        UUID(as_uuid=True),
        nullable=True,  # No FK for now, team table may not exist
    )
    
    # For link sharing
    share_link_token = Column(String(100), nullable=True, unique=True, index=True)
    link_expires_at = Column(DateTime, nullable=True)
    link_password_hash = Column(String(255), nullable=True)
    
    # Permission level
    permission = Column(SQLEnum(SharePermission), nullable=False, default=SharePermission.VIEW)
    
    # Sharing metadata
    shared_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    message = Column(Text, nullable=True)  # Optional message to recipient
    
    # Status
    is_active = Column(Boolean, default=True)
    accepted_at = Column(DateTime, nullable=True)  # When recipient accepted
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    document = relationship("Document")
    shared_with_user = relationship("User", foreign_keys=[shared_with_user_id])
    shared_by_user = relationship("User", foreign_keys=[shared_by])
    
    __table_args__ = (
        # Ensure unique share per user/document combination
        UniqueConstraint('document_id', 'shared_with_user_id', name='uq_doc_share_user'),
        Index('ix_share_document_type', 'document_id', 'share_type'),
    )
    
    def __repr__(self) -> str:
        return f"<DocumentShare(id={self.id}, doc={self.document_id}, type={self.share_type})>"


class CollaborationSession(Base):
    """Tracks active collaboration sessions on documents.
    
    Enables real-time presence awareness and collaborative editing.
    """
    
    __tablename__ = "collaboration_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Session info
    session_token = Column(String(100), nullable=False, unique=True)
    
    # Presence info
    is_active = Column(Boolean, default=True)
    cursor_position = Column(JSON, nullable=True)  # {line, column, selection}
    viewport = Column(JSON, nullable=True)  # Visible area
    
    # Connection info
    connected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_heartbeat = Column(DateTime, default=datetime.utcnow)
    disconnected_at = Column(DateTime, nullable=True)
    
    # Client info
    client_id = Column(String(100), nullable=True)  # For WebSocket identification
    client_info = Column(JSON, nullable=True)  # Browser, device, etc.
    
    # Relationships
    document = relationship("Document")
    user = relationship("User")
    
    __table_args__ = (
        Index('ix_session_doc_user', 'document_id', 'user_id'),
        Index('ix_session_active', 'is_active', 'last_heartbeat'),
    )
    
    def __repr__(self) -> str:
        return f"<CollaborationSession(id={self.id}, doc={self.document_id}, user={self.user_id})>"


class DocumentComment(Base):
    """Comments and annotations on documents.
    
    Supports threaded discussions and inline comments.
    """
    
    __tablename__ = "document_comments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Comment content
    content = Column(Text, nullable=False)
    
    # Position in document (for inline comments)
    anchor_type = Column(String(20), nullable=True)  # text, chunk, page, general
    anchor_data = Column(JSON, nullable=True)  # Position details
    
    # Threading
    parent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_comments.id", ondelete="CASCADE"),
        nullable=True,
    )
    
    # Status
    is_resolved = Column(Boolean, default=False)
    resolved_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    document = relationship("Document")
    user = relationship("User", foreign_keys=[user_id])
    resolver = relationship("User", foreign_keys=[resolved_by])
    parent = relationship("DocumentComment", remote_side=[id], backref="replies")
    
    __table_args__ = (
        Index('ix_comment_doc_parent', 'document_id', 'parent_id'),
    )
    
    def __repr__(self) -> str:
        return f"<DocumentComment(id={self.id}, doc={self.document_id})>"


class CollaborativeEdit(Base):
    """Tracks real-time collaborative edits.
    
    Stores edit operations for conflict resolution
    and history reconstruction.
    """
    
    __tablename__ = "collaborative_edits"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("collaboration_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Operation details (Operational Transform / CRDT)
    operation_type = Column(String(20), nullable=False)  # insert, delete, retain
    operation_data = Column(JSON, nullable=False)  # Operation-specific data
    
    # Versioning
    base_version = Column(Integer, nullable=False)  # Version this edit is based on
    result_version = Column(Integer, nullable=False)  # Version after applying
    
    # Conflict resolution
    is_conflicted = Column(Boolean, default=False)
    conflict_resolution = Column(JSON, nullable=True)  # How conflict was resolved
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    applied_at = Column(DateTime, nullable=True)
    
    # Relationships
    document = relationship("Document")
    user = relationship("User")
    session = relationship("CollaborationSession")
    
    __table_args__ = (
        Index('ix_edit_doc_version', 'document_id', 'base_version'),
    )
    
    def __repr__(self) -> str:
        return f"<CollaborativeEdit(id={self.id}, doc={self.document_id}, op={self.operation_type})>"


class DocumentNotification(Base):
    """Notifications for document-related events.
    
    Tracks mentions, comments, shares, and other activities.
    """
    
    __tablename__ = "document_notifications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    
    # Recipient
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Source
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=True,
    )
    triggered_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Notification details
    notification_type = Column(String(50), nullable=False)  # share, comment, mention, edit
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=True)
    data = Column(JSON, nullable=True)  # Additional context
    
    # Status
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    document = relationship("Document")
    triggered_by_user = relationship("User", foreign_keys=[triggered_by])
    
    __table_args__ = (
        Index('ix_notification_user_read', 'user_id', 'is_read'),
    )
    
    def __repr__(self) -> str:
        return f"<DocumentNotification(id={self.id}, user={self.user_id}, type={self.notification_type})>"