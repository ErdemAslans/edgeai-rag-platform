"""Advanced Analytics Service for tracking usage, costs, and query patterns.

This service provides:
1. Query pattern analysis
2. Usage tracking by user/team
3. Cost estimation and tracking
4. Performance metrics
5. Popular document sections
6. Trend analysis
"""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import uuid

from sqlalchemy import select, func, and_, or_, desc, text
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.db.models.query import Query
from src.db.models.document import Document
from src.db.models.chunk import Chunk
from src.db.models.agent_log import AgentLog
from src.db.models.user import User
from src.db.models.feedback import QueryFeedback
from src.core.logging import get_logger

logger = get_logger(__name__)


class AnalyticsService:
    """Service for advanced analytics and usage tracking."""

    # Cost estimation per 1K tokens (approximate)
    COST_PER_1K_TOKENS = {
        "gpt-4": 0.03,
        "gpt-4-turbo": 0.01,
        "gpt-3.5-turbo": 0.002,
        "claude-3-opus": 0.015,
        "claude-3-sonnet": 0.003,
        "gemini-pro": 0.00025,
        "embedding": 0.0001,
    }

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_usage_summary(
        self,
        user_id: Optional[uuid.UUID] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get usage summary for a user or system-wide.
        
        Args:
            user_id: Optional user ID for user-specific stats
            days: Number of days to analyze
            
        Returns:
            Usage summary dictionary
        """
        since = datetime.utcnow() - timedelta(days=days)
        
        # Build base query
        query_filter = Query.created_at >= since
        if user_id:
            query_filter = and_(query_filter, Query.user_id == user_id)
        
        # Total queries
        total_result = await self.session.execute(
            select(func.count(Query.id)).where(query_filter)
        )
        total_queries = total_result.scalar() or 0
        
        # Queries by day
        daily_result = await self.session.execute(
            select(
                func.date(Query.created_at).label("date"),
                func.count(Query.id).label("count")
            )
            .where(query_filter)
            .group_by(func.date(Query.created_at))
            .order_by(func.date(Query.created_at))
        )
        daily_queries = [
            {"date": str(row.date), "count": row.count}
            for row in daily_result.all()
        ]
        
        # Average response time
        avg_time_result = await self.session.execute(
            select(func.avg(Query.processing_time_ms)).where(query_filter)
        )
        avg_response_time = avg_time_result.scalar() or 0
        
        # Token usage
        token_result = await self.session.execute(
            select(
                func.sum(Query.token_count).label("total_tokens"),
                func.avg(Query.token_count).label("avg_tokens")
            ).where(query_filter)
        )
        token_row = token_result.one()
        total_tokens = token_row.total_tokens or 0
        avg_tokens = token_row.avg_tokens or 0
        
        # Queries by agent type
        agent_result = await self.session.execute(
            select(
                AgentLog.agent_type,
                func.count(AgentLog.id).label("count")
            )
            .where(AgentLog.created_at >= since)
            .group_by(AgentLog.agent_type)
            .order_by(desc("count"))
        )
        queries_by_agent = [
            {"agent": row.agent_type, "count": row.count}
            for row in agent_result.all()
        ]
        
        return {
            "period_days": days,
            "total_queries": total_queries,
            "daily_queries": daily_queries,
            "avg_response_time_ms": float(avg_response_time),
            "total_tokens": int(total_tokens),
            "avg_tokens_per_query": float(avg_tokens),
            "queries_by_agent": queries_by_agent,
            "estimated_cost": self._estimate_cost(int(total_tokens)),
        }

    async def get_query_patterns(
        self,
        user_id: Optional[uuid.UUID] = None,
        days: int = 30,
        top_n: int = 20,
    ) -> Dict[str, Any]:
        """Analyze query patterns to identify common themes.
        
        Args:
            user_id: Optional user ID
            days: Analysis period
            top_n: Number of top patterns to return
            
        Returns:
            Query pattern analysis
        """
        since = datetime.utcnow() - timedelta(days=days)
        
        query_filter = Query.created_at >= since
        if user_id:
            query_filter = and_(query_filter, Query.user_id == user_id)
        
        # Get all queries
        result = await self.session.execute(
            select(Query.query_text, Query.metadata)
            .where(query_filter)
            .order_by(Query.created_at.desc())
            .limit(1000)  # Limit for performance
        )
        queries = result.all()
        
        # Extract keywords and patterns
        keyword_counts: Dict[str, int] = defaultdict(int)
        query_types: Dict[str, int] = defaultdict(int)
        
        for query_text, metadata in queries:
            # Simple keyword extraction
            words = query_text.lower().split()
            for word in words:
                if len(word) > 3:  # Skip short words
                    keyword_counts[word] += 1
            
            # Query type classification (from metadata if available)
            if metadata and "query_type" in metadata:
                query_types[metadata["query_type"]] += 1
            else:
                # Simple classification based on keywords
                query_type = self._classify_query(query_text)
                query_types[query_type] += 1
        
        # Top keywords
        top_keywords = sorted(
            keyword_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_n]
        
        # Query type distribution
        type_distribution = dict(query_types)
        
        # Time-based patterns
        time_patterns = await self._analyze_time_patterns(since, user_id)
        
        return {
            "period_days": days,
            "total_queries_analyzed": len(queries),
            "top_keywords": [
                {"keyword": k, "count": c} for k, c in top_keywords
            ],
            "query_type_distribution": type_distribution,
            "time_patterns": time_patterns,
        }

    async def get_document_analytics(
        self,
        user_id: Optional[uuid.UUID] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get document usage analytics.
        
        Args:
            user_id: Optional user ID
            days: Analysis period
            
        Returns:
            Document analytics
        """
        since = datetime.utcnow() - timedelta(days=days)
        
        # Filter conditions
        doc_filter = Document.created_at >= since
        if user_id:
            doc_filter = and_(doc_filter, Document.user_id == user_id)
        
        # Total documents
        total_result = await self.session.execute(
            select(func.count(Document.id)).where(doc_filter)
        )
        total_docs = total_result.scalar() or 0
        
        # Documents by status
        status_result = await self.session.execute(
            select(
                Document.status,
                func.count(Document.id).label("count")
            )
            .where(doc_filter)
            .group_by(Document.status)
        )
        docs_by_status = {row.status: row.count for row in status_result.all()}
        
        # Documents by type (from file extension)
        type_result = await self.session.execute(
            select(
                Document.file_type,
                func.count(Document.id).label("count")
            )
            .where(doc_filter)
            .group_by(Document.file_type)
            .order_by(desc("count"))
        )
        docs_by_type = [
            {"type": row.file_type or "unknown", "count": row.count}
            for row in type_result.all()
        ]
        
        # Total chunks
        chunk_count_result = await self.session.execute(
            select(func.count(Chunk.id))
            .join(Document, Chunk.document_id == Document.id)
            .where(doc_filter)
        )
        total_chunks = chunk_count_result.scalar() or 0
        
        # Average chunks per document
        avg_chunks = total_chunks / total_docs if total_docs > 0 else 0
        
        # Most accessed documents (by chunk retrieval in queries)
        # This would require tracking chunk access - simplified version
        
        return {
            "period_days": days,
            "total_documents": total_docs,
            "documents_by_status": docs_by_status,
            "documents_by_type": docs_by_type,
            "total_chunks": total_chunks,
            "avg_chunks_per_document": avg_chunks,
        }

    async def get_cost_tracking(
        self,
        user_id: Optional[uuid.UUID] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get cost tracking and estimation.
        
        Args:
            user_id: Optional user ID
            days: Analysis period
            
        Returns:
            Cost tracking data
        """
        since = datetime.utcnow() - timedelta(days=days)
        
        query_filter = Query.created_at >= since
        if user_id:
            query_filter = and_(query_filter, Query.user_id == user_id)
        
        # Daily token usage
        daily_result = await self.session.execute(
            select(
                func.date(Query.created_at).label("date"),
                func.sum(Query.token_count).label("tokens")
            )
            .where(query_filter)
            .group_by(func.date(Query.created_at))
            .order_by(func.date(Query.created_at))
        )
        daily_tokens = [
            {"date": str(row.date), "tokens": int(row.tokens or 0)}
            for row in daily_result.all()
        ]
        
        # Calculate daily costs
        daily_costs = [
            {"date": d["date"], "cost": self._estimate_cost(d["tokens"])}
            for d in daily_tokens
        ]
        
        # Total cost
        total_tokens = sum(d["tokens"] for d in daily_tokens)
        total_cost = self._estimate_cost(total_tokens)
        
        # Cost by agent/model
        agent_cost_result = await self.session.execute(
            select(
                AgentLog.agent_type,
                func.sum(AgentLog.token_count).label("tokens")
            )
            .where(AgentLog.created_at >= since)
            .group_by(AgentLog.agent_type)
        )
        cost_by_agent = [
            {
                "agent": row.agent_type,
                "tokens": int(row.tokens or 0),
                "cost": self._estimate_cost(int(row.tokens or 0))
            }
            for row in agent_cost_result.all()
        ]
        
        # Projected monthly cost
        if len(daily_costs) > 0:
            avg_daily_cost = total_cost / len(daily_costs)
            projected_monthly = avg_daily_cost * 30
        else:
            projected_monthly = 0
        
        return {
            "period_days": days,
            "total_tokens": total_tokens,
            "total_cost": total_cost,
            "daily_costs": daily_costs,
            "cost_by_agent": cost_by_agent,
            "projected_monthly_cost": projected_monthly,
            "cost_breakdown": {
                "llm_inference": total_cost * 0.85,  # Estimated split
                "embeddings": total_cost * 0.10,
                "other": total_cost * 0.05,
            },
        }

    async def get_performance_metrics(
        self,
        user_id: Optional[uuid.UUID] = None,
        days: int = 7,
    ) -> Dict[str, Any]:
        """Get performance metrics.
        
        Args:
            user_id: Optional user ID
            days: Analysis period
            
        Returns:
            Performance metrics
        """
        since = datetime.utcnow() - timedelta(days=days)
        
        query_filter = Query.created_at >= since
        if user_id:
            query_filter = and_(query_filter, Query.user_id == user_id)
        
        # Response time percentiles
        time_result = await self.session.execute(
            select(Query.processing_time_ms)
            .where(query_filter)
            .order_by(Query.processing_time_ms)
        )
        response_times = [row[0] for row in time_result.all() if row[0] is not None]
        
        percentiles = {}
        if response_times:
            import statistics
            percentiles = {
                "p50": statistics.median(response_times),
                "p90": self._percentile(response_times, 90),
                "p99": self._percentile(response_times, 99),
                "min": min(response_times),
                "max": max(response_times),
                "avg": statistics.mean(response_times),
            }
        
        # Error rate
        total_queries = len(response_times)
        error_result = await self.session.execute(
            select(func.count(Query.id))
            .where(and_(query_filter, Query.status == "error"))
        )
        error_count = error_result.scalar() or 0
        error_rate = error_count / total_queries if total_queries > 0 else 0
        
        # Cache hit rate (from agent logs)
        cache_result = await self.session.execute(
            select(
                func.sum(
                    func.cast(
                        AgentLog.metadata["cache_hit"].astext == "true",
                        sa.Integer
                    )
                ).label("hits"),
                func.count(AgentLog.id).label("total")
            )
            .where(AgentLog.created_at >= since)
        )
        cache_row = cache_result.one()
        cache_hit_rate = (cache_row.hits or 0) / (cache_row.total or 1)
        
        # Satisfaction rate (from feedback)
        feedback_result = await self.session.execute(
            select(
                func.sum(func.cast(QueryFeedback.is_positive, sa.Integer)).label("positive"),
                func.count(QueryFeedback.id).label("total")
            )
            .where(QueryFeedback.created_at >= since)
        )
        feedback_row = feedback_result.one()
        satisfaction_rate = (
            (feedback_row.positive or 0) / (feedback_row.total or 1)
            if feedback_row.total else 0.5
        )
        
        return {
            "period_days": days,
            "total_queries": total_queries,
            "response_time_percentiles": percentiles,
            "error_rate": error_rate,
            "cache_hit_rate": cache_hit_rate,
            "satisfaction_rate": satisfaction_rate,
            "availability": 1 - error_rate,  # Simplified availability
        }

    async def get_trending_topics(
        self,
        days: int = 7,
        top_n: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get trending topics from recent queries.
        
        Args:
            days: Analysis period
            top_n: Number of topics to return
            
        Returns:
            List of trending topics with metrics
        """
        since = datetime.utcnow() - timedelta(days=days)
        prev_since = since - timedelta(days=days)
        
        # Current period keywords
        current_result = await self.session.execute(
            select(Query.query_text)
            .where(Query.created_at >= since)
            .limit(500)
        )
        current_queries = [row[0] for row in current_result.all()]
        
        # Previous period keywords
        prev_result = await self.session.execute(
            select(Query.query_text)
            .where(and_(Query.created_at >= prev_since, Query.created_at < since))
            .limit(500)
        )
        prev_queries = [row[0] for row in prev_result.all()]
        
        # Extract and compare keywords
        current_keywords = self._extract_keywords(current_queries)
        prev_keywords = self._extract_keywords(prev_queries)
        
        # Calculate trend scores
        trending = []
        for keyword, count in current_keywords.items():
            prev_count = prev_keywords.get(keyword, 0)
            if prev_count > 0:
                growth = (count - prev_count) / prev_count
            else:
                growth = 1.0 if count > 0 else 0
            
            trending.append({
                "topic": keyword,
                "current_count": count,
                "previous_count": prev_count,
                "growth_rate": growth,
                "trend": "up" if growth > 0.1 else ("down" if growth < -0.1 else "stable"),
            })
        
        # Sort by growth rate
        trending.sort(key=lambda x: x["growth_rate"], reverse=True)
        
        return trending[:top_n]

    def _estimate_cost(self, tokens: int, model: str = "gpt-3.5-turbo") -> float:
        """Estimate cost based on token count."""
        rate = self.COST_PER_1K_TOKENS.get(model, 0.002)
        return (tokens / 1000) * rate

    def _classify_query(self, query: str) -> str:
        """Simple query classification based on keywords."""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ["how", "what", "why", "explain"]):
            return "question"
        elif any(word in query_lower for word in ["summarize", "summary", "brief"]):
            return "summarization"
        elif any(word in query_lower for word in ["code", "function", "implement"]):
            return "coding"
        elif any(word in query_lower for word in ["compare", "difference", "vs"]):
            return "comparison"
        elif any(word in query_lower for word in ["find", "search", "locate"]):
            return "search"
        else:
            return "general"

    async def _analyze_time_patterns(
        self,
        since: datetime,
        user_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """Analyze time-based query patterns."""
        query_filter = Query.created_at >= since
        if user_id:
            query_filter = and_(query_filter, Query.user_id == user_id)
        
        # Queries by hour of day
        hour_result = await self.session.execute(
            select(
                func.extract("hour", Query.created_at).label("hour"),
                func.count(Query.id).label("count")
            )
            .where(query_filter)
            .group_by(func.extract("hour", Query.created_at))
            .order_by("hour")
        )
        by_hour = {int(row.hour): row.count for row in hour_result.all()}
        
        # Queries by day of week
        dow_result = await self.session.execute(
            select(
                func.extract("dow", Query.created_at).label("dow"),
                func.count(Query.id).label("count")
            )
            .where(query_filter)
            .group_by(func.extract("dow", Query.created_at))
            .order_by("dow")
        )
        days_map = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        by_day = {days_map[int(row.dow)]: row.count for row in dow_result.all()}
        
        # Peak hour
        peak_hour = max(by_hour.items(), key=lambda x: x[1])[0] if by_hour else 0
        
        return {
            "by_hour": by_hour,
            "by_day_of_week": by_day,
            "peak_hour": peak_hour,
            "peak_day": max(by_day.items(), key=lambda x: x[1])[0] if by_day else "Monday",
        }

    def _extract_keywords(self, queries: List[str]) -> Dict[str, int]:
        """Extract keywords from queries."""
        keywords: Dict[str, int] = defaultdict(int)
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "what", "how", "why", "when", "where", "who"}
        
        for query in queries:
            words = query.lower().split()
            for word in words:
                # Clean word
                word = ''.join(c for c in word if c.isalnum())
                if len(word) > 3 and word not in stop_words:
                    keywords[word] += 1
        
        return dict(keywords)

    @staticmethod
    def _percentile(data: List[float], percentile: int) -> float:
        """Calculate percentile of a list."""
        if not data:
            return 0
        k = (len(data) - 1) * percentile / 100
        f = int(k)
        c = f + 1 if f + 1 < len(data) else f
        return data[f] + (k - f) * (data[c] - data[f])


# Import for type hint
import sqlalchemy as sa


# Factory function
def get_analytics_service(session: AsyncSession) -> AnalyticsService:
    """Get analytics service instance."""
    return AnalyticsService(session)