"""Query repository for query-specific database operations."""

import uuid
from datetime import datetime, timedelta
from typing import List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models.query import Query, QueryChunk
from src.db.repositories.base import BaseRepository


class QueryRepository(BaseRepository[Query]):
    """Repository for Query model operations."""

    def __init__(self, session: AsyncSession):
        """Initialize the query repository.

        Args:
            session: The async database session.
        """
        super().__init__(Query, session)

    async def get_by_user_id(
        self,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Query]:
        """Get all queries for a user.

        Args:
            user_id: The UUID of the user.
            skip: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of query instances.
        """
        stmt = (
            select(Query)
            .where(Query.user_id == user_id)
            .offset(skip)
            .limit(limit)
            .order_by(Query.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_with_chunks(self, query_id: uuid.UUID) -> Query | None:
        """Get a query with its related chunks eagerly loaded.

        Args:
            query_id: The UUID of the query.

        Returns:
            The query instance with chunks or None if not found.
        """
        stmt = (
            select(Query)
            .where(Query.id == query_id)
            .options(selectinload(Query.query_chunks))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_agent(
        self,
        agent_name: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Query]:
        """Get queries by agent name.

        Args:
            agent_name: The name of the agent.
            skip: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of query instances.
        """
        stmt = (
            select(Query)
            .where(Query.agent_used == agent_name)
            .offset(skip)
            .limit(limit)
            .order_by(Query.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_recent_queries(
        self,
        user_id: uuid.UUID,
        hours: int = 24,
        limit: int = 50,
    ) -> List[Query]:
        """Get recent queries for a user within a time window.

        Args:
            user_id: The UUID of the user.
            hours: Number of hours to look back.
            limit: Maximum number of records to return.

        Returns:
            List of recent query instances.
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        stmt = (
            select(Query)
            .where(Query.user_id == user_id)
            .where(Query.created_at >= since)
            .limit(limit)
            .order_by(Query.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_average_response_time(
        self,
        user_id: uuid.UUID | None = None,
        agent_name: str | None = None,
    ) -> float | None:
        """Get average response time for queries.

        Args:
            user_id: Optional user ID to filter by.
            agent_name: Optional agent name to filter by.

        Returns:
            Average response time in milliseconds or None.
        """
        stmt = select(func.avg(Query.response_time_ms))
        
        if user_id:
            stmt = stmt.where(Query.user_id == user_id)
        if agent_name:
            stmt = stmt.where(Query.agent_used == agent_name)
        
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_by_user(self, user_id: uuid.UUID) -> int:
        """Count queries for a specific user.

        Args:
            user_id: The UUID of the user.

        Returns:
            Number of queries.
        """
        stmt = (
            select(func.count())
            .select_from(Query)
            .where(Query.user_id == user_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def count_by_agent(self, agent_name: str) -> int:
        """Count queries for a specific agent.

        Args:
            agent_name: The name of the agent.

        Returns:
            Number of queries.
        """
        stmt = (
            select(func.count())
            .select_from(Query)
            .where(Query.agent_used == agent_name)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def add_query_chunk(
        self,
        query_id: uuid.UUID,
        chunk_id: uuid.UUID,
        similarity_score: float,
    ) -> QueryChunk:
        """Add a chunk reference to a query.

        Args:
            query_id: The UUID of the query.
            chunk_id: The UUID of the chunk.
            similarity_score: The similarity score.

        Returns:
            The created QueryChunk instance.
        """
        query_chunk = QueryChunk(
            query_id=query_id,
            chunk_id=chunk_id,
            similarity_score=similarity_score,
        )
        self.session.add(query_chunk)
        await self.session.flush()
        await self.session.refresh(query_chunk)
        return query_chunk

    async def add_query_chunks(
        self,
        query_id: uuid.UUID,
        chunks: List[tuple[uuid.UUID, float]],
    ) -> List[QueryChunk]:
        """Add multiple chunk references to a query.

        Args:
            query_id: The UUID of the query.
            chunks: List of (chunk_id, similarity_score) tuples.

        Returns:
            List of created QueryChunk instances.
        """
        query_chunks = [
            QueryChunk(
                query_id=query_id,
                chunk_id=chunk_id,
                similarity_score=score,
            )
            for chunk_id, score in chunks
        ]
        self.session.add_all(query_chunks)
        await self.session.flush()
        for qc in query_chunks:
            await self.session.refresh(qc)
        return query_chunks

    async def get_query_statistics(
        self,
        user_id: uuid.UUID | None = None,
    ) -> dict:
        """Get query statistics.

        Args:
            user_id: Optional user ID to filter by.

        Returns:
            Dictionary with statistics.
        """
        base_stmt = select(Query)
        if user_id:
            base_stmt = base_stmt.where(Query.user_id == user_id)

        # Total count
        count_stmt = select(func.count()).select_from(Query)
        if user_id:
            count_stmt = count_stmt.where(Query.user_id == user_id)
        count_result = await self.session.execute(count_stmt)
        total_count = count_result.scalar_one()

        # Average response time
        avg_stmt = select(func.avg(Query.response_time_ms))
        if user_id:
            avg_stmt = avg_stmt.where(Query.user_id == user_id)
        avg_result = await self.session.execute(avg_stmt)
        avg_response_time = avg_result.scalar_one_or_none()

        # Agent distribution
        agent_stmt = (
            select(Query.agent_used, func.count())
            .group_by(Query.agent_used)
        )
        if user_id:
            agent_stmt = agent_stmt.where(Query.user_id == user_id)
        agent_result = await self.session.execute(agent_stmt)
        agent_distribution = dict(agent_result.fetchall())

        return {
            "total_queries": total_count,
            "average_response_time_ms": avg_response_time,
            "agent_distribution": agent_distribution,
        }