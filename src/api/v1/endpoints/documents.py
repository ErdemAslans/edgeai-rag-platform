"""Document management endpoints."""

import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db, CurrentUser
from src.api.v1.schemas.documents import (
    DocumentResponse,
    DocumentListResponse,
    DocumentStatusResponse,
    ChunkResponse,
)
from src.config import settings
from src.db.repositories.document import DocumentRepository

router = APIRouter()


def validate_file_extension(filename: str) -> bool:
    """Validate file extension against allowed extensions."""
    if not filename:
        return False
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in settings.ALLOWED_EXTENSIONS


def validate_file_size(file_size: int) -> bool:
    """Validate file size against maximum allowed size."""
    max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    return file_size <= max_size


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: CurrentUser = None,
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Upload a new document for processing."""
    # Validate file extension
    if not validate_file_extension(file.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed types: {settings.ALLOWED_EXTENSIONS}",
        )
    
    # Read file content to check size
    content = await file.read()
    if not validate_file_size(len(content)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB",
        )
    
    # Reset file position
    await file.seek(0)
    
    # Generate unique filename
    file_ext = file.filename.rsplit(".", 1)[-1].lower()
    unique_filename = f"{uuid.uuid4()}.{file_ext}"
    
    # Ensure upload directory exists
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    storage_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
    
    # Save file
    with open(storage_path, "wb") as f:
        f.write(content)
    
    # Create document record
    doc_repo = DocumentRepository(db)
    document = await doc_repo.create({
        "user_id": current_user.id,
        "filename": file.filename,
        "content_type": file.content_type or "application/octet-stream",
        "storage_path": storage_path,
        "file_size": len(content),
    })
    
    # TODO: Trigger async document processing pipeline
    
    return DocumentResponse.model_validate(document)


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
) -> DocumentListResponse:
    """List all documents for the current user."""
    doc_repo = DocumentRepository(db)
    
    documents = await doc_repo.get_by_user_id(
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    total = await doc_repo.count_by_user(user_id=current_user.id)
    
    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(doc) for doc in documents],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Get a specific document by ID."""
    doc_repo = DocumentRepository(db)
    document = await doc_repo.get_by_id(document_id)
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    if document.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this document",
        )
    
    return DocumentResponse.model_validate(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a document."""
    doc_repo = DocumentRepository(db)
    document = await doc_repo.get_by_id(document_id)
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    if document.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this document",
        )
    
    # Delete file from storage
    if os.path.exists(document.storage_path):
        os.remove(document.storage_path)
    
    # Delete document record (cascades to chunks)
    await doc_repo.delete(document_id)


@router.get("/{document_id}/chunks", response_model=List[ChunkResponse])
async def get_document_chunks(
    document_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> List[ChunkResponse]:
    """Get all chunks for a document."""
    doc_repo = DocumentRepository(db)
    document = await doc_repo.get_by_id(document_id)
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    if document.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this document",
        )
    
    chunks = await doc_repo.get_chunks(document_id)
    return [ChunkResponse.model_validate(chunk) for chunk in chunks]


@router.post("/{document_id}/reprocess", response_model=DocumentStatusResponse)
async def reprocess_document(
    document_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> DocumentStatusResponse:
    """Reprocess a document (re-run ingestion pipeline)."""
    doc_repo = DocumentRepository(db)
    document = await doc_repo.get_by_id(document_id)
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    if document.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to reprocess this document",
        )
    
    # Update status to pending
    await doc_repo.update_status(document_id, "pending")
    
    # TODO: Trigger async document processing pipeline
    
    return DocumentStatusResponse(
        document_id=document_id,
        status="pending",
        message="Document queued for reprocessing",
    )


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> DocumentStatusResponse:
    """Get the processing status of a document."""
    doc_repo = DocumentRepository(db)
    document = await doc_repo.get_by_id(document_id)
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    if document.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this document",
        )
    
    return DocumentStatusResponse(
        document_id=document_id,
        status=document.status,
        message=f"Document is {document.status}",
    )