"""Document schemas."""

import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field, ConfigDict


class DocumentBase(BaseModel):
    """Base document schema."""
    filename: str
    content_type: str


class DocumentResponse(DocumentBase):
    """Schema for document response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    user_id: uuid.UUID
    file_path: str
    file_size: int
    status: str
    chunk_count: int = 0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="doc_metadata")
    created_at: datetime
    updated_at: Optional[datetime] = None


class DocumentListResponse(BaseModel):
    """Schema for paginated document list."""
    documents: List[DocumentResponse]
    total: int
    skip: int
    limit: int


class DocumentStatusResponse(BaseModel):
    """Schema for document status response."""
    document_id: uuid.UUID
    status: str
    message: str


class ChunkBase(BaseModel):
    """Base chunk schema."""
    content: str
    chunk_index: int
    token_count: Optional[int] = None


class ChunkResponse(ChunkBase):
    """Schema for chunk response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    document_id: uuid.UUID
    metadata: Dict[str, Any] = {}
    created_at: datetime


class DocumentWithChunks(DocumentResponse):
    """Document response with chunks included."""
    chunks: List[ChunkResponse] = []