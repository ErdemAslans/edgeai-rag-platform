"""Schemas for edge-to-cloud log ingestion API."""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from pydantic import BaseModel, Field, validator


class LogLevel(str, Enum):
    """Log severity levels."""
    TRACE = "trace"
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    FATAL = "fatal"


# Request schemas
class LogEntry(BaseModel):
    """Schema for a single edge log entry."""
    id: Optional[uuid.UUID] = Field(
        default=None,
        description="Optional client-generated log ID"
    )
    timestamp: datetime = Field(
        ...,
        description="Timestamp when the log was generated at edge"
    )
    source_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Identifier of the edge device or sensor"
    )
    level: LogLevel = Field(
        ...,
        description="Log severity level"
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Log message content"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional structured metadata"
    )

    @validator("timestamp")
    def validate_timestamp(cls, v):
        """Ensure timestamp is not in the future (with 1 minute tolerance)."""
        from datetime import timezone, timedelta
        now = datetime.now(timezone.utc)
        if v.tzinfo is None:
            # Assume UTC if no timezone
            v = v.replace(tzinfo=timezone.utc)
        if v > now + timedelta(minutes=1):
            raise ValueError("Timestamp cannot be in the future")
        return v


class LogBatchRequest(BaseModel):
    """Schema for batch log ingestion request."""
    logs: List[LogEntry] = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="List of log entries to ingest (max 1000 per batch)"
    )
    batch_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Optional client-generated batch ID for idempotency"
    )
    source: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Identifier of the edge collector sending the batch"
    )


# Response schemas
class IngestResponse(BaseModel):
    """Schema for log ingestion response."""
    status: str = Field(
        ...,
        description="Ingestion status (accepted, rejected)"
    )
    batch_id: uuid.UUID = Field(
        ...,
        description="Server-assigned or client-provided batch ID"
    )
    received_count: int = Field(
        ...,
        ge=0,
        description="Number of logs received"
    )
    accepted_count: int = Field(
        ...,
        ge=0,
        description="Number of logs accepted for processing"
    )
    rejected_count: int = Field(
        default=0,
        ge=0,
        description="Number of logs rejected due to validation errors"
    )
    message: Optional[str] = Field(
        default=None,
        description="Additional status message"
    )
    errors: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Validation errors for rejected logs"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(),
        description="Server timestamp of response"
    )

    class Config:
        from_attributes = True
