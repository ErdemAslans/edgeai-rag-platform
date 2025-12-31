"""Repository for feedback and adaptive learning data."""

import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.repositories.base import BaseRepository
from src.db.models.feedback import (
    QueryFeedback,
    AgentPerformanceMetrics,
    QueryTypePattern,
    FeedbackType,
    FeedbackCategory,
)


class QueryFeedbackRepository(BaseRepository[QueryFeedback]):
    """Repository for query feedback operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(QueryFeedback, session)

    async def get_by_query_id(self, query_id: uuid.UUID) -> List[QueryFeedback]:
        """Get all feedback for a specific query."""
        result = await self.session.execute(
            select(QueryFeedback).where(QueryFeedback.query_id == query_id)
        )
        return list(result.scalars().all())

    async def get_by_user(
        self,
        user_id: uuid.UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> List[QueryFeedback]:
        """Get feedback submitted by a user."""
        result = await self.session.execute(
            select(QueryFeedback)
            .where(QueryFeedback.user_id == user_id)
            .order_by(QueryFeedback.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_by_agent(
        self,
        agent_name: str,
        since: Optional[datetime] = None,
        is_positive: Optional[bool] = None,
    ) -> List[QueryFeedback]:
        """Get feedback for a specific agent."""
        query = select(QueryFeedback).where(QueryFeedback.agent_used == agent_name)
        
        if since:
            query = query.where(QueryFeedback.created_at >= since)
        if is_positive is not None:
            query = query.where(QueryFeedback.is_positive == is_positive)
        
        result = await self.session.execute(
            query.order_by(QueryFeedback.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_agent_stats(
        self,
        agent_name: str,
        since: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get aggregated stats for an agent."""
        if since is None:
            since = datetime.utcnow() - timedelta(days=30)
        
        # Total feedback count
        total_query = select(func.count(QueryFeedback.id)).where(
            and_(
                QueryFeedback.agent_used == agent_name,
                QueryFeedback.created_at >= since,
            )
        )
        total_result = await self.session.execute(total_query)
        total = total_result.scalar() or 0
        
        # Positive feedback count
        positive_query = select(func.count(QueryFeedback.id)).where(
            and_(
                QueryFeedback.agent_used == agent_name,
                QueryFeedback.created_at >= since,
                QueryFeedback.is_positive == True,
            )
        )
        positive_result = await self.session.execute(positive_query)
        positive = positive_result.scalar() or 0
        
        # Average rating (for rating type feedback)
        avg_rating_query = select(func.avg(QueryFeedback.rating)).where(
            and_(
                QueryFeedback.agent_used == agent_name,
                QueryFeedback.created_at >= since,
                QueryFeedback.rating.isnot(None),
            )
        )
        avg_rating_result = await self.session.execute(avg_rating_query)
        avg_rating = avg_rating_result.scalar()
        
        # Category breakdown for negative feedback
        category_query = select(
            QueryFeedback.category,
            func.count(QueryFeedback.id)
        ).where(
            and_(
                QueryFeedback.agent_used == agent_name,
                QueryFeedback.created_at >= since,
                QueryFeedback.is_positive == False,
                QueryFeedback.category.isnot(None),
            )
        ).group_by(QueryFeedback.category)
        
        category_result = await self.session.execute(category_query)
        category_breakdown = {row[0]: row[1] for row in category_result.all()}
        
        return {
            "agent_name": agent_name,
            "total_feedback": total,
            "positive_feedback": positive,
            "negative_feedback": total - positive,
            "satisfaction_rate": positive / total if total > 0 else 0.5,
            "avg_rating": float(avg_rating) if avg_rating else None,
            "category_breakdown": category_breakdown,
            "period_start": since.isoformat(),
            "period_end": datetime.utcnow().isoformat(),
        }

    async def has_user_feedback(
        self,
        query_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Check if user already gave feedback for a query."""
        result = await self.session.execute(
            select(func.count(QueryFeedback.id)).where(
                and_(
                    QueryFeedback.query_id == query_id,
                    QueryFeedback.user_id == user_id,
                )
            )
        )
        return (result.scalar() or 0) > 0


class AgentPerformanceRepository(BaseRepository[AgentPerformanceMetrics]):
    """Repository for agent performance metrics."""

    def __init__(self, session: AsyncSession):
        super().__init__(AgentPerformanceMetrics, session)

    async def get_latest_metrics(
        self,
        agent_name: str,
        framework: Optional[str] = None,
    ) -> Optional[AgentPerformanceMetrics]:
        """Get the latest metrics for an agent."""
        query = select(AgentPerformanceMetrics).where(
            AgentPerformanceMetrics.agent_name == agent_name
        )
        if framework:
            query = query.where(AgentPerformanceMetrics.framework == framework)
        
        query = query.order_by(AgentPerformanceMetrics.period_end.desc()).limit(1)
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_all_latest_metrics(self) -> List[AgentPerformanceMetrics]:
        """Get latest metrics for all agents."""
        # Subquery to get max period_end for each agent
        subquery = (
            select(
                AgentPerformanceMetrics.agent_name,
                func.max(AgentPerformanceMetrics.period_end).label("max_period")
            )
            .group_by(AgentPerformanceMetrics.agent_name)
            .subquery()
        )
        
        # Main query to get the records
        query = select(AgentPerformanceMetrics).join(
            subquery,
            and_(
                AgentPerformanceMetrics.agent_name == subquery.c.agent_name,
                AgentPerformanceMetrics.period_end == subquery.c.max_period,
            )
        )
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_routing_weights(self) -> Dict[str, float]:
        """Get current routing weights for all agents."""
        metrics = await self.get_all_latest_metrics()
        return {m.agent_name: m.routing_weight for m in metrics}

    async def update_routing_weight(
        self,
        agent_name: str,
        new_weight: float,
    ) -> Optional[AgentPerformanceMetrics]:
        """Update routing weight for an agent."""
        metrics = await self.get_latest_metrics(agent_name)
        if metrics:
            metrics.routing_weight = max(0.1, min(1.0, new_weight))  # Clamp between 0.1 and 1.0
            await self.session.flush()
        return metrics


class QueryTypePatternRepository(BaseRepository[QueryTypePattern]):
    """Repository for query type patterns."""

    def __init__(self, session: AsyncSession):
        super().__init__(QueryTypePattern, session)

    async def get_active_patterns(self) -> List[QueryTypePattern]:
        """Get all active patterns."""
        result = await self.session.execute(
            select(QueryTypePattern)
            .where(QueryTypePattern.is_active == True)
            .order_by(QueryTypePattern.confidence.desc())
        )
        return list(result.scalars().all())

    async def find_matching_pattern(
        self,
        query_text: str,
    ) -> Optional[QueryTypePattern]:
        """Find the best matching pattern for a query."""
        patterns = await self.get_active_patterns()
        
        query_lower = query_text.lower()
        best_match = None
        best_score = 0
        
        for pattern in patterns:
            keywords = pattern.keywords or []
            matching_keywords = sum(1 for kw in keywords if kw.lower() in query_lower)
            
            if matching_keywords > 0:
                # Score based on keyword matches and pattern confidence
                score = matching_keywords * pattern.confidence
                if score > best_score:
                    best_score = score
                    best_match = pattern
        
        return best_match

    async def update_pattern_stats(
        self,
        pattern_id: uuid.UUID,
        is_positive: bool,
    ) -> Optional[QueryTypePattern]:
        """Update pattern statistics after feedback."""
        pattern = await self.get(pattern_id)
        if pattern:
            # Incrementally update satisfaction using exponential moving average
            alpha = 0.1  # Learning rate
            new_value = 1.0 if is_positive else 0.0
            pattern.avg_satisfaction = (
                alpha * new_value + (1 - alpha) * pattern.avg_satisfaction
            )
            pattern.sample_size += 1
            
            # Update confidence based on sample size
            pattern.confidence = min(0.95, 0.5 + (pattern.sample_size / 100) * 0.45)
            
            pattern.updated_at = datetime.utcnow()
            await self.session.flush()
        
        return pattern

    async def get_by_pattern_name(self, name: str) -> Optional[QueryTypePattern]:
        """Get pattern by name."""
        result = await self.session.execute(
            select(QueryTypePattern).where(QueryTypePattern.pattern_name == name)
        )
        return result.scalar_one_or_none()