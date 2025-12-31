"""Adaptive Learning Service for intelligent agent optimization.

This service analyzes user feedback to:
1. Track agent performance metrics
2. Optimize routing weights
3. Learn query patterns
4. Suggest prompt improvements
"""

import asyncio
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.feedback import (
    QueryFeedback,
    AgentPerformanceMetrics,
    QueryTypePattern,
)
from src.db.repositories.feedback import (
    QueryFeedbackRepository,
    AgentPerformanceRepository,
    QueryTypePatternRepository,
)
from src.core.logging import get_logger

logger = get_logger(__name__)


class AdaptiveLearningService:
    """Service for adaptive learning based on user feedback."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.feedback_repo = QueryFeedbackRepository(session)
        self.performance_repo = AgentPerformanceRepository(session)
        self.pattern_repo = QueryTypePatternRepository(session)
        
        # Learning parameters
        self.min_samples_for_adjustment = 10
        self.weight_learning_rate = 0.1
        self.pattern_confidence_threshold = 0.6
        self.metrics_aggregation_hours = 24

    async def record_feedback(
        self,
        query_id: str,
        user_id: str,
        is_positive: bool,
        agent_used: str,
        framework_used: Optional[str] = None,
        response_time_ms: Optional[float] = None,
        query_text: Optional[str] = None,
    ) -> None:
        """Record feedback and trigger learning updates."""
        # Update agent performance metrics
        await self._update_agent_metrics(
            agent_used=agent_used,
            framework_used=framework_used,
            is_positive=is_positive,
            response_time_ms=response_time_ms,
        )
        
        # Update routing weights if enough data
        await self._maybe_update_routing_weights(agent_used)
        
        # Update query patterns if query text provided
        if query_text:
            await self._update_query_patterns(
                query_text=query_text,
                agent_used=agent_used,
                is_positive=is_positive,
            )

    async def _update_agent_metrics(
        self,
        agent_used: str,
        framework_used: Optional[str],
        is_positive: bool,
        response_time_ms: Optional[float],
    ) -> None:
        """Update or create performance metrics for an agent."""
        now = datetime.utcnow()
        period_start = now - timedelta(hours=self.metrics_aggregation_hours)
        
        # Get or create metrics for current period
        metrics = await self.performance_repo.get_latest_metrics(
            agent_used, framework_used
        )
        
        if metrics and metrics.period_end >= period_start:
            # Update existing metrics
            metrics.total_queries += 1
            if is_positive:
                metrics.positive_feedbacks += 1
            else:
                metrics.negative_feedbacks += 1
            
            # Update average response time
            if response_time_ms is not None:
                if metrics.avg_response_time_ms is not None:
                    # Incremental average
                    n = metrics.total_queries
                    metrics.avg_response_time_ms = (
                        (metrics.avg_response_time_ms * (n - 1) + response_time_ms) / n
                    )
                else:
                    metrics.avg_response_time_ms = response_time_ms
            
            metrics.period_end = now
        else:
            # Create new metrics period
            new_metrics = AgentPerformanceMetrics(
                agent_name=agent_used,
                framework=framework_used,
                period_start=period_start,
                period_end=now,
                total_queries=1,
                positive_feedbacks=1 if is_positive else 0,
                negative_feedbacks=0 if is_positive else 1,
                avg_response_time_ms=response_time_ms,
                routing_weight=1.0,
                category_breakdown={},
            )
            await self.performance_repo.create(new_metrics)
        
        await self.session.flush()

    async def _maybe_update_routing_weights(self, agent_name: str) -> None:
        """Update routing weights if enough samples collected."""
        stats = await self.feedback_repo.get_agent_stats(agent_name)
        
        if stats["total_feedback"] < self.min_samples_for_adjustment:
            return
        
        # Calculate new weight based on satisfaction rate
        satisfaction = stats["satisfaction_rate"]
        
        # Get current metrics
        metrics = await self.performance_repo.get_latest_metrics(agent_name)
        if not metrics:
            return
        
        current_weight = metrics.routing_weight
        
        # Adjust weight towards satisfaction rate
        # If satisfaction is high (>0.8), increase weight
        # If satisfaction is low (<0.5), decrease weight
        target_weight = 0.5 + (satisfaction * 0.5)  # Maps 0-1 to 0.5-1.0
        
        new_weight = current_weight + self.weight_learning_rate * (
            target_weight - current_weight
        )
        
        # Clamp to valid range
        new_weight = max(0.1, min(1.0, new_weight))
        
        await self.performance_repo.update_routing_weight(agent_name, new_weight)
        
        logger.info(
            f"Updated routing weight for {agent_name}: "
            f"{current_weight:.3f} -> {new_weight:.3f} "
            f"(satisfaction: {satisfaction:.2%})"
        )

    async def _update_query_patterns(
        self,
        query_text: str,
        agent_used: str,
        is_positive: bool,
    ) -> None:
        """Update query pattern learning based on feedback."""
        # Find matching pattern
        pattern = await self.pattern_repo.find_matching_pattern(query_text)
        
        if pattern:
            # Update existing pattern stats
            await self.pattern_repo.update_pattern_stats(pattern.id, is_positive)
            
            # If this agent performed better than current best, consider switching
            if is_positive and pattern.best_agent != agent_used:
                # Get stats for both agents on this pattern type
                current_best_stats = await self.feedback_repo.get_agent_stats(
                    pattern.best_agent
                )
                new_agent_stats = await self.feedback_repo.get_agent_stats(agent_used)
                
                # Only switch if new agent has significantly better satisfaction
                if (
                    new_agent_stats["total_feedback"] >= self.min_samples_for_adjustment
                    and new_agent_stats["satisfaction_rate"]
                    > current_best_stats["satisfaction_rate"] + 0.1
                ):
                    pattern.best_agent = agent_used
                    logger.info(
                        f"Pattern '{pattern.pattern_name}' best agent changed to {agent_used}"
                    )

    async def get_recommended_agent(
        self,
        query_text: str,
        available_agents: List[str],
    ) -> Tuple[str, float]:
        """Get recommended agent for a query based on learned patterns.
        
        Returns:
            Tuple of (agent_name, confidence)
        """
        # First, try to match a pattern
        pattern = await self.pattern_repo.find_matching_pattern(query_text)
        
        if pattern and pattern.best_agent in available_agents:
            if pattern.confidence >= self.pattern_confidence_threshold:
                return pattern.best_agent, pattern.confidence
        
        # Fall back to routing weights
        weights = await self.performance_repo.get_routing_weights()
        
        # Filter to available agents and get best
        available_weights = {
            agent: weights.get(agent, 1.0)
            for agent in available_agents
        }
        
        if not available_weights:
            # Return first available agent with default confidence
            return available_agents[0], 0.5
        
        best_agent = max(available_weights, key=available_weights.get)
        return best_agent, available_weights[best_agent]

    async def get_agent_insights(
        self,
        agent_name: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get detailed insights for an agent's performance."""
        since = datetime.utcnow() - timedelta(days=days)
        stats = await self.feedback_repo.get_agent_stats(agent_name, since)
        
        # Get performance trends (compare with previous period)
        prev_since = since - timedelta(days=days)
        prev_stats = await self.feedback_repo.get_agent_stats(agent_name, prev_since)
        
        # Calculate trend
        if (
            prev_stats["total_feedback"] > 0
            and stats["total_feedback"] > 0
        ):
            trend = stats["satisfaction_rate"] - prev_stats["satisfaction_rate"]
            if trend > 0.05:
                trend_label = "improving"
            elif trend < -0.05:
                trend_label = "declining"
            else:
                trend_label = "stable"
        else:
            trend_label = "insufficient_data"
        
        # Get common issues from category breakdown
        issues = []
        for category, count in stats["category_breakdown"].items():
            if count >= 3:  # At least 3 occurrences
                issues.append({
                    "category": category,
                    "count": count,
                    "percentage": count / stats["negative_feedback"] if stats["negative_feedback"] > 0 else 0,
                })
        
        # Sort issues by count
        issues.sort(key=lambda x: x["count"], reverse=True)
        
        # Get routing weight
        metrics = await self.performance_repo.get_latest_metrics(agent_name)
        routing_weight = metrics.routing_weight if metrics else 1.0
        
        return {
            "agent_name": agent_name,
            "current_stats": stats,
            "trend": trend_label,
            "common_issues": issues[:5],  # Top 5 issues
            "routing_weight": routing_weight,
            "recommendations": await self._generate_recommendations(
                agent_name, stats, issues
            ),
        }

    async def _generate_recommendations(
        self,
        agent_name: str,
        stats: Dict[str, Any],
        issues: List[Dict[str, Any]],
    ) -> List[str]:
        """Generate recommendations for improving agent performance."""
        recommendations = []
        
        satisfaction = stats["satisfaction_rate"]
        
        if satisfaction < 0.5:
            recommendations.append(
                f"Critical: {agent_name} has low satisfaction ({satisfaction:.1%}). "
                "Review and optimize prompts immediately."
            )
        elif satisfaction < 0.7:
            recommendations.append(
                f"Attention: {agent_name} satisfaction ({satisfaction:.1%}) "
                "is below target. Consider prompt refinement."
            )
        
        # Issue-specific recommendations
        for issue in issues[:3]:
            category = issue["category"]
            if category == "irrelevant":
                recommendations.append(
                    "Users report irrelevant responses. "
                    "Improve context understanding and relevance filtering."
                )
            elif category == "incomplete":
                recommendations.append(
                    "Responses are reported as incomplete. "
                    "Increase response detail or add follow-up prompts."
                )
            elif category == "incorrect":
                recommendations.append(
                    "Factual accuracy issues detected. "
                    "Add fact-checking steps or improve source validation."
                )
            elif category == "too_long":
                recommendations.append(
                    "Responses are too verbose. "
                    "Add summarization or adjust response length parameters."
                )
            elif category == "slow":
                recommendations.append(
                    "Response time issues. "
                    "Consider caching, parallel processing, or model optimization."
                )
        
        if not recommendations:
            recommendations.append(
                f"{agent_name} is performing well. Continue monitoring."
            )
        
        return recommendations

    async def aggregate_daily_metrics(self) -> None:
        """Aggregate metrics for the past day. Run as scheduled task."""
        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)
        
        # Get unique agents from feedback
        result = await self.session.execute(
            select(QueryFeedback.agent_used.distinct()).where(
                QueryFeedback.created_at >= yesterday
            )
        )
        agents = [row[0] for row in result.all()]
        
        for agent_name in agents:
            stats = await self.feedback_repo.get_agent_stats(agent_name, yesterday)
            
            # Create daily metrics record
            metrics = AgentPerformanceMetrics(
                agent_name=agent_name,
                period_start=yesterday,
                period_end=now,
                total_queries=stats["total_feedback"],
                positive_feedbacks=stats["positive_feedback"],
                negative_feedbacks=stats["negative_feedback"],
                avg_rating=stats["avg_rating"],
                category_breakdown=stats["category_breakdown"],
                routing_weight=1.0,  # Will be calculated
            )
            
            # Calculate routing weight based on satisfaction
            satisfaction = stats["satisfaction_rate"]
            metrics.routing_weight = 0.5 + (satisfaction * 0.5)
            
            await self.performance_repo.create(metrics)
        
        await self.session.commit()
        logger.info(f"Aggregated daily metrics for {len(agents)} agents")

    async def learn_new_patterns(
        self,
        min_samples: int = 20,
    ) -> List[QueryTypePattern]:
        """Analyze feedback to discover new query patterns."""
        # This is a placeholder for more sophisticated pattern learning
        # In production, you might use clustering or topic modeling
        
        new_patterns = []
        
        # Get high-performing agent-query combinations
        result = await self.session.execute(
            select(
                QueryFeedback.agent_used,
                func.count(QueryFeedback.id).label("count"),
                func.avg(
                    func.cast(QueryFeedback.is_positive, sa.Integer)
                ).label("satisfaction"),
            )
            .where(QueryFeedback.is_positive == True)
            .group_by(QueryFeedback.agent_used)
            .having(func.count(QueryFeedback.id) >= min_samples)
        )
        
        for row in result.all():
            agent_name, count, satisfaction = row
            
            # Check if pattern already exists for this agent
            existing = await self.pattern_repo.get_by_pattern_name(
                f"auto_{agent_name}"
            )
            
            if not existing and satisfaction >= 0.7:
                # Create new pattern
                pattern = QueryTypePattern(
                    pattern_name=f"auto_{agent_name}",
                    pattern_description=f"Auto-discovered pattern for {agent_name}",
                    keywords=[],  # Would be populated by topic modeling
                    best_agent=agent_name,
                    sample_size=count,
                    confidence=min(0.9, 0.5 + (count / 100) * 0.4),
                    avg_satisfaction=satisfaction,
                )
                await self.pattern_repo.create(pattern)
                new_patterns.append(pattern)
        
        if new_patterns:
            await self.session.commit()
            logger.info(f"Discovered {len(new_patterns)} new query patterns")
        
        return new_patterns


# Import for type hint in aggregate_daily_metrics
import sqlalchemy as sa


# Singleton instance for easy access
_learning_service: Optional[AdaptiveLearningService] = None
_learning_lock = asyncio.Lock()


async def get_adaptive_learning_service(
    session: AsyncSession,
) -> AdaptiveLearningService:
    """Get or create the adaptive learning service instance."""
    global _learning_service
    
    # Always create new instance with the provided session
    return AdaptiveLearningService(session)