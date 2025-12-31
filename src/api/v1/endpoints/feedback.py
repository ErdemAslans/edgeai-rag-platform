"""Feedback API endpoints for adaptive learning system."""

import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query as QueryParam
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db, get_current_user
from src.db.models.user import User
from src.db.models.query import Query
from src.db.repositories.feedback import (
    QueryFeedbackRepository,
    AgentPerformanceRepository,
    QueryTypePatternRepository,
)
from src.db.repositories.query import QueryRepository
from src.api.v1.schemas.feedback import (
    FeedbackCreate,
    QuickFeedback,
    FeedbackResponse,
    AgentStatsResponse,
    AgentPerformanceResponse,
    RoutingWeightsResponse,
    QueryPatternResponse,
    PatternCreateRequest,
    PatternUpdateRequest,
    LearningAnalyticsResponse,
    LearningInsight,
    FeedbackSummary,
)
from src.db.models.feedback import QueryFeedback, QueryTypePattern

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    feedback_data: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FeedbackResponse:
    """Submit feedback for a query response."""
    feedback_repo = QueryFeedbackRepository(db)
    query_repo = QueryRepository(db)
    
    # Verify query exists
    query = await query_repo.get(feedback_data.query_id)
    if not query:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query not found",
        )
    
    # Check if user already gave feedback
    has_feedback = await feedback_repo.has_user_feedback(
        feedback_data.query_id,
        current_user.id,
    )
    if has_feedback:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already submitted feedback for this query",
        )
    
    # Extract agent info from query metadata
    agent_used = "unknown"
    framework_used = None
    response_time_ms = None
    sources_count = None
    
    if query.metadata:
        agent_used = query.metadata.get("agent_type", "unknown")
        framework_used = query.metadata.get("framework")
        response_time_ms = query.metadata.get("processing_time_ms")
        sources_count = query.metadata.get("sources_count")
    
    # Create feedback
    feedback = QueryFeedback(
        query_id=feedback_data.query_id,
        user_id=current_user.id,
        feedback_type=feedback_data.feedback_type.value,
        is_positive=feedback_data.is_positive,
        rating=feedback_data.rating,
        category=feedback_data.category.value if feedback_data.category else None,
        comment=feedback_data.comment,
        agent_used=agent_used,
        framework_used=framework_used,
        response_time_ms=response_time_ms,
        sources_count=sources_count,
    )
    
    created_feedback = await feedback_repo.create(feedback)
    await db.commit()
    
    return created_feedback


@router.post("/quick", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_quick_feedback(
    feedback_data: QuickFeedback,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FeedbackResponse:
    """Submit quick thumbs up/down feedback."""
    feedback_repo = QueryFeedbackRepository(db)
    query_repo = QueryRepository(db)
    
    # Verify query exists
    query = await query_repo.get(feedback_data.query_id)
    if not query:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query not found",
        )
    
    # Check if user already gave feedback
    has_feedback = await feedback_repo.has_user_feedback(
        feedback_data.query_id,
        current_user.id,
    )
    if has_feedback:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already submitted feedback for this query",
        )
    
    # Extract agent info from query metadata
    agent_used = "unknown"
    framework_used = None
    response_time_ms = None
    sources_count = None
    
    if query.metadata:
        agent_used = query.metadata.get("agent_type", "unknown")
        framework_used = query.metadata.get("framework")
        response_time_ms = query.metadata.get("processing_time_ms")
        sources_count = query.metadata.get("sources_count")
    
    # Create feedback
    feedback_type = "thumbs_up" if feedback_data.is_positive else "thumbs_down"
    feedback = QueryFeedback(
        query_id=feedback_data.query_id,
        user_id=current_user.id,
        feedback_type=feedback_type,
        is_positive=feedback_data.is_positive,
        agent_used=agent_used,
        framework_used=framework_used,
        response_time_ms=response_time_ms,
        sources_count=sources_count,
    )
    
    created_feedback = await feedback_repo.create(feedback)
    await db.commit()
    
    return created_feedback


