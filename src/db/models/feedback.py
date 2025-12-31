"""Feedback database model for adaptive learning system."""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional, TYPE_CHECKING

from sqlalchemy import String, Float, DateTime, ForeignKey, Text, Integer, Boolean, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from src.db.base import Base

if TYPE_CHECKING:
    from src.db.models.user import User
    from src.db.models.query import Query


class FeedbackType(str, enum.Enum):
    """Types of feedback."""
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    RATING = "rating"  # 1-5 scale
    DETAILED = "detailed"  # With text comment


class FeedbackCategory(str, enum.Enum):
    """Categories for negative feedback."""
    IRRELEVANT = "irrelevant"  # Answer not related to question
    INCOMPLETE = "incomplete"  # Answer missing information
    INCORRECT = "incorrect"  # Factually wrong
    TOO_LONG = "too_long"
    TOO_SHORT = "too_short"
    WRONG_SOURCES = "wrong_sources"  # Used wrong documents
    SLOW = "slow"  # Response too slow
    OTHER = "other"


class QueryFeedback(Base):
    """User feedback on query responses for adaptive learning."""

    __tablename__ = "query_feedbacks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    query_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("queries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Feedback type and value
    feedback_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=FeedbackType.THUMBS_UP.value,
    )
    is_positive: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        index=True,
    )
    rating: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,  # 1-5 for rating type
    )
    
    # Detailed feedback
    category: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Context at time of feedback
    agent_used: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    framework_used: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    response_time_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    sources_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    
    # For learning
    query_embedding_hash: Mapped[str | None] = mapped_column(
        String(64),  # SHA256 hash of query embedding for similarity
        nullable=True,
        index=True,
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    query: Mapped["Query"] = relationship(
        "Query",
        backref="feedbacks",
    )
    user: Mapped["User"] = relationship(
        "User",
        backref="feedbacks",
    )

    def __repr__(self) -> str:
        return f"<QueryFeedback(id={self.id}, positive={self.is_positive}, agent={self.agent_used})>"


class AgentPerformanceMetrics(Base):
    """Aggregated performance metrics for each agent."""

    __tablename__ = "agent_performance_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    agent_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    framework: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    
    # Time period
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    
    # Metrics
    total_queries: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    positive_feedbacks: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    negative_feedbacks: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    avg_rating: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    avg_response_time_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    
    # Routing weight (0.0 - 1.0)
    routing_weight: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
    )
    
    # Category breakdown (JSON)
    category_breakdown: Mapped[Dict[str, int]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<AgentPerformanceMetrics(agent={self.agent_name}, queries={self.total_queries})>"

    @property
    def satisfaction_rate(self) -> float:
        """Calculate satisfaction rate."""
        total_feedback = self.positive_feedbacks + self.negative_feedbacks
        if total_feedback == 0:
            return 0.5  # Neutral when no feedback
        return self.positive_feedbacks / total_feedback


class QueryTypePattern(Base):
    """Patterns learned about query types and best agents."""

    __tablename__ = "query_type_patterns"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    # Pattern identification
    pattern_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    pattern_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Keywords/patterns to match
    keywords: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    
    # Best performing agent for this pattern
    best_agent: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    best_framework: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    
    # Confidence based on sample size
    sample_size: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        default=0.5,
        nullable=False,
    )
    
    # Performance metrics for this pattern
    avg_satisfaction: Mapped[float] = mapped_column(
        Float,
        default=0.5,
        nullable=False,
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<QueryTypePattern(name={self.pattern_name}, agent={self.best_agent}, confidence={self.confidence})>"