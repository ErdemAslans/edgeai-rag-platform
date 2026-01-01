"""Log ingestion endpoints for edge-to-cloud streaming."""

import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.db.models.edge_log import EdgeLog
from src.db.session import async_session_factory
from src.schemas.ingest import LogBatchRequest, IngestResponse, LogEntry

router = APIRouter()
logger = logging.getLogger(__name__)


async def process_logs_batch(logs: List[LogEntry], batch_id: uuid.UUID) -> None:
    """Process and store log batch in background.

    This function runs in a background task to avoid blocking the HTTP response.
    It uses a new database session since BackgroundTasks run after response is sent.

    Args:
        logs: List of validated log entries to store
        batch_id: Unique identifier for this batch (for logging/debugging)
    """
    async with async_session_factory() as session:
        try:
            # Prepare log records for bulk insert
            log_records = [
                {
                    "id": log.id if log.id else uuid.uuid4(),
                    "timestamp": log.timestamp,
                    "source_id": log.source_id,
                    "level": log.level.value,
                    "message": log.message,
                    "log_metadata": log.metadata if log.metadata else {},
                    "received_at": datetime.now(timezone.utc),
                }
                for log in logs
            ]

            # Use bulk insert for efficient storage
            stmt = insert(EdgeLog).values(log_records)
            await session.execute(stmt)
            await session.commit()

            logger.info(
                f"Batch {batch_id}: Successfully stored {len(logs)} logs"
            )

        except Exception as e:
            await session.rollback()
            logger.error(
                f"Batch {batch_id}: Failed to store logs - {str(e)}"
            )
            raise


@router.post(
    "/logs",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest edge logs",
    description="Accept a batch of edge logs for async processing and storage.",
)
async def ingest_logs(
    request: LogBatchRequest,
    background_tasks: BackgroundTasks,
) -> IngestResponse:
    """Ingest a batch of edge logs.

    This endpoint accepts log batches from edge collectors and queues them
    for background processing. The response is returned immediately (202 Accepted)
    while logs are stored asynchronously.

    Args:
        request: Batch of log entries to ingest
        background_tasks: FastAPI background tasks for async processing

    Returns:
        IngestResponse with batch details and acceptance status
    """
    # Generate or use provided batch ID
    batch_id = request.batch_id if request.batch_id else uuid.uuid4()

    # Validate and count logs
    received_count = len(request.logs)

    # For now, accept all valid logs (validation is done by Pydantic)
    accepted_count = received_count

    # Queue background task for database storage
    background_tasks.add_task(
        process_logs_batch,
        request.logs,
        batch_id,
    )

    logger.info(
        f"Batch {batch_id}: Accepted {accepted_count}/{received_count} logs "
        f"from source '{request.source or 'unknown'}'"
    )

    return IngestResponse(
        status="accepted",
        batch_id=batch_id,
        received_count=received_count,
        accepted_count=accepted_count,
        rejected_count=0,
        message=f"Batch queued for processing",
        timestamp=datetime.now(timezone.utc),
    )


@router.get(
    "/health",
    summary="Ingest endpoint health",
    description="Check if the ingest endpoint is operational.",
)
async def ingest_health() -> Dict[str, Any]:
    """Health check for ingest endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "endpoint": "/api/v1/ingest",
    }