@router.get("/my", response_model=List[FeedbackResponse])
async def get_my_feedback(
    limit: int = QueryParam(default=50, ge=1, le=100),
    offset: int = QueryParam(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[FeedbackResponse]:
    """Get feedback submitted by the current user."""
    feedback_repo = QueryFeedbackRepository(db)
    feedbacks = await feedback_repo.get_by_user(
        current_user.id,
        limit=limit,
        offset=offset,
    )
    return feedbacks


@router.get("/query/{query_id}", response_model=List[FeedbackResponse])
async def get_query_feedback(
    query_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[FeedbackResponse]:
    """Get all feedback for a specific query."""
    feedback_repo = QueryFeedbackRepository(db)
    feedbacks = await feedback_repo.get_by_query_id(query_id)
    return feedbacks


# Agent Statistics Endpoints
@router.get("/stats/agent/{agent_name}", response_model=AgentStatsResponse)
async def get_agent_stats(
    agent_name: str,
    days: int = QueryParam(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgentStatsResponse:
    """Get statistics for a specific agent."""
    feedback_repo = QueryFeedbackRepository(db)
    since = datetime.utcnow() - timedelta(days=days)
    stats = await feedback_repo.get_agent_stats(agent_name, since)
    return AgentStatsResponse(**stats)


@router.get("/stats/all", response_model=List[AgentStatsResponse])
async def get_all_agent_stats(
    days: int = QueryParam(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[AgentStatsResponse]:
    """Get statistics for all agents."""
    feedback_repo = QueryFeedbackRepository(db)
    since = datetime.utcnow() - timedelta(days=days)
    
    # Get unique agents from feedback
    from sqlalchemy import select, distinct
    from src.db.models.feedback import QueryFeedback as QF
    
    result = await db.execute(
        select(distinct(QF.agent_used)).where(QF.created_at >= since)
    )
    agents = [row[0] for row in result.all()]
    
    stats_list = []
    for agent_name in agents:
        stats = await feedback_repo.get_agent_stats(agent_name, since)
        stats_list.append(AgentStatsResponse(**stats))
    
    return stats_list


# Performance Metrics Endpoints
@router.get("/performance", response_model=List[AgentPerformanceResponse])
async def get_performance_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[AgentPerformanceResponse]:
    """Get latest performance metrics for all agents."""
    perf_repo = AgentPerformanceRepository(db)
    metrics = await perf_repo.get_all_latest_metrics()
    
    return [
        AgentPerformanceResponse(
            id=m.id,
            agent_name=m.agent_name,
            framework=m.framework,
            period_start=m.period_start,
            period_end=m.period_end,
            total_queries=m.total_queries,
            positive_feedbacks=m.positive_feedbacks,
            negative_feedbacks=m.negative_feedbacks,
            avg_rating=m.avg_rating,
            avg_response_time_ms=m.avg_response_time_ms,
            routing_weight=m.routing_weight,
            satisfaction_rate=m.satisfaction_rate,
        )
        for m in metrics
    ]


@router.get("/routing-weights", response_model=RoutingWeightsResponse)
async def get_routing_weights(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RoutingWeightsResponse:
    """Get current routing weights for all agents."""
    perf_repo = AgentPerformanceRepository(db)
    weights = await perf_repo.get_routing_weights()
    
    return RoutingWeightsResponse(
        weights=weights,
        last_updated=datetime.utcnow(),
    )


# Query Pattern Endpoints
@router.get("/patterns", response_model=List[QueryPatternResponse])
async def get_query_patterns(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[QueryPatternResponse]:
    """Get all query type patterns."""
    pattern_repo = QueryTypePatternRepository(db)
    
    if include_inactive:
        from sqlalchemy import select
        result = await db.execute(select(QueryTypePattern))
        patterns = list(result.scalars().all())
    else:
        patterns = await pattern_repo.get_active_patterns()
    
    return patterns


@router.post("/patterns", response_model=QueryPatternResponse, status_code=status.HTTP_201_CREATED)
async def create_pattern(
    pattern_data: PatternCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QueryPatternResponse:
    """Create a new query type pattern."""
    pattern_repo = QueryTypePatternRepository(db)
    
    # Check if pattern name already exists
    existing = await pattern_repo.get_by_pattern_name(pattern_data.pattern_name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Pattern with name '{pattern_data.pattern_name}' already exists",
        )
    
    pattern = QueryTypePattern(
        pattern_name=pattern_data.pattern_name,
        pattern_description=pattern_data.pattern_description,
        keywords=pattern_data.keywords,
        best_agent=pattern_data.best_agent,
        best_framework=pattern_data.best_framework,
    )
    
    created_pattern = await pattern_repo.create(pattern)
    await db.commit()
    
    return created_pattern


@router.patch("/patterns/{pattern_id}", response_model=QueryPatternResponse)
async def update_pattern(
    pattern_id: uuid.UUID,
    pattern_data: PatternUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QueryPatternResponse:
    """Update a query type pattern."""
    pattern_repo = QueryTypePatternRepository(db)
    
    pattern = await pattern_repo.get(pattern_id)
    if not pattern:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pattern not found",
        )
    
    # Update fields
    if pattern_data.pattern_name is not None:
        pattern.pattern_name = pattern_data.pattern_name
    if pattern_data.pattern_description is not None:
        pattern.pattern_description = pattern_data.pattern_description
    if pattern_data.keywords is not None:
        pattern.keywords = pattern_data.keywords
    if pattern_data.best_agent is not None:
        pattern.best_agent = pattern_data.best_agent
    if pattern_data.best_framework is not None:
        pattern.best_framework = pattern_data.best_framework
    if pattern_data.is_active is not None:
        pattern.is_active = pattern_data.is_active
    
    pattern.updated_at = datetime.utcnow()
    await db.commit()
    
    return pattern


@router.delete("/patterns/{pattern_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pattern(
    pattern_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a query type pattern."""
    pattern_repo = QueryTypePatternRepository(db)
    
    pattern = await pattern_repo.get(pattern_id)
    if not pattern:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pattern not found",
        )
    
    await pattern_repo.delete(pattern_id)
    await db.commit()


# Analytics Endpoints
@router.get("/analytics", response_model=LearningAnalyticsResponse)
async def get_learning_analytics(
    days: int = QueryParam(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LearningAnalyticsResponse:
    """Get learning analytics and insights."""
    feedback_repo = QueryFeedbackRepository(db)
    pattern_repo = QueryTypePatternRepository(db)
    
    since = datetime.utcnow() - timedelta(days=days)
    
    # Get all agent stats
    from sqlalchemy import select, distinct, func
    from src.db.models.feedback import QueryFeedback as QF
    
    result = await db.execute(
        select(distinct(QF.agent_used)).where(QF.created_at >= since)
    )
    agents = [row[0] for row in result.all()]
    
    agents_performance = []
    total_feedback = 0
    total_positive = 0
    
    for agent_name in agents:
        stats = await feedback_repo.get_agent_stats(agent_name, since)
        agents_performance.append(AgentStatsResponse(**stats))
        total_feedback += stats["total_feedback"]
        total_positive += stats["positive_feedback"]
    
    # Get active patterns count
    patterns = await pattern_repo.get_active_patterns()
    
    # Generate insights
    insights = []
    
    # Insight: Best performing agent
    if agents_performance:
        best_agent = max(agents_performance, key=lambda x: x.satisfaction_rate)
        if best_agent.satisfaction_rate > 0.8:
            insights.append(LearningInsight(
                insight_type="best_performer",
                title=f"{best_agent.agent_name} is performing well",
                description=f"With a {best_agent.satisfaction_rate:.1%} satisfaction rate, this agent is delivering quality responses.",
                impact="high",
                recommendation="Consider routing more similar queries to this agent.",
                data={"agent": best_agent.agent_name, "satisfaction": best_agent.satisfaction_rate},
            ))
    
    # Insight: Underperforming agent
    if agents_performance:
        worst_agent = min(agents_performance, key=lambda x: x.satisfaction_rate)
        if worst_agent.satisfaction_rate < 0.5 and worst_agent.total_feedback >= 10:
            insights.append(LearningInsight(
                insight_type="underperformer",
                title=f"{worst_agent.agent_name} needs attention",
                description=f"With only {worst_agent.satisfaction_rate:.1%} satisfaction, this agent may need prompt optimization.",
                impact="high",
                recommendation="Review negative feedback categories and optimize prompts.",
                data={
                    "agent": worst_agent.agent_name,
                    "satisfaction": worst_agent.satisfaction_rate,
                    "categories": worst_agent.category_breakdown,
                },
            ))
    
    # Insight: Low feedback volume
    if total_feedback < 20:
        insights.append(LearningInsight(
            insight_type="low_data",
            title="Need more feedback for reliable learning",
            description=f"Only {total_feedback} feedback entries in the last {days} days.",
            impact="medium",
            recommendation="Encourage users to provide feedback after queries.",
            data={"total_feedback": total_feedback},
        ))
    
    return LearningAnalyticsResponse(
        total_feedback_count=total_feedback,
        positive_rate=total_positive / total_feedback if total_feedback > 0 else 0.5,
        agents_performance=agents_performance,
        active_patterns_count=len(patterns),
        insights=insights,
        period_start=since,
        period_end=datetime.utcnow(),
    )


@router.get("/summary", response_model=FeedbackSummary)
async def get_feedback_summary(
    days: int = QueryParam(default=7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FeedbackSummary:
    """Get a summary of recent feedback."""
    feedback_repo = QueryFeedbackRepository(db)
    since = datetime.utcnow() - timedelta(days=days)
    previous_since = since - timedelta(days=days)
    
    from sqlalchemy import select, func, distinct
    from src.db.models.feedback import QueryFeedback as QF
    
    # Get current period stats
    result = await db.execute(
        select(distinct(QF.agent_used)).where(QF.created_at >= since)
    )
    agents = [row[0] for row in result.all()]
    
    by_agent = {}
    total_positive = 0
    total_negative = 0
    by_category = {}
    
    for agent_name in agents:
        stats = await feedback_repo.get_agent_stats(agent_name, since)
        by_agent[agent_name] = {
            "positive": stats["positive_feedback"],
            "negative": stats["negative_feedback"],
        }
        total_positive += stats["positive_feedback"]
        total_negative += stats["negative_feedback"]
        
        for cat, count in stats["category_breakdown"].items():
            by_category[cat] = by_category.get(cat, 0) + count
    
    total = total_positive + total_negative
    current_rate = total_positive / total if total > 0 else 0.5
    
    # Get previous period for trend
    prev_positive = 0
    prev_negative = 0
    for agent_name in agents:
        stats = await feedback_repo.get_agent_stats(agent_name, previous_since)
        # Filter to only previous period
        prev_positive += stats["positive_feedback"]
        prev_negative += stats["negative_feedback"]
    
    prev_total = prev_positive + prev_negative
    prev_rate = prev_positive / prev_total if prev_total > 0 else 0.5
    
    # Determine trend
    if current_rate > prev_rate + 0.05:
        trend = "improving"
    elif current_rate < prev_rate - 0.05:
        trend = "declining"
    else:
        trend = "stable"
    
    return FeedbackSummary(
        total_feedbacks=total,
        positive_feedbacks=total_positive,
        negative_feedbacks=total_negative,
        satisfaction_rate=current_rate,
        by_agent=by_agent,
        by_category=by_category,
        trend=trend,
    )