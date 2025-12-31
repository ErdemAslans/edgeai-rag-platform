"""Document versioning API endpoints.

Provides endpoints for:
- Version history listing
- Version content retrieval
- Diff viewing
- Rollback functionality
- Audit log access
"""

from typing import Optional, List
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from src.api.deps import get_current_user, get_db
from src.db.models.user import User
from src.db.models.document_version import VersionType
from src.services.document_version_service import get_document_version_service

router = APIRouter(prefix="/documents/{document_id}/versions", tags=["versions"])


# Request/Response Models
class VersionInfo(BaseModel):
    id: str
    version_number: int
    version_type: str
    title: str
    content_hash: Optional[str]
    file_size: Optional[int]
    change_summary: Optional[str]
    changed_by: Optional[str]
    created_at: str
    diff_stats: Optional[dict]


class VersionHistoryResponse(BaseModel):
    document_id: str
    total_versions: int
    versions: List[VersionInfo]


class VersionContentResponse(BaseModel):
    document_id: str
    version_number: int
    title: str
    content: Optional[str]
    created_at: str


class DiffResponse(BaseModel):
    from_version: int
    to_version: int
    from_version_info: dict
    to_version_info: dict
    diff_content: Optional[str]


class CompareResponse(BaseModel):
    version_a: dict
    version_b: dict
    diff: Optional[str]
    same_content: bool


class RollbackRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=500)


class RollbackResponse(BaseModel):
    success: bool
    message: str
    new_version_number: int


class AuditLogEntry(BaseModel):
    id: str
    action: str
    action_details: Optional[dict]
    user_id: Optional[str]
    version_id: Optional[str]
    ip_address: Optional[str]
    success: bool
    error_message: Optional[str]
    created_at: str


class AuditLogResponse(BaseModel):
    document_id: str
    entries: List[AuditLogEntry]


# Helper function to get client info
def get_client_info(request: Request) -> tuple:
    """Extract client IP and user agent from request."""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return ip_address, user_agent


@router.get("", response_model=VersionHistoryResponse)
async def get_version_history(
    document_id: uuid.UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VersionHistoryResponse:
    """Get version history for a document.
    
    Returns a paginated list of all versions with metadata.
    """
    service = get_document_version_service(db)
    
    try:
        versions = await service.get_version_history(document_id, skip, limit)
        
        # Get total count
        total = len(versions)  # Could optimize with separate count query
        
        return VersionHistoryResponse(
            document_id=str(document_id),
            total_versions=total,
            versions=[VersionInfo(**v) for v in versions],
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{version_number}", response_model=VersionContentResponse)
async def get_version_content(
    document_id: uuid.UUID,
    version_number: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VersionContentResponse:
    """Get content of a specific version.
    
    Returns the full content of the document at the specified version.
    """
    service = get_document_version_service(db)
    
    version = await service.get_version(document_id, version_number)
    if not version:
        raise HTTPException(
            status_code=404,
            detail=f"Version {version_number} not found for document {document_id}"
        )
    
    return VersionContentResponse(
        document_id=str(document_id),
        version_number=version.version_number,
        title=version.title,
        content=version.content,
        created_at=version.created_at.isoformat(),
    )


@router.get("/{from_version}/diff", response_model=DiffResponse)
async def get_version_diff(
    document_id: uuid.UUID,
    from_version: int,
    to_version: Optional[int] = Query(default=None, description="Target version (default: latest)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DiffResponse:
    """Get diff between two versions.
    
    If to_version is not specified, compares with the latest version.
    """
    service = get_document_version_service(db)
    
    try:
        diff = await service.get_diff(document_id, from_version, to_version)
        return DiffResponse(**diff)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{version_a}/compare/{version_b}", response_model=CompareResponse)
async def compare_versions(
    document_id: uuid.UUID,
    version_a: int,
    version_b: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CompareResponse:
    """Compare two specific versions side by side.
    
    Returns both version contents and the diff between them.
    """
    service = get_document_version_service(db)
    
    try:
        comparison = await service.compare_versions(document_id, version_a, version_b)
        return CompareResponse(**comparison)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{version_number}/rollback", response_model=RollbackResponse)
async def rollback_to_version(
    document_id: uuid.UUID,
    version_number: int,
    request: Request,
    rollback_request: Optional[RollbackRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RollbackResponse:
    """Rollback document to a previous version.
    
    Creates a new version with the content from the target version.
    The current state is preserved as a version before rollback.
    """
    service = get_document_version_service(db)
    ip_address, user_agent = get_client_info(request)
    
    reason = rollback_request.reason if rollback_request else None
    
    try:
        document = await service.rollback(
            document_id=document_id,
            target_version=version_number,
            user_id=current_user.id,
            reason=reason,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        # Get new version number
        versions = await service.get_version_history(document_id, skip=0, limit=1)
        new_version = versions[0]["version_number"] if versions else 0
        
        await db.commit()
        
        return RollbackResponse(
            success=True,
            message=f"Successfully rolled back to version {version_number}",
            new_version_number=new_version,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/audit-log", response_model=AuditLogResponse)
async def get_audit_log(
    document_id: uuid.UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AuditLogResponse:
    """Get audit log for a document.
    
    Returns all recorded actions performed on the document.
    """
    service = get_document_version_service(db)
    
    logs = await service.get_audit_log(document_id, skip, limit)
    
    return AuditLogResponse(
        document_id=str(document_id),
        entries=[AuditLogEntry(**log) for log in logs],
    )


# Additional endpoint for creating manual versions
class CreateVersionRequest(BaseModel):
    change_summary: Optional[str] = Field(None, max_length=500)


class CreateVersionResponse(BaseModel):
    version_id: str
    version_number: int
    created_at: str


@router.post("", response_model=CreateVersionResponse)
async def create_version(
    document_id: uuid.UUID,
    request: Request,
    create_request: Optional[CreateVersionRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CreateVersionResponse:
    """Manually create a version snapshot.
    
    Creates a new version of the document's current state.
    Useful for marking important checkpoints.
    """
    service = get_document_version_service(db)
    ip_address, user_agent = get_client_info(request)
    
    change_summary = create_request.change_summary if create_request else None
    
    try:
        version = await service.create_version(
            document_id=document_id,
            version_type=VersionType.UPDATE,
            change_summary=change_summary,
            user_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        await db.commit()
        
        return CreateVersionResponse(
            version_id=str(version.id),
            version_number=version.version_number,
            created_at=version.created_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))