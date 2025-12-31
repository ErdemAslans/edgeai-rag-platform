"""Real-time collaboration service for document sharing and sessions.

This service provides:
1. Document sharing management
2. Collaboration session handling
3. Comment management
4. Real-time presence

"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import uuid
import secrets

from sqlalchemy import select, func, and_, or_, desc, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.collaboration import (
    DocumentShare,
    CollaborationSession,
    DocumentComment,
    CollaborativeEdit,
    DocumentNotification,
    SharePermission,
    ShareType,
)
from src.db.models.document import Document
from src.db.models.user import User
from src.core.logging import get_logger

logger = get_logger(__name__)


class CollaborationService:
    """Service for collaboration features."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # Document Sharing

    async def share_document(
        self,
        document_id: uuid.UUID,
        shared_by: uuid.UUID,
        share_type: ShareType = ShareType.USER,
        shared_with_user_id: Optional[uuid.UUID] = None,
        shared_with_team_id: Optional[uuid.UUID] = None,
        permission: SharePermission = SharePermission.VIEW,
        message: Optional[str] = None,
        link_expires_in_days: Optional[int] = None,
        link_password: Optional[str] = None,
    ) -> DocumentShare:
        """Share a document with a user, team, or create a share link.
        
        Args:
            document_id: The document to share
            shared_by: User sharing the document
            share_type: Type of share (user, team, public, link)
            shared_with_user_id: User to share with (for user share)
            shared_with_team_id: Team to share with (for team share)
            permission: Permission level
            message: Optional message to recipient
            link_expires_in_days: Link expiration (for link shares)
            link_password: Optional password for link
            
        Returns:
            Created DocumentShare
        """
        # Check for existing share
        if share_type == ShareType.USER and shared_with_user_id:
            existing = await self.session.execute(
                select(DocumentShare)
                .where(
                    and_(
                        DocumentShare.document_id == document_id,
                        DocumentShare.shared_with_user_id == shared_with_user_id,
                        DocumentShare.is_active == True,
                    )
                )
            )
            if existing.scalar_one_or_none():
                raise ValueError("Document already shared with this user")
        
        # Generate link token if needed
        link_token = None
        link_expires_at = None
        password_hash = None
        
        if share_type in [ShareType.PUBLIC, ShareType.LINK]:
            link_token = secrets.token_urlsafe(32)
            if link_expires_in_days:
                link_expires_at = datetime.utcnow() + timedelta(days=link_expires_in_days)
            if link_password:
                from src.core.security import hash_password
                password_hash = hash_password(link_password)
        
        share = DocumentShare(
            document_id=document_id,
            share_type=share_type,
            shared_with_user_id=shared_with_user_id,
            shared_with_team_id=shared_with_team_id,
            share_link_token=link_token,
            link_expires_at=link_expires_at,
            link_password_hash=password_hash,
            permission=permission,
            shared_by=shared_by,
            message=message,
        )
        
        self.session.add(share)
        await self.session.flush()
        
        # Create notification for user shares
        if share_type == ShareType.USER and shared_with_user_id:
            await self._create_notification(
                user_id=shared_with_user_id,
                document_id=document_id,
                triggered_by=shared_by,
                notification_type="share",
                title="Document shared with you",
                message=message,
            )
        
        logger.info(
            "Document shared",
            document_id=str(document_id),
            share_type=share_type.value,
        )
        
        return share

    async def get_shared_documents(
        self,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get documents shared with a user.
        
        Args:
            user_id: The user ID
            skip: Pagination offset
            limit: Maximum results
            
        Returns:
            List of shared documents with share info
        """
        result = await self.session.execute(
            select(DocumentShare, Document)
            .join(Document, DocumentShare.document_id == Document.id)
            .where(
                and_(
                    DocumentShare.shared_with_user_id == user_id,
                    DocumentShare.is_active == True,
                )
            )
            .order_by(desc(DocumentShare.created_at))
            .offset(skip)
            .limit(limit)
        )
        
        shares = []
        for share, document in result.all():
            shares.append({
                "share_id": str(share.id),
                "document_id": str(document.id),
                "document_title": document.filename,
                "permission": share.permission.value,
                "shared_by": str(share.shared_by) if share.shared_by else None,
                "shared_at": share.created_at.isoformat(),
                "message": share.message,
            })
        
        return shares

    async def get_document_shares(
        self,
        document_id: uuid.UUID,
    ) -> List[Dict[str, Any]]:
        """Get all shares for a document.
        
        Args:
            document_id: The document ID
            
        Returns:
            List of shares
        """
        result = await self.session.execute(
            select(DocumentShare)
            .where(
                and_(
                    DocumentShare.document_id == document_id,
                    DocumentShare.is_active == True,
                )
            )
            .order_by(desc(DocumentShare.created_at))
        )
        
        shares = []
        for share in result.scalars().all():
            share_info = {
                "id": str(share.id),
                "share_type": share.share_type.value,
                "permission": share.permission.value,
                "created_at": share.created_at.isoformat(),
            }
            
            if share.share_type == ShareType.USER:
                share_info["shared_with_user_id"] = str(share.shared_with_user_id)
            elif share.share_type in [ShareType.PUBLIC, ShareType.LINK]:
                share_info["share_link_token"] = share.share_link_token
                share_info["expires_at"] = share.link_expires_at.isoformat() if share.link_expires_at else None
            
            shares.append(share_info)
        
        return shares

    async def revoke_share(
        self,
        share_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Revoke a document share.
        
        Args:
            share_id: The share ID to revoke
            user_id: User performing the action
            
        Returns:
            True if revoked
        """
        share = await self.session.get(DocumentShare, share_id)
        if not share:
            raise ValueError("Share not found")
        
        share.is_active = False
        share.updated_at = datetime.utcnow()
        
        await self.session.flush()
        
        logger.info("Share revoked", share_id=str(share_id))
        
        return True

    async def update_share_permission(
        self,
        share_id: uuid.UUID,
        permission: SharePermission,
    ) -> DocumentShare:
        """Update share permission level.
        
        Args:
            share_id: The share ID
            permission: New permission level
            
        Returns:
            Updated share
        """
        share = await self.session.get(DocumentShare, share_id)
        if not share:
            raise ValueError("Share not found")
        
        share.permission = permission
        share.updated_at = datetime.utcnow()
        
        await self.session.flush()
        
        return share

    async def check_access(
        self,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
        required_permission: SharePermission = SharePermission.VIEW,
    ) -> bool:
        """Check if user has required permission on document.
        
        Args:
            document_id: The document ID
            user_id: The user ID
            required_permission: Minimum required permission
            
        Returns:
            True if user has access
        """
        # Check if user is document owner
        document = await self.session.get(Document, document_id)
        if document and document.user_id == user_id:
            return True
        
        # Check shares
        result = await self.session.execute(
            select(DocumentShare)
            .where(
                and_(
                    DocumentShare.document_id == document_id,
                    DocumentShare.shared_with_user_id == user_id,
                    DocumentShare.is_active == True,
                )
            )
        )
        share = result.scalar_one_or_none()
        
        if not share:
            return False
        
        # Check permission level
        permission_levels = {
            SharePermission.VIEW: 1,
            SharePermission.COMMENT: 2,
            SharePermission.EDIT: 3,
            SharePermission.ADMIN: 4,
        }
        
        return permission_levels.get(share.permission, 0) >= permission_levels.get(required_permission, 0)

    # Collaboration Sessions

    async def start_session(
        self,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
        client_id: Optional[str] = None,
        client_info: Optional[Dict[str, Any]] = None,
    ) -> CollaborationSession:
        """Start a collaboration session on a document.
        
        Args:
            document_id: The document ID
            user_id: The user ID
            client_id: WebSocket client identifier
            client_info: Client metadata
            
        Returns:
            Created session
        """
        # End any existing sessions for this user on this document
        await self.session.execute(
            update(CollaborationSession)
            .where(
                and_(
                    CollaborationSession.document_id == document_id,
                    CollaborationSession.user_id == user_id,
                    CollaborationSession.is_active == True,
                )
            )
            .values(is_active=False, disconnected_at=datetime.utcnow())
        )
        
        session = CollaborationSession(
            document_id=document_id,
            user_id=user_id,
            session_token=secrets.token_urlsafe(32),
            client_id=client_id,
            client_info=client_info or {},
        )
        
        self.session.add(session)
        await self.session.flush()
        
        return session

    async def heartbeat(
        self,
        session_id: uuid.UUID,
        cursor_position: Optional[Dict[str, Any]] = None,
        viewport: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update session heartbeat and presence info.
        
        Args:
            session_id: The session ID
            cursor_position: Current cursor position
            viewport: Current viewport
        """
        session = await self.session.get(CollaborationSession, session_id)
        if session and session.is_active:
            session.last_heartbeat = datetime.utcnow()
            if cursor_position:
                session.cursor_position = cursor_position
            if viewport:
                session.viewport = viewport
            await self.session.flush()

    async def end_session(
        self,
        session_id: uuid.UUID,
    ) -> None:
        """End a collaboration session.
        
        Args:
            session_id: The session ID
        """
        session = await self.session.get(CollaborationSession, session_id)
        if session:
            session.is_active = False
            session.disconnected_at = datetime.utcnow()
            await self.session.flush()

    async def get_active_collaborators(
        self,
        document_id: uuid.UUID,
    ) -> List[Dict[str, Any]]:
        """Get currently active collaborators on a document.
        
        Args:
            document_id: The document ID
            
        Returns:
            List of active collaborators with presence info
        """
        # Consider sessions active if heartbeat within last 30 seconds
        cutoff = datetime.utcnow() - timedelta(seconds=30)
        
        result = await self.session.execute(
            select(CollaborationSession, User)
            .join(User, CollaborationSession.user_id == User.id)
            .where(
                and_(
                    CollaborationSession.document_id == document_id,
                    CollaborationSession.is_active == True,
                    CollaborationSession.last_heartbeat >= cutoff,
                )
            )
        )
        
        collaborators = []
        for session, user in result.all():
            collaborators.append({
                "session_id": str(session.id),
                "user_id": str(user.id),
                "user_name": user.full_name or user.email,
                "cursor_position": session.cursor_position,
                "connected_at": session.connected_at.isoformat(),
            })
        
        return collaborators

    # Comments

    async def add_comment(
        self,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
        content: str,
        anchor_type: Optional[str] = None,
        anchor_data: Optional[Dict[str, Any]] = None,
        parent_id: Optional[uuid.UUID] = None,
    ) -> DocumentComment:
        """Add a comment to a document.
        
        Args:
            document_id: The document ID
            user_id: Comment author
            content: Comment content
            anchor_type: Type of anchor (text, chunk, page, general)
            anchor_data: Anchor position data
            parent_id: Parent comment ID for replies
            
        Returns:
            Created comment
        """
        comment = DocumentComment(
            document_id=document_id,
            user_id=user_id,
            content=content,
            anchor_type=anchor_type,
            anchor_data=anchor_data,
            parent_id=parent_id,
        )
        
        self.session.add(comment)
        await self.session.flush()
        
        # Notify document owner and other commenters
        await self._notify_comment(comment, user_id)
        
        return comment

    async def get_comments(
        self,
        document_id: uuid.UUID,
        include_resolved: bool = False,
    ) -> List[Dict[str, Any]]:
        """Get comments for a document.
        
        Args:
            document_id: The document ID
            include_resolved: Whether to include resolved comments
            
        Returns:
            List of comments (threaded)
        """
        filters = [DocumentComment.document_id == document_id]
        if not include_resolved:
            filters.append(DocumentComment.is_resolved == False)
        
        result = await self.session.execute(
            select(DocumentComment, User)
            .join(User, DocumentComment.user_id == User.id, isouter=True)
            .where(and_(*filters))
            .order_by(DocumentComment.created_at)
        )
        
        # Build threaded structure
        comments_by_id: Dict[str, Dict] = {}
        root_comments = []
        
        for comment, user in result.all():
            comment_data = {
                "id": str(comment.id),
                "content": comment.content,
                "user_id": str(comment.user_id) if comment.user_id else None,
                "user_name": user.full_name or user.email if user else "Unknown",
                "anchor_type": comment.anchor_type,
                "anchor_data": comment.anchor_data,
                "is_resolved": comment.is_resolved,
                "created_at": comment.created_at.isoformat(),
                "replies": [],
            }
            
            comments_by_id[str(comment.id)] = comment_data
            
            if comment.parent_id:
                parent = comments_by_id.get(str(comment.parent_id))
                if parent:
                    parent["replies"].append(comment_data)
            else:
                root_comments.append(comment_data)
        
        return root_comments

    async def resolve_comment(
        self,
        comment_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> DocumentComment:
        """Mark a comment as resolved.
        
        Args:
            comment_id: The comment ID
            user_id: User resolving the comment
            
        Returns:
            Updated comment
        """
        comment = await self.session.get(DocumentComment, comment_id)
        if not comment:
            raise ValueError("Comment not found")
        
        comment.is_resolved = True
        comment.resolved_by = user_id
        comment.resolved_at = datetime.utcnow()
        
        await self.session.flush()
        
        return comment

    # Notifications

    async def _create_notification(
        self,
        user_id: uuid.UUID,
        document_id: Optional[uuid.UUID],
        triggered_by: Optional[uuid.UUID],
        notification_type: str,
        title: str,
        message: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> DocumentNotification:
        """Create a notification."""
        notification = DocumentNotification(
            user_id=user_id,
            document_id=document_id,
            triggered_by=triggered_by,
            notification_type=notification_type,
            title=title,
            message=message,
            data=data,
        )
        
        self.session.add(notification)
        await self.session.flush()
        
        return notification

    async def _notify_comment(
        self,
        comment: DocumentComment,
        author_id: uuid.UUID,
    ) -> None:
        """Notify relevant users about a new comment."""
        # Get document owner
        document = await self.session.get(Document, comment.document_id)
        if document and document.user_id != author_id:
            await self._create_notification(
                user_id=document.user_id,
                document_id=comment.document_id,
                triggered_by=author_id,
                notification_type="comment",
                title="New comment on your document",
                data={"comment_id": str(comment.id)},
            )
        
        # If it's a reply, notify parent comment author
        if comment.parent_id:
            parent = await self.session.get(DocumentComment, comment.parent_id)
            if parent and parent.user_id and parent.user_id != author_id:
                await self._create_notification(
                    user_id=parent.user_id,
                    document_id=comment.document_id,
                    triggered_by=author_id,
                    notification_type="reply",
                    title="Reply to your comment",
                    data={"comment_id": str(comment.id)},
                )

    async def get_notifications(
        self,
        user_id: uuid.UUID,
        unread_only: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get notifications for a user.
        
        Args:
            user_id: The user ID
            unread_only: Only return unread notifications
            skip: Pagination offset
            limit: Maximum results
            
        Returns:
            List of notifications
        """
        filters = [DocumentNotification.user_id == user_id]
        if unread_only:
            filters.append(DocumentNotification.is_read == False)
        
        result = await self.session.execute(
            select(DocumentNotification)
            .where(and_(*filters))
            .order_by(desc(DocumentNotification.created_at))
            .offset(skip)
            .limit(limit)
        )
        
        notifications = []
        for notification in result.scalars().all():
            notifications.append({
                "id": str(notification.id),
                "type": notification.notification_type,
                "title": notification.title,
                "message": notification.message,
                "document_id": str(notification.document_id) if notification.document_id else None,
                "is_read": notification.is_read,
                "created_at": notification.created_at.isoformat(),
            })
        
        return notifications

    async def mark_notification_read(
        self,
        notification_id: uuid.UUID,
    ) -> None:
        """Mark a notification as read."""
        notification = await self.session.get(DocumentNotification, notification_id)
        if notification:
            notification.is_read = True
            notification.read_at = datetime.utcnow()
            await self.session.flush()

    async def mark_all_notifications_read(
        self,
        user_id: uuid.UUID,
    ) -> int:
        """Mark all notifications as read for a user.
        
        Returns:
            Number of notifications marked read
        """
        result = await self.session.execute(
            update(DocumentNotification)
            .where(
                and_(
                    DocumentNotification.user_id == user_id,
                    DocumentNotification.is_read == False,
                )
            )
            .values(is_read=True, read_at=datetime.utcnow())
        )
        
        await self.session.flush()
        
        return result.rowcount


def get_collaboration_service(session: AsyncSession) -> CollaborationService:
    """Get collaboration service instance."""
    return CollaborationService(session)