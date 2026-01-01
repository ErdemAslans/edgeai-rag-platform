"""EdgeLog database model for storing edge device log entries."""

import uuid
from datetime import datetime
from typing import Dict, Any

from sqlalchemy import String, DateTime, Text, PrimaryKeyConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class EdgeLog(Base):
    """EdgeLog model for storing edge device logs with timeseries optimization.

    This model uses a composite primary key (id, timestamp) to support
    PostgreSQL table partitioning by timestamp range for efficient
    time-series queries and storage management.
    """

    __tablename__ = "edge_logs"

    # CRITICAL: Composite primary key required for PostgreSQL partitioning
    __table_args__ = (
        PrimaryKeyConstraint("id", "timestamp"),
        {"postgresql_partition_by": "RANGE (timestamp)"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        default=uuid.uuid4,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    source_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    log_metadata: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<EdgeLog(id={self.id}, source={self.source_id}, level={self.level}, timestamp={self.timestamp})>"
