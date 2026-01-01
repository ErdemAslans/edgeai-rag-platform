"""Document service for document management and processing."""

import uuid
import os
from pathlib import Path
from typing import List, BinaryIO
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.core.exceptions import (
    DocumentNotFoundError,
    ValidationError,
    StorageError,
)
from src.db.repositories.document import DocumentRepository
from src.db.repositories.chunk import ChunkRepository
from src.db.models.document import Document


class DocumentService:
    """Service for document management and processing."""

    ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".json", ".csv", ".docx", ".pptx", ".xlsx", ".xls", ".html", ".htm", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"}
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

    def __init__(self, session: AsyncSession):
        """Initialize the document service.

        Args:
            session: The async database session.
        """
        self.session = session
        self.document_repo = DocumentRepository(session)
        self.chunk_repo = ChunkRepository(session)
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self._ensure_upload_dir()

    def _ensure_upload_dir(self) -> None:
        """Ensure the upload directory exists."""
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def upload_document(
        self,
        user_id: uuid.UUID,
        filename: str,
        content_type: str,
        file_content: bytes,
    ) -> Document:
        """Upload a new document.

        Args:
            user_id: The ID of the user uploading the document.
            filename: Original filename.
            content_type: MIME type of the file.
            file_content: Binary content of the file.

        Returns:
            The created document instance.

        Raises:
            ValidationError: If file validation fails.
            StorageError: If file storage fails.
        """
        # Validate file extension
        ext = Path(filename).suffix.lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            raise ValidationError(
                f"File type '{ext}' not allowed. Allowed types: {', '.join(self.ALLOWED_EXTENSIONS)}"
            )

        # Validate file size
        file_size = len(file_content)
        if file_size > self.MAX_FILE_SIZE:
            raise ValidationError(
                f"File size {file_size / (1024 * 1024):.2f}MB exceeds maximum {self.MAX_FILE_SIZE / (1024 * 1024)}MB"
            )

        # Generate unique file path
        file_id = uuid.uuid4()
        stored_filename = f"{file_id}{ext}"
        file_path = self.upload_dir / str(user_id) / stored_filename

        # Ensure user directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Save file to disk
            with open(file_path, "wb") as f:
                f.write(file_content)
        except Exception as e:
            raise StorageError(f"Failed to save file: {str(e)}")

        # Create document record
        document = await self.document_repo.create({
            "user_id": user_id,
            "filename": filename,
            "content_type": content_type,
            "file_size": file_size,
            "file_path": str(file_path),
            "status": "pending",
        })

        await self.session.commit()
        return document

    async def get_document(
        self,
        document_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> Document:
        """Get a document by ID.

        Args:
            document_id: The document's UUID.
            user_id: Optional user ID to verify ownership.

        Returns:
            The document instance.

        Raises:
            DocumentNotFoundError: If document not found or access denied.
        """
        document = await self.document_repo.get_by_id(document_id)
        
        if not document:
            raise DocumentNotFoundError(f"Document with ID '{document_id}' not found")

        if user_id and document.user_id != user_id:
            raise DocumentNotFoundError(f"Document with ID '{document_id}' not found")

        return document

    async def get_document_with_chunks(
        self,
        document_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> Document:
        """Get a document with its chunks.

        Args:
            document_id: The document's UUID.
            user_id: Optional user ID to verify ownership.

        Returns:
            The document instance with chunks loaded.

        Raises:
            DocumentNotFoundError: If document not found or access denied.
        """
        document = await self.document_repo.get_with_chunks(document_id)
        
        if not document:
            raise DocumentNotFoundError(f"Document with ID '{document_id}' not found")

        if user_id and document.user_id != user_id:
            raise DocumentNotFoundError(f"Document with ID '{document_id}' not found")

        return document

    async def list_documents(
        self,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Document]:
        """List documents for a user.

        Args:
            user_id: The user's UUID.
            skip: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of document instances.
        """
        return await self.document_repo.get_by_user_id(user_id, skip=skip, limit=limit)

    async def search_documents(
        self,
        user_id: uuid.UUID,
        query: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Document]:
        """Search documents by filename.

        Args:
            user_id: The user's UUID.
            query: Search query for filename.
            skip: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of matching document instances.
        """
        return await self.document_repo.search_by_filename(
            user_id, query, skip=skip, limit=limit
        )

    async def delete_document(
        self,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Delete a document and its associated files and chunks.

        Args:
            document_id: The document's UUID.
            user_id: The user's UUID for ownership verification.

        Returns:
            True if deleted successfully.

        Raises:
            DocumentNotFoundError: If document not found or access denied.
        """
        document = await self.get_document(document_id, user_id)

        # Delete file from disk
        file_path = Path(document.file_path)
        if file_path.exists():
            try:
                file_path.unlink()
            except Exception:
                pass  # Log but don't fail if file deletion fails

        # Delete chunks (cascade should handle this, but explicit is better)
        await self.chunk_repo.delete_by_document_id(document_id)

        # Delete document record
        await self.document_repo.delete(document_id)
        await self.session.commit()

        return True

    async def update_status(
        self,
        document_id: uuid.UUID,
        status: str,
        error_message: str | None = None,
    ) -> Document:
        """Update document processing status.

        Args:
            document_id: The document's UUID.
            status: New status (pending, processing, completed, failed).
            error_message: Optional error message if status is 'failed'.

        Returns:
            The updated document instance.

        Raises:
            DocumentNotFoundError: If document not found.
        """
        document = await self.document_repo.update_status(
            document_id, status, error_message
        )
        
        if not document:
            raise DocumentNotFoundError(f"Document with ID '{document_id}' not found")

        await self.session.commit()
        return document

    async def get_document_content(self, document_id: uuid.UUID, user_id: uuid.UUID) -> str:
        """Get the text content of a document.

        Args:
            document_id: The document's UUID.
            user_id: The user's UUID for ownership verification.

        Returns:
            The text content of the document.

        Raises:
            DocumentNotFoundError: If document not found.
            StorageError: If file cannot be read.
        """
        document = await self.get_document(document_id, user_id)
        
        file_path = Path(document.file_path)
        if not file_path.exists():
            raise StorageError(f"File not found on disk: {document.file_path}")

        try:
            ext = file_path.suffix.lower()
            
            if ext == ".pdf":
                return await self._extract_pdf_text(file_path)
            elif ext in {".txt", ".md", ".json"}:
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read()
            else:
                raise ValidationError(f"Unsupported file type: {ext}")
                
        except Exception as e:
            raise StorageError(f"Failed to read file: {str(e)}")

    async def _extract_pdf_text(self, file_path: Path) -> str:
        """Extract text from a PDF file.

        Args:
            file_path: Path to the PDF file.

        Returns:
            Extracted text content.
        """
        try:
            import pypdf
            
            text_parts = []
            with open(file_path, "rb") as f:
                reader = pypdf.PdfReader(f)
                for page in reader.pages:
                    text_parts.append(page.extract_text() or "")
            
            return "\n\n".join(text_parts)
        except ImportError:
            raise StorageError("pypdf library not installed for PDF processing")
        except Exception as e:
            raise StorageError(f"Failed to extract PDF text: {str(e)}")

    async def get_user_statistics(self, user_id: uuid.UUID) -> dict:
        """Get document statistics for a user.

        Args:
            user_id: The user's UUID.

        Returns:
            Dictionary with statistics.
        """
        document_count = await self.document_repo.count_by_user(user_id)
        total_size = await self.document_repo.get_total_size_by_user(user_id)

        return {
            "document_count": document_count,
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024) if total_size else 0,
        }