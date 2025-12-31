"""Advanced Analytics API endpoints.

Provides comprehensive analytics including:
- Usage summaries
- Query patterns
- Document analytics
- Cost tracking
- Performance metrics
- Trending topics
"""

from typing import Optional
from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.db.models.user import User
from src.services.analytics_service import get_analytics_service
from pydantic import BaseModel, Field
from typing import Dict, List, Any

router = APIRouter(prefix="/analytics", tags=["analytics"])


# Response Models
class DailyCount(BaseModel):
    date: str
    count: int


class AgentCount(BaseModel):
    agent: str
    count: int


class UsageSummaryResponse(BaseModel):
    period_days: int
    total_queries: int
    daily_queries: List[DailyCount]
    avg_response_time_ms: float
    total_tokens: int
    avg_tokens_per_query: float
    queries_by_agent: List[AgentCount]
    estimated_cost: float


class KeywordCount(BaseModel):
    keyword: str
    count: int


class TimePatterns(BaseModel):
    by_hour: Dict[str, int]
    by_day_of_week: Dict[str, int]
    peak_hour: int
    peak_day: str


class QueryPatternsResponse(BaseModel):
    period_days: int
    total_queries_analyzed: int
    top_keywords: List[KeywordCount]
    query_type_distribution: Dict[str, int]
    time_patterns: TimePatterns


class DocumentTypeCount(BaseModel):
    type: str
    count: int


class DocumentAnalyticsResponse(BaseModel):
    period_days: int
    total_documents: int
    documents_by_status: Dict[str, int]
    documents_by_type: List[DocumentTypeCount]
    total_chunks: int
    avg_chunks_per_document: float


class DailyCost(BaseModel):
    date: str
    cost: float


class AgentCost(BaseModel):
    agent: str
    tokens: int
    cost: float


class CostBreakdown(BaseModel):
    llm_inference: float
    embeddings: float
    other: float


class CostTrackingResponse(BaseModel):
    period_days: int
    total_tokens: int
    total_cost: float
    daily_costs: List[DailyCost]
    cost_by_agent: List[AgentCost]
    projected_monthly_cost: float
    cost_breakdown: CostBreakdown


class ResponseTimePercentiles(BaseModel):
    p50: float = 0
    p90: float = 0
    p99: float = 0
    min: float = 0
    max: float = 0
    avg: float = 0


class PerformanceMetricsResponse(BaseModel):
    period_days: int
    total_queries: int
    response_time_percentiles: ResponseTimePercentiles
    error_rate: float
    cache_hit_rate: float
    satisfaction_rate: float
    availability: float


class TrendingTopic(BaseModel):
    topic: str
    current_count: int
    previous_count: int
    growth_rate: float
    trend: str


class DashboardResponse(BaseModel):
    """Combined dashboard data."""
    usage: UsageSummaryResponse
    performance: PerformanceMetricsResponse
    trending: List[TrendingTopic]
    document_stats: DocumentAnalyticsResponse


