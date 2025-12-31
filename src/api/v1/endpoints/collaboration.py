"""Collaboration API endpoints.

This module provides endpoints for:
1. Document sharing
2. Collaboration sessions
3. Comments
4. Notifications
"""

from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.db.models.user import User
from src.db.models.collaboration import SharePermission, ShareType
from src.services.collaboration_service import get_collaboration_service
from src.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/collaboration", tags=["collaboration"])


# Request/Response schemas

class ShareDocumentRequest(BaseModel):
    """Request to share a document."""
    document_id: UUID
    share_type: str = Field(default="user", description="user, team, public, link")
    shared_with_user_id: Optional[UUID] = None
    shared_with_team_id: Optional[UUID] = None
    permission: str = Field(default="view", description="view, comment, edit, admin")
    message: Optional[str] = None
    link_expires_in_days: Optional[int] = None
    link_password: Optional[str] = None


class ShareResponse(BaseModel):
    """Share response."""
    id: str
    document_id: str
    share_type: str
    permission: str
    share_link_token: Optional[str] = None
    created_at: str


class UpdatePermissionRequest(BaseModel):
    """Request to update share permission."""
    permission: str = Field(description="view, comment, edit, admin")


class AddCommentRequest(BaseModel):
    """Request to add a comment."""
    content: str
    anchor_type: Optional[str] = None
    anchor_data: Optional[dict] = None
    parent_id: Optional[UUID] = None


class CommentResponse(BaseModel):
    """Comment response."""
    id: str
    content: str
    user_id: Optional[str]
    user_name: str
    anchor_type: Optional[str]
    is_resolved: bool
    created_at: str
    replies: List[dict] = []


class StartSessionRequest(BaseModel):
    """Request to start a collaboration session."""
    document_id: UUID
    client_id: Optional[str] = None
    client_info: Optional[dict] = None


class SessionResponse(BaseModel):
    """Session response."""
    session_id: str
    session_token: str
    document_id: str


class HeartbeatRequest(BaseModel):
    """Heartbeat request."""
    cursor_position: Optional[dict] = None
    viewport: Optional[dict] = None


class CollaboratorInfo(BaseModel):
    """Collaborator info."""
    session_id: str
    user_id: str
    user_name: str
    cursor_position: Optional[dict]
    connected_at: str


class NotificationResponse(BaseModel):
    """Notification response."""
    id: str
    type: str
    title: str
    message: Optional[str]
    document_id: Optional[str]
    is_read: bool
    created_at: str


# Helper functions

def parse_share_type(share_type: str) -> ShareType:
    """Parse share type string to enum."""
    mapping = {
        "user": ShareType.USER,
        "team": ShareType.TEAM,
        "public": ShareType.PUBLIC,
        "link": ShareType.LINK,
    }
    if share_type.lower() not in mapping:
        raise ValueError(f"Invalid share type: {share_type}")
    return mapping[share_type.lower()]


def parse_permission(permission: str) -> SharePermission:
    """Parse permission string to enum."""
    mapping = {
        "view": SharePermission.VIEW,
        "comment": SharePermission.COMMENT,
        "edit": SharePermission.EDIT,
        "admin": SharePermission.ADMIN,
    }
    if permission.lower() not in mapping:
        raise ValueError(f"Invalid permission: {permission}")
    return mapping[permission.lower()]


# Endpoints

@router.post("/share", response_model=ShareResponse)
async def share_document(
    request: ShareDocumentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ShareResponse:
    """Share a document with a user, team, or create a share link."""
    try:
        share_type = parse_share_type(request.share_type)
        permission = parse_permission(request.permission)
        
        service = get_collaboration_service(db)
        share = await service.share_document(
            document_id=request.document_id,
            shared_by=current_user.id,
            share_type=share_type,
            shared_with_user_id=request.shared_with_user_id,
            shared_with_team_id=request.shared_with_team_id,
            permission=permission,
            message=request.message,
            link_expires_in_days=request.link_expires_in_days,
            link_password=request.link_password,
        )
        
        await db.commit()
        
        return ShareResponse(
            id=str(share.id),
            document_id=str(share.document_id),
            share_type=share.share_type.value,
            permission=share.permission.value,
            share_link_token=share.share_link_token,
            created_at=share.created_at.isoformat(),
        )
        
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Failed to share document", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to share document",
        )


@router.get("/shared-with-me")
async def get_shared_with_me(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get documents shared with the current user."""
    service = get_collaboration_service(db)
    shares = await service.get_shared_documents(
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    return {"shares": shares, "total": len(shares)}


@router.get("/documents/{document_id}/shares")
async def get_document_shares(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all shares for a document."""
    service = get_collaboration_service(db)
    
    # Verify user has access
    has_access = await service.check_access(
        document_id=document_id,
        user_id=current_user.id,
        required_permission=SharePermission.ADMIN,
    )
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permission required to view shares",
        )
    
    shares = await service.get_document_shares(document_id)
    return {"shares": shares}


