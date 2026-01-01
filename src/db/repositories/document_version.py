"""Document version repository for CRUD operations on versions.

This module provides:
1. DocumentVersionRepository - Version CRUD
2. DocumentDiffRepository - Diff operations
3. DocumentAuditLogRepository - Audit log operations
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, cast
import uuid
import hashlib
import difflib

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.repositories.base import BaseRepository
from src.db.models.document_version import (
    DocumentVersion,
    DocumentDiff,
    DocumentAuditLog,
    VersionType,
)


class DocumentVersionRepository(BaseRepository[DocumentVersion]):
    """Repository for document version operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(DocumentVersion, session)

    async def create_version(
        self,
        document_id: uuid.UUID,
        title: str,
        content: Optional[str],
        version_type: VersionType = VersionType.UPDATE,
        file_size: Optional[int] = None,
        file_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        change_summary: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
    ) -> DocumentVersion:
        """Create a new version for a document.
        
        Args:
            document_id: The document ID
            title: Document title at this version
            content: Document content at this version
            version_type: Type of version change
            file_size: File size in bytes
            file_type: File MIME type
            metadata: Additional metadata
            change_summary: Description of changes
            user_id: ID of user making the change
            
        Returns:
            Created DocumentVersion
        """
        # Get next version number
        version_number = await self._get_next_version_number(document_id)
        
        # Calculate content hash
        content_hash = None
        if content:
            content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        version = DocumentVersion(
            document_id=document_id,
            version_number=version_number,
            version_type=version_type,
            title=title,
            content=content,
            content_hash=content_hash,
            file_size=file_size,
            file_type=file_type,
            metadata=metadata or {},
            change_summary=change_summary,
            changed_by=user_id,
        )
        
        self.session.add(version)
        await self.session.flush()
        
        # Create diff from previous version
        if version_number > 1:
            await self._create_diff_from_previous(version)
        
        return version

    async def _get_next_version_number(self, document_id: uuid.UUID) -> int:
        """Get the next version number for a document."""
        result = await self.session.execute(
            select(func.max(DocumentVersion.version_number))
            .where(DocumentVersion.document_id == document_id)
        )
        max_version = result.scalar() or 0
        return max_version + 1

    async def _create_diff_from_previous(self, version: DocumentVersion) -> None:
        """Create a diff between this version and the previous one."""
        # Get previous version - cast column types to their Python equivalents
        doc_id = cast(uuid.UUID, version.document_id)
        ver_num = cast(int, version.version_number)
        prev_version = await self.get_version(
            doc_id,
            ver_num - 1
        )

        if not prev_version:
            return

        # Calculate diff - cast column types to their Python equivalents
        version_id = cast(uuid.UUID, version.id)
        prev_version_id = cast(uuid.UUID, prev_version.id)
        old_content = cast(str, prev_version.content) if prev_version.content else ""
        new_content = cast(str, version.content) if version.content else ""

        diff_repo = DocumentDiffRepository(self.session)
        await diff_repo.create_diff(
            version_id=version_id,
            from_version_id=prev_version_id,
            old_content=old_content,
            new_content=new_content,
        )

    async def get_version(
        self,
        document_id: uuid.UUID,
        version_number: int,
    ) -> Optional[DocumentVersion]:
        """Get a specific version of a document."""
        result = await self.session.execute(
            select(DocumentVersion)
            .where(
                and_(
                    DocumentVersion.document_id == document_id,
                    DocumentVersion.version_number == version_number,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_versions(
        self,
        document_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> List[DocumentVersion]:
        """Get all versions of a document."""
        result = await self.session.execute(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(desc(DocumentVersion.version_number))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_latest_version(
        self,
        document_id: uuid.UUID,
    ) -> Optional[DocumentVersion]:
        """Get the latest version of a document."""
        result = await self.session.execute(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(desc(DocumentVersion.version_number))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def count_versions(self, document_id: uuid.UUID) -> int:
        """Count versions of a document."""
        result = await self.session.execute(
            select(func.count(DocumentVersion.id))
            .where(DocumentVersion.document_id == document_id)
        )
        return result.scalar() or 0


class DocumentDiffRepository(BaseRepository[DocumentDiff]):
    """Repository for document diff operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(DocumentDiff, session)

    async def create_diff(
        self,
        version_id: uuid.UUID,
        from_version_id: Optional[uuid.UUID],
        old_content: str,
        new_content: str,
        diff_type: str = "unified",
    ) -> DocumentDiff:
        """Create a diff between two versions.
        
        Args:
            version_id: The target version ID
            from_version_id: The source version ID (None for first version)
            old_content: Previous content
            new_content: New content
            diff_type: Type of diff format
            
        Returns:
            Created DocumentDiff
        """
        # Generate unified diff
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        
        diff_generator = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile="previous",
            tofile="current",
            lineterm="",
        )
        diff_content = "".join(diff_generator)
        
        # Calculate statistics
        lines_added = sum(1 for line in diff_content.splitlines() if line.startswith("+") and not line.startswith("+++"))
        lines_removed = sum(1 for line in diff_content.splitlines() if line.startswith("-") and not line.startswith("---"))
        
        # Semantic changes (simplified)
        semantic_changes = self._extract_semantic_changes(old_content, new_content)
        
        diff = DocumentDiff(
            version_id=version_id,
            from_version_id=from_version_id,
            diff_type=diff_type,
            diff_content=diff_content,
            lines_added=lines_added,
            lines_removed=lines_removed,
            lines_changed=min(lines_added, lines_removed),
            semantic_changes=semantic_changes,
        )
        
        self.session.add(diff)
        await self.session.flush()
        
        return diff

    def _extract_semantic_changes(
        self,
        old_content: str,
        new_content: str,
    ) -> List[Dict[str, Any]]:
        """Extract semantic changes between content versions.
        
        This provides high-level change descriptions.
        """
        changes = []
        
        old_len = len(old_content)
        new_len = len(new_content)
        
        if old_len == 0 and new_len > 0:
            changes.append({"type": "created", "description": "Document created"})
        elif new_len == 0 and old_len > 0:
            changes.append({"type": "cleared", "description": "Content cleared"})
        elif abs(new_len - old_len) > old_len * 0.5:
            if new_len > old_len:
                changes.append({"type": "major_addition", "description": "Significant content added"})
            else:
                changes.append({"type": "major_removal", "description": "Significant content removed"})
        else:
            # Use sequence matcher for similarity
            ratio = difflib.SequenceMatcher(None, old_content, new_content).ratio()
            if ratio < 0.5:
                changes.append({"type": "major_rewrite", "description": "Major content rewrite"})
            elif ratio < 0.9:
                changes.append({"type": "moderate_edit", "description": "Moderate edits"})
            else:
                changes.append({"type": "minor_edit", "description": "Minor edits"})
        
        return changes

    async def get_diff(
        self,
        version_id: uuid.UUID,
    ) -> Optional[DocumentDiff]:
        """Get diff for a specific version."""
        result = await self.session.execute(
            select(DocumentDiff)
            .where(DocumentDiff.version_id == version_id)
        )
        return result.scalar_one_or_none()

    async def get_diff_between_versions(
        self,
        document_id: uuid.UUID,
        from_version: int,
        to_version: int,
    ) -> Optional[str]:
        """Get combined diff between two non-adjacent versions.
        
        Args:
            document_id: The document ID
            from_version: Start version number
            to_version: End version number
            
        Returns:
            Combined diff content
        """
        version_repo = DocumentVersionRepository(self.session)
        
        from_ver = await version_repo.get_version(document_id, from_version)
        to_ver = await version_repo.get_version(document_id, to_version)
        
        if not from_ver or not to_ver:
            return None
        
        old_content = from_ver.content or ""
        new_content = to_ver.content or ""
        
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        
        diff_generator = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"v{from_version}",
            tofile=f"v{to_version}",
            lineterm="",
        )
        
        return "".join(diff_generator)


class DocumentAuditLogRepository(BaseRepository[DocumentAuditLog]):
    """Repository for document audit log operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(DocumentAuditLog, session)

    async def log_action(
        self,
        document_id: Optional[uuid.UUID],
        action: str,
        user_id: Optional[uuid.UUID] = None,
        version_id: Optional[uuid.UUID] = None,
        action_details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> DocumentAuditLog:
        """Log a document action.
        
        Args:
            document_id: The document ID (None for deleted docs)
            action: The action performed
            user_id: ID of user performing action
            version_id: Related version ID if applicable
            action_details: Additional context
            ip_address: Client IP address
            user_agent: Client user agent
            success: Whether action succeeded
            error_message: Error message if failed
            
        Returns:
            Created audit log entry
        """
        log = DocumentAuditLog(
            document_id=document_id,
            action=action,
            user_id=user_id,
            version_id=version_id,
            action_details=action_details,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            error_message=error_message,
        )
        
        self.session.add(log)
        await self.session.flush()
        
        return log

    async def get_document_audit_log(
        self,
        document_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> List[DocumentAuditLog]:
        """Get audit log for a document."""
        result = await self.session.execute(
            select(DocumentAuditLog)
            .where(DocumentAuditLog.document_id == document_id)
            .order_by(desc(DocumentAuditLog.created_at))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_user_audit_log(
        self,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> List[DocumentAuditLog]:
        """Get audit log for a user."""
        result = await self.session.execute(
            select(DocumentAuditLog)
            .where(DocumentAuditLog.user_id == user_id)
            .order_by(desc(DocumentAuditLog.created_at))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_recent_activity(
        self,
        hours: int = 24,
        limit: int = 100,
    ) -> List[DocumentAuditLog]:
        """Get recent activity across all documents."""
        since = datetime.utcnow() - timedelta(hours=hours)
        
        result = await self.session.execute(
            select(DocumentAuditLog)
            .where(DocumentAuditLog.created_at >= since)
            .order_by(desc(DocumentAuditLog.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())


# Import needed for timedelta
from datetime import timedelta