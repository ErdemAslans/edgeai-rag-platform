"""Document repository for document-specific database operations."""

import uuid
from typing import List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models.document import Document
from src.db.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    """Repository for Document model operations."""

    def __init__(self, session: AsyncSession):
        """Initialize the document repository.

        Args:
            session: The async database session.
        """
        super().__init__(Document, session)

    async def get_by_user_id(
        self,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Document]:
        """Get all documents for a user.

        Args:
            user_id: The UUID of the user.
            skip: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of document instances.
        """
        stmt = (
            select(Document)
            .where(Document.user_id == user_id)
            .offset(skip)
            .limit(limit)
            .order_by(Document.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_with_chunks(self, document_id: uuid.UUID) -> Document | None:
        """Get a document with its chunks eagerly loaded.

        Args:
            document_id: The UUID of the document.

        Returns:
            The document instance with chunks or None if not found.
        """
        stmt = (
            select(Document)
            .where(Document.id == document_id)
            .options(selectinload(Document.chunks))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_status(
        self,
        status: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Document]:
        """Get documents by processing status.

        Args:
            status: The status to filter by.
            skip: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of document instances.
        """
        stmt = (
            select(Document)
            .where(Document.status == status)
            .offset(skip)
            .limit(limit)
            .order_by(Document.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_pending_documents(self, limit: int = 10) -> List[Document]:
        """Get pending documents for processing.

        Args:
            limit: Maximum number of documents to return.

        Returns:
            List of pending document instances.
        """
        return await self.get_by_status("pending", limit=limit)

    async def update_status(
        self,
        document_id: uuid.UUID,
        status: str,
        error_message: str | None = None,
    ) -> Document | None:
        """Update the status of a document.

        Args:
            document_id: The UUID of the document.
            status: The new status.
            error_message: Optional error message if status is 'failed'.

        Returns:
            The updated document instance or None if not found.
        """
        update_data = {"status": status}
        if error_message:
            update_data["error_message"] = error_message
        return await self.update(document_id, update_data)

    async def update_chunk_count(
        self,
        document_id: uuid.UUID,
        chunk_count: int,
    ) -> Document | None:
        """Update the chunk count of a document.

        Args:
            document_id: The UUID of the document.
            chunk_count: The number of chunks.

        Returns:
            The updated document instance or None if not found.
        """
        return await self.update(document_id, {"chunk_count": chunk_count})

    async def count_by_user(self, user_id: uuid.UUID) -> int:
        """Count documents for a specific user.

        Args:
            user_id: The UUID of the user.

        Returns:
            Number of documents.
        """
        stmt = (
            select(func.count())
            .select_from(Document)
            .where(Document.user_id == user_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_total_size_by_user(self, user_id: uuid.UUID) -> int:
        """Get total file size for a user's documents.

        Args:
            user_id: The UUID of the user.

        Returns:
            Total file size in bytes.
        """
        stmt = (
            select(func.coalesce(func.sum(Document.file_size), 0))
            .where(Document.user_id == user_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def search_by_filename(
        self,
        user_id: uuid.UUID,
        filename_pattern: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Document]:
        """Search documents by filename pattern for a user.

        Args:
            user_id: The UUID of the user.
            filename_pattern: The pattern to search for (case-insensitive).
            skip: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of matching document instances.
        """
        stmt = (
            select(Document)
            .where(Document.user_id == user_id)
            .where(Document.filename.ilike(f"%{filename_pattern}%"))
            .offset(skip)
            .limit(limit)
            .order_by(Document.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_by_user(self, user_id: uuid.UUID) -> int:
        """Delete all documents for a user.

        Args:
            user_id: The UUID of the user.

        Returns:
            Number of documents deleted.
        """
        from sqlalchemy import delete

        stmt = delete(Document).where(Document.user_id == user_id)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def get_chunks(self, document_id: uuid.UUID) -> List:
        """Get all chunks for a document.

        Args:
            document_id: The UUID of the document.

        Returns:
            List of chunk instances.
        """
        from src.db.models.chunk import Chunk

        stmt = (
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.chunk_index.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())