@router.get("/usage", response_model=UsageSummaryResponse)
async def get_usage_summary(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to analyze"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UsageSummaryResponse:
    """Get usage summary for the current user.
    
    Returns:
        Usage summary including total queries, daily breakdown, 
        response times, tokens, and cost estimates.
    """
    service = get_analytics_service(db)
    result = await service.get_usage_summary(user_id=current_user.id, days=days)
    return UsageSummaryResponse(**result)


@router.get("/usage/system", response_model=UsageSummaryResponse)
async def get_system_usage_summary(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to analyze"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UsageSummaryResponse:
    """Get system-wide usage summary (admin only).
    
    Returns:
        System-wide usage summary.
    """
    # TODO: Add admin check
    service = get_analytics_service(db)
    result = await service.get_usage_summary(user_id=None, days=days)
    return UsageSummaryResponse(**result)


@router.get("/patterns", response_model=QueryPatternsResponse)
async def get_query_patterns(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to analyze"),
    top_n: int = Query(default=20, ge=5, le=100, description="Number of top patterns"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QueryPatternsResponse:
    """Analyze query patterns for the current user.
    
    Returns:
        Query pattern analysis including top keywords,
        query types, and time patterns.
    """
    service = get_analytics_service(db)
    result = await service.get_query_patterns(
        user_id=current_user.id,
        days=days,
        top_n=top_n
    )
    return QueryPatternsResponse(**result)


@router.get("/documents", response_model=DocumentAnalyticsResponse)
async def get_document_analytics(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to analyze"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentAnalyticsResponse:
    """Get document usage analytics for the current user.
    
    Returns:
        Document analytics including counts by status and type,
        chunk statistics.
    """
    service = get_analytics_service(db)
    result = await service.get_document_analytics(user_id=current_user.id, days=days)
    return DocumentAnalyticsResponse(**result)


@router.get("/costs", response_model=CostTrackingResponse)
async def get_cost_tracking(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to analyze"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CostTrackingResponse:
    """Get cost tracking and estimation for the current user.
    
    Returns:
        Cost tracking data including daily costs, 
        cost by agent, and projections.
    """
    service = get_analytics_service(db)
    result = await service.get_cost_tracking(user_id=current_user.id, days=days)
    return CostTrackingResponse(**result)


@router.get("/costs/system", response_model=CostTrackingResponse)
async def get_system_cost_tracking(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to analyze"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CostTrackingResponse:
    """Get system-wide cost tracking (admin only).
    
    Returns:
        System-wide cost tracking data.
    """
    # TODO: Add admin check
    service = get_analytics_service(db)
    result = await service.get_cost_tracking(user_id=None, days=days)
    return CostTrackingResponse(**result)


@router.get("/performance", response_model=PerformanceMetricsResponse)
async def get_performance_metrics(
    days: int = Query(default=7, ge=1, le=90, description="Number of days to analyze"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PerformanceMetricsResponse:
    """Get performance metrics for the current user.
    
    Returns:
        Performance metrics including response time percentiles,
        error rate, cache hit rate, and satisfaction rate.
    """
    service = get_analytics_service(db)
    result = await service.get_performance_metrics(user_id=current_user.id, days=days)
    return PerformanceMetricsResponse(**result)


@router.get("/trending", response_model=List[TrendingTopic])
async def get_trending_topics(
    days: int = Query(default=7, ge=1, le=30, description="Number of days to analyze"),
    top_n: int = Query(default=10, ge=5, le=50, description="Number of topics"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[TrendingTopic]:
    """Get trending topics from recent queries.
    
    Returns:
        List of trending topics with growth metrics.
    """
    service = get_analytics_service(db)
    result = await service.get_trending_topics(days=days, top_n=top_n)
    return [TrendingTopic(**t) for t in result]


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardResponse:
    """Get combined dashboard data for quick overview.
    
    Returns:
        Combined analytics data for dashboard display.
    """
    service = get_analytics_service(db)
    
    # Gather all data concurrently
    import asyncio
    usage_task = service.get_usage_summary(user_id=current_user.id, days=30)
    performance_task = service.get_performance_metrics(user_id=current_user.id, days=7)
    trending_task = service.get_trending_topics(days=7, top_n=5)
    documents_task = service.get_document_analytics(user_id=current_user.id, days=30)
    
    usage, performance, trending, documents = await asyncio.gather(
        usage_task, performance_task, trending_task, documents_task
    )
    
    return DashboardResponse(
        usage=UsageSummaryResponse(**usage),
        performance=PerformanceMetricsResponse(**performance),
        trending=[TrendingTopic(**t) for t in trending],
        document_stats=DocumentAnalyticsResponse(**documents),
    )


@router.get("/export")
async def export_analytics(
    days: int = Query(default=30, ge=1, le=365),
    format: str = Query(default="json", pattern="^(json|csv)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export analytics data.
    
    Returns:
        Analytics data in requested format.
    """
    service = get_analytics_service(db)
    
    # Gather all analytics
    usage = await service.get_usage_summary(user_id=current_user.id, days=days)
    patterns = await service.get_query_patterns(user_id=current_user.id, days=days)
    costs = await service.get_cost_tracking(user_id=current_user.id, days=days)
    
    data = {
        "export_date": datetime.utcnow().isoformat(),
        "period_days": days,
        "usage": usage,
        "patterns": patterns,
        "costs": costs,
    }
    
    if format == "csv":
        # Convert to CSV format
        import io
        import csv
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write usage summary
        writer.writerow(["=== Usage Summary ==="])
        writer.writerow(["Total Queries", usage["total_queries"]])
        writer.writerow(["Total Tokens", usage["total_tokens"]])
        writer.writerow(["Estimated Cost", usage["estimated_cost"]])
        writer.writerow([])
        
        # Write daily queries
        writer.writerow(["=== Daily Queries ==="])
        writer.writerow(["Date", "Count"])
        for day in usage["daily_queries"]:
            writer.writerow([day["date"], day["count"]])
        writer.writerow([])
        
        # Write costs
        writer.writerow(["=== Daily Costs ==="])
        writer.writerow(["Date", "Cost"])
        for day in costs["daily_costs"]:
            writer.writerow([day["date"], day["cost"]])
        
        from fastapi.responses import StreamingResponse
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=analytics_{days}d.csv"}
        )
    
    return data