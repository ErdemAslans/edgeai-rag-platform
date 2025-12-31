"""Document versioning service for managing document history.

This service provides:
1. Version creation and management
2. Diff generation and comparison
3. Rollback functionality
4. Audit logging

"""

from datetime import datetime
from typing import Optional, List, Dict, Any
import uuid
import hashlib

from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.db.models.document import Document
from src.db.models.document_version import (
    DocumentVersion,
    DocumentDiff,
    DocumentAuditLog,
    VersionType,
)
from src.db.repositories.document_version import (
    DocumentVersionRepository,
    DocumentDiffRepository,
    DocumentAuditLogRepository,
)
from src.db.repositories.document import DocumentRepository
from src.core.logging import get_logger

logger = get_logger(__name__)


class DocumentVersionService:
    """Service for document version management."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.version_repo = DocumentVersionRepository(session)
        self.diff_repo = DocumentDiffRepository(session)
        self.audit_repo = DocumentAuditLogRepository(session)
        self.document_repo = DocumentRepository(session)

    async def create_version(
        self,
        document_id: uuid.UUID,
        version_type: VersionType = VersionType.UPDATE,
        change_summary: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> DocumentVersion:
        """Create a new version snapshot of a document.
        
        Args:
            document_id: The document ID
            version_type: Type of version change
            change_summary: Description of changes
            user_id: ID of user making the change
            ip_address: Client IP for audit
            user_agent: Client user agent for audit
            
        Returns:
            Created DocumentVersion
            
        Raises:
            ValueError: If document not found
        """
        # Get current document state
        document = await self.document_repo.get_by_id(document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found")
        
        # Create version snapshot
        version = await self.version_repo.create_version(
            document_id=document_id,
            title=document.title,
            content=document.content,
            version_type=version_type,
            file_size=document.file_size,
            file_type=document.file_type,
            metadata=document.metadata,
            change_summary=change_summary,
            user_id=user_id,
        )
        
        # Log the action
        await self.audit_repo.log_action(
            document_id=document_id,
            action=f"version_created_{version_type.value}",
            user_id=user_id,
            version_id=version.id,
            action_details={
                "version_number": version.version_number,
                "change_summary": change_summary,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        logger.info(
            "Document version created",
            document_id=str(document_id),
            version_number=version.version_number,
            version_type=version_type.value,
        )
        
        return version

    async def get_version_history(
        self,
        document_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get version history for a document.
        
        Args:
            document_id: The document ID
            skip: Number of versions to skip
            limit: Maximum versions to return
            
        Returns:
            List of version info dictionaries
        """
        versions = await self.version_repo.get_versions(document_id, skip, limit)
        
        result = []
        for version in versions:
            # Get diff for this version
            diff = await self.diff_repo.get_diff(version.id)
            
            result.append({
                "id": str(version.id),
                "version_number": version.version_number,
                "version_type": version.version_type.value,
                "title": version.title,
                "content_hash": version.content_hash,
                "file_size": version.file_size,
                "change_summary": version.change_summary,
                "changed_by": str(version.changed_by) if version.changed_by else None,
                "created_at": version.created_at.isoformat(),
                "diff_stats": {
                    "lines_added": diff.lines_added if diff else 0,
                    "lines_removed": diff.lines_removed if diff else 0,
                    "lines_changed": diff.lines_changed if diff else 0,
                } if diff else None,
            })
        
        return result

    async def get_version(
        self,
        document_id: uuid.UUID,
        version_number: int,
    ) -> Optional[DocumentVersion]:
        """Get a specific version of a document.
        
        Args:
            document_id: The document ID
            version_number: Version number to retrieve
            
        Returns:
            DocumentVersion or None
        """
        return await self.version_repo.get_version(document_id, version_number)

    async def get_version_content(
        self,
        document_id: uuid.UUID,
        version_number: int,
    ) -> Optional[str]:
        """Get content of a specific version.
        
        Args:
            document_id: The document ID
            version_number: Version number
            
        Returns:
            Content string or None
        """
        version = await self.version_repo.get_version(document_id, version_number)
        return version.content if version else None

    async def get_diff(
        self,
        document_id: uuid.UUID,
        from_version: int,
        to_version: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get diff between two versions.
        
        Args:
            document_id: The document ID
            from_version: Start version number
            to_version: End version number (default: latest)
            
        Returns:
            Diff information dictionary
        """
        # Get target version
        if to_version is None:
            latest = await self.version_repo.get_latest_version(document_id)
            if not latest:
                raise ValueError(f"No versions found for document {document_id}")
            to_version = latest.version_number
        
        # Get diff content
        diff_content = await self.diff_repo.get_diff_between_versions(
            document_id, from_version, to_version
        )
        
        # Get version details
        from_ver = await self.version_repo.get_version(document_id, from_version)
        to_ver = await self.version_repo.get_version(document_id, to_version)
        
        return {
            "from_version": from_version,
            "to_version": to_version,
            "from_version_info": {
                "title": from_ver.title if from_ver else None,
                "created_at": from_ver.created_at.isoformat() if from_ver else None,
            },
            "to_version_info": {
                "title": to_ver.title if to_ver else None,
                "created_at": to_ver.created_at.isoformat() if to_ver else None,
            },
            "diff_content": diff_content,
        }

    async def rollback(
        self,
        document_id: uuid.UUID,
        target_version: int,
        user_id: Optional[uuid.UUID] = None,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Document:
        """Rollback a document to a previous version.
        
        Args:
            document_id: The document ID
            target_version: Version number to rollback to
            user_id: ID of user performing rollback
            reason: Reason for rollback
            ip_address: Client IP for audit
            user_agent: Client user agent for audit
            
        Returns:
            Updated Document
            
        Raises:
            ValueError: If version not found
        """
        # Get target version
        version = await self.version_repo.get_version(document_id, target_version)
        if not version:
            raise ValueError(f"Version {target_version} not found for document {document_id}")
        
        # Get current document
        document = await self.document_repo.get_by_id(document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found")
        
        # Create version snapshot of current state before rollback
        await self.create_version(
            document_id=document_id,
            version_type=VersionType.UPDATE,
            change_summary=f"Pre-rollback snapshot (before rolling back to v{target_version})",
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        # Update document with version content
        document.title = version.title
        document.content = version.content
        document.metadata = version.metadata or {}
        document.updated_at = datetime.utcnow()
        
        await self.session.flush()
        
        # Create restore version
        restore_version = await self.version_repo.create_version(
            document_id=document_id,
            title=version.title,
            content=version.content,
            version_type=VersionType.RESTORE,
            file_size=version.file_size,
            file_type=version.file_type,
            metadata=version.metadata,
            change_summary=f"Restored from version {target_version}" + (f": {reason}" if reason else ""),
            user_id=user_id,
        )
        
        # Log the rollback
        await self.audit_repo.log_action(
            document_id=document_id,
            action="rollback",
            user_id=user_id,
            version_id=restore_version.id,
            action_details={
                "target_version": target_version,
                "restore_version": restore_version.version_number,
                "reason": reason,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        logger.info(
            "Document rolled back",
            document_id=str(document_id),
            target_version=target_version,
            new_version=restore_version.version_number,
        )
        
        return document

    async def compare_versions(
        self,
        document_id: uuid.UUID,
        version_a: int,
        version_b: int,
    ) -> Dict[str, Any]:
        """Compare two specific versions side by side.
        
        Args:
            document_id: The document ID
            version_a: First version number
            version_b: Second version number
            
        Returns:
            Comparison data dictionary
        """
        ver_a = await self.version_repo.get_version(document_id, version_a)
        ver_b = await self.version_repo.get_version(document_id, version_b)
        
        if not ver_a or not ver_b:
            raise ValueError("One or both versions not found")
        
        # Get diff
        diff_content = await self.diff_repo.get_diff_between_versions(
            document_id, version_a, version_b
        )
        
        return {
            "version_a": {
                "number": version_a,
                "title": ver_a.title,
                "content": ver_a.content,
                "content_hash": ver_a.content_hash,
                "created_at": ver_a.created_at.isoformat(),
                "changed_by": str(ver_a.changed_by) if ver_a.changed_by else None,
            },
            "version_b": {
                "number": version_b,
                "title": ver_b.title,
                "content": ver_b.content,
                "content_hash": ver_b.content_hash,
                "created_at": ver_b.created_at.isoformat(),
                "changed_by": str(ver_b.changed_by) if ver_b.changed_by else None,
            },
            "diff": diff_content,
            "same_content": ver_a.content_hash == ver_b.content_hash,
        }

    async def get_audit_log(
        self,
        document_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get audit log for a document.
        
        Args:
            document_id: The document ID
            skip: Number of entries to skip
            limit: Maximum entries to return
            
        Returns:
            List of audit log entries
        """
        logs = await self.audit_repo.get_document_audit_log(document_id, skip, limit)
        
        return [
            {
                "id": str(log.id),
                "action": log.action,
                "action_details": log.action_details,
                "user_id": str(log.user_id) if log.user_id else None,
                "version_id": str(log.version_id) if log.version_id else None,
                "ip_address": log.ip_address,
                "success": log.success,
                "error_message": log.error_message,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ]

    async def log_document_access(
        self,
        document_id: uuid.UUID,
        action: str,
        user_id: Optional[uuid.UUID] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Log document access or action.
        
        Args:
            document_id: The document ID
            action: Action being performed (view, download, share, etc.)
            user_id: ID of user performing action
            details: Additional action details
            ip_address: Client IP address
            user_agent: Client user agent
        """
        await self.audit_repo.log_action(
            document_id=document_id,
            action=action,
            user_id=user_id,
            action_details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )


def get_document_version_service(session: AsyncSession) -> DocumentVersionService:
    """Get document version service instance."""
    return DocumentVersionService(session)