@router.delete("/shares/{share_id}")
async def revoke_share(
    share_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revoke a document share."""
    try:
        service = get_collaboration_service(db)
        await service.revoke_share(share_id=share_id, user_id=current_user.id)
        await db.commit()
        return {"message": "Share revoked"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/shares/{share_id}/permission")
async def update_share_permission(
    share_id: UUID,
    request: UpdatePermissionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update share permission level."""
    try:
        permission = parse_permission(request.permission)
        service = get_collaboration_service(db)
        share = await service.update_share_permission(share_id, permission)
        await db.commit()
        
        return {
            "id": str(share.id),
            "permission": share.permission.value,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# Sessions

@router.post("/sessions/start", response_model=SessionResponse)
async def start_session(
    request: StartSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionResponse:
    """Start a collaboration session on a document."""
    service = get_collaboration_service(db)
    
    # Verify user has at least view access
    has_access = await service.check_access(
        document_id=request.document_id,
        user_id=current_user.id,
    )
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this document",
        )
    
    session = await service.start_session(
        document_id=request.document_id,
        user_id=current_user.id,
        client_id=request.client_id,
        client_info=request.client_info,
    )
    
    await db.commit()
    
    return SessionResponse(
        session_id=str(session.id),
        session_token=session.session_token,
        document_id=str(session.document_id),
    )


@router.post("/sessions/{session_id}/heartbeat")
async def session_heartbeat(
    session_id: UUID,
    request: HeartbeatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send heartbeat to keep session alive and update presence."""
    service = get_collaboration_service(db)
    await service.heartbeat(
        session_id=session_id,
        cursor_position=request.cursor_position,
        viewport=request.viewport,
    )
    await db.commit()
    return {"status": "ok"}


@router.post("/sessions/{session_id}/end")
async def end_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """End a collaboration session."""
    service = get_collaboration_service(db)
    await service.end_session(session_id)
    await db.commit()
    return {"status": "ended"}


@router.get("/documents/{document_id}/collaborators")
async def get_collaborators(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get active collaborators on a document."""
    service = get_collaboration_service(db)
    collaborators = await service.get_active_collaborators(document_id)
    return {"collaborators": collaborators}


# Comments

@router.post("/documents/{document_id}/comments", response_model=CommentResponse)
async def add_comment(
    document_id: UUID,
    request: AddCommentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommentResponse:
    """Add a comment to a document."""
    service = get_collaboration_service(db)
    
    # Verify user has at least comment permission
    has_access = await service.check_access(
        document_id=document_id,
        user_id=current_user.id,
        required_permission=SharePermission.COMMENT,
    )
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Comment permission required",
        )
    
    comment = await service.add_comment(
        document_id=document_id,
        user_id=current_user.id,
        content=request.content,
        anchor_type=request.anchor_type,
        anchor_data=request.anchor_data,
        parent_id=request.parent_id,
    )
    
    await db.commit()
    
    return CommentResponse(
        id=str(comment.id),
        content=comment.content,
        user_id=str(comment.user_id) if comment.user_id else None,
        user_name=current_user.full_name or current_user.email,
        anchor_type=comment.anchor_type,
        is_resolved=comment.is_resolved,
        created_at=comment.created_at.isoformat(),
        replies=[],
    )


@router.get("/documents/{document_id}/comments")
async def get_comments(
    document_id: UUID,
    include_resolved: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get comments for a document."""
    service = get_collaboration_service(db)
    comments = await service.get_comments(
        document_id=document_id,
        include_resolved=include_resolved,
    )
    return {"comments": comments}


@router.post("/comments/{comment_id}/resolve")
async def resolve_comment(
    comment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a comment as resolved."""
    try:
        service = get_collaboration_service(db)
        comment = await service.resolve_comment(
            comment_id=comment_id,
            user_id=current_user.id,
        )
        await db.commit()
        return {"id": str(comment.id), "is_resolved": True}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# Notifications

@router.get("/notifications")
async def get_notifications(
    unread_only: bool = Query(default=False),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get notifications for the current user."""
    service = get_collaboration_service(db)
    notifications = await service.get_notifications(
        user_id=current_user.id,
        unread_only=unread_only,
        skip=skip,
        limit=limit,
    )
    return {"notifications": notifications}


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a notification as read."""
    service = get_collaboration_service(db)
    await service.mark_notification_read(notification_id)
    await db.commit()
    return {"status": "read"}


@router.post("/notifications/read-all")
async def mark_all_notifications_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark all notifications as read."""
    service = get_collaboration_service(db)
    count = await service.mark_all_notifications_read(current_user.id)
    await db.commit()
    return {"marked_read": count}