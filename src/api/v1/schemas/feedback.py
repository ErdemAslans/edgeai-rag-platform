"""Schemas for feedback and adaptive learning API."""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from pydantic import BaseModel, Field, validator


class FeedbackType(str, Enum):
    """Types of feedback."""
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    RATING = "rating"
    DETAILED = "detailed"


class FeedbackCategory(str, Enum):
    """Categories for negative feedback."""
    IRRELEVANT = "irrelevant"
    INCOMPLETE = "incomplete"
    INCORRECT = "incorrect"
    TOO_LONG = "too_long"
    TOO_SHORT = "too_short"
    WRONG_SOURCES = "wrong_sources"
    SLOW = "slow"
    OTHER = "other"


# Request schemas
class FeedbackCreate(BaseModel):
    """Schema for creating feedback."""
    query_id: uuid.UUID = Field(..., description="ID of the query being rated")
    feedback_type: FeedbackType = Field(
        default=FeedbackType.THUMBS_UP,
        description="Type of feedback"
    )
    is_positive: bool = Field(..., description="Whether feedback is positive")
    rating: Optional[int] = Field(
        None,
        ge=1,
        le=5,
        description="Rating from 1-5 (only for rating type)"
    )
    category: Optional[FeedbackCategory] = Field(
        None,
        description="Category for negative feedback"
    )
    comment: Optional[str] = Field(
        None,
        max_length=1000,
        description="Optional comment"
    )

    @validator("rating")
    def validate_rating(cls, v: Optional[int], values: Dict[str, Any]) -> Optional[int]:
        if values.get("feedback_type") == FeedbackType.RATING and v is None:
            raise ValueError("Rating is required for rating type feedback")
        return v

    @validator("category")
    def validate_category(
        cls, v: Optional[FeedbackCategory], values: Dict[str, Any]
    ) -> Optional[FeedbackCategory]:
        if not values.get("is_positive") and v is None and values.get("feedback_type") == FeedbackType.DETAILED:
            raise ValueError("Category is required for detailed negative feedback")
        return v


class QuickFeedback(BaseModel):
    """Schema for quick thumbs up/down feedback."""
    query_id: uuid.UUID = Field(..., description="ID of the query being rated")
    is_positive: bool = Field(..., description="Thumbs up (true) or thumbs down (false)")


# Response schemas
class FeedbackResponse(BaseModel):
    """Schema for feedback response."""
    id: uuid.UUID
    query_id: uuid.UUID
    user_id: uuid.UUID
    feedback_type: str
    is_positive: bool
    rating: Optional[int] = None
    category: Optional[str] = None
    comment: Optional[str] = None
    agent_used: str
    created_at: datetime

    class Config:
        from_attributes = True


class AgentStatsResponse(BaseModel):
    """Schema for agent statistics."""
    agent_name: str
    total_feedback: int
    positive_feedback: int
    negative_feedback: int
    satisfaction_rate: float = Field(..., ge=0, le=1)
    avg_rating: Optional[float] = None
    category_breakdown: Dict[str, int]
    period_start: str
    period_end: str


class AgentPerformanceResponse(BaseModel):
    """Schema for agent performance metrics."""
    id: uuid.UUID
    agent_name: str
    framework: Optional[str] = None
    period_start: datetime
    period_end: datetime
    total_queries: int
    positive_feedbacks: int
    negative_feedbacks: int
    avg_rating: Optional[float] = None
    avg_response_time_ms: Optional[float] = None
    routing_weight: float
    satisfaction_rate: float

    class Config:
        from_attributes = True


class RoutingWeightsResponse(BaseModel):
    """Schema for routing weights."""
    weights: Dict[str, float] = Field(
        ...,
        description="Agent name to routing weight mapping"
    )
    last_updated: datetime


class QueryPatternResponse(BaseModel):
    """Schema for query type pattern."""
    id: uuid.UUID
    pattern_name: str
    pattern_description: Optional[str] = None
    keywords: List[str]
    best_agent: str
    best_framework: Optional[str] = None
    sample_size: int
    confidence: float
    avg_satisfaction: float
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PatternCreateRequest(BaseModel):
    """Schema for creating a new query pattern."""
    pattern_name: str = Field(..., min_length=1, max_length=100)
    pattern_description: Optional[str] = None
    keywords: List[str] = Field(..., min_length=1)
    best_agent: str
    best_framework: Optional[str] = None


class PatternUpdateRequest(BaseModel):
    """Schema for updating a query pattern."""
    pattern_name: Optional[str] = Field(None, min_length=1, max_length=100)
    pattern_description: Optional[str] = None
    keywords: Optional[List[str]] = None
    best_agent: Optional[str] = None
    best_framework: Optional[str] = None
    is_active: Optional[bool] = None


# Analytics schemas
class LearningInsight(BaseModel):
    """Schema for learning insights."""
    insight_type: str
    title: str
    description: str
    impact: str  # "high", "medium", "low"
    recommendation: str
    data: Dict[str, Any]


class LearningAnalyticsResponse(BaseModel):
    """Schema for learning analytics."""
    total_feedback_count: int
    positive_rate: float
    agents_performance: List[AgentStatsResponse]
    active_patterns_count: int
    insights: List[LearningInsight]
    period_start: datetime
    period_end: datetime


class FeedbackSummary(BaseModel):
    """Schema for feedback summary."""
    total_feedbacks: int
    positive_feedbacks: int
    negative_feedbacks: int
    satisfaction_rate: float
    by_agent: Dict[str, Dict[str, int]]
    by_category: Dict[str, int]
    trend: str  # "improving", "stable", "declining"