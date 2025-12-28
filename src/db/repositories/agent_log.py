"""AgentLog repository for agent execution logging operations."""

import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.agent_log import AgentLog
from src.db.repositories.base import BaseRepository


class AgentLogRepository(BaseRepository[AgentLog]):
    """Repository for AgentLog model operations."""

    def __init__(self, session: AsyncSession):
        """Initialize the agent log repository.

        Args:
            session: The async database session.
        """
        super().__init__(AgentLog, session)

    async def get_by_query_id(
        self,
        query_id: uuid.UUID,
    ) -> List[AgentLog]:
        """Get all agent logs for a query.

        Args:
            query_id: The UUID of the query.

        Returns:
            List of agent log instances.
        """
        stmt = (
            select(AgentLog)
            .where(AgentLog.query_id == query_id)
            .order_by(AgentLog.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_agent_name(
        self,
        agent_name: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AgentLog]:
        """Get agent logs by agent name.

        Args:
            agent_name: The name of the agent.
            skip: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of agent log instances.
        """
        stmt = (
            select(AgentLog)
            .where(AgentLog.agent_name == agent_name)
            .offset(skip)
            .limit(limit)
            .order_by(AgentLog.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_status(
        self,
        status: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AgentLog]:
        """Get agent logs by status.

        Args:
            status: The status to filter by.
            skip: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of agent log instances.
        """
        stmt = (
            select(AgentLog)
            .where(AgentLog.status == status)
            .offset(skip)
            .limit(limit)
            .order_by(AgentLog.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_failed_logs(
        self,
        hours: int = 24,
        limit: int = 100,
    ) -> List[AgentLog]:
        """Get failed agent logs within a time window.

        Args:
            hours: Number of hours to look back.
            limit: Maximum number of records to return.

        Returns:
            List of failed agent log instances.
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        stmt = (
            select(AgentLog)
            .where(AgentLog.status == "failed")
            .where(AgentLog.created_at >= since)
            .limit(limit)
            .order_by(AgentLog.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_recent_logs(
        self,
        hours: int = 24,
        limit: int = 100,
    ) -> List[AgentLog]:
        """Get recent agent logs within a time window.

        Args:
            hours: Number of hours to look back.
            limit: Maximum number of records to return.

        Returns:
            List of recent agent log instances.
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        stmt = (
            select(AgentLog)
            .where(AgentLog.created_at >= since)
            .limit(limit)
            .order_by(AgentLog.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_logs(
        self,
        skip: int = 0,
        limit: int = 100,
        agent_name: str | None = None,
    ) -> tuple[List[AgentLog], int]:
        """Get agent logs with optional filtering.

        Args:
            skip: Number of records to skip.
            limit: Maximum number of records to return.
            agent_name: Optional agent name to filter by.

        Returns:
            Tuple of (list of agent log instances, total count).
        """
        # Build base query
        stmt = select(AgentLog)
        count_stmt = select(func.count()).select_from(AgentLog)
        
        if agent_name:
            stmt = stmt.where(AgentLog.agent_name == agent_name)
            count_stmt = count_stmt.where(AgentLog.agent_name == agent_name)
        
        # Add pagination and ordering
        stmt = stmt.offset(skip).limit(limit).order_by(AgentLog.created_at.desc())
        
        # Execute queries
        result = await self.session.execute(stmt)
        logs = list(result.scalars().all())
        
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar_one()
        
        return logs, total

    async def create_log(
        self,
        agent_name: str,
        input_data: Dict[str, Any],
        query_id: uuid.UUID | None = None,
        model_name: str | None = None,
    ) -> AgentLog:
        """Create a new agent log entry.

        Args:
            agent_name: The name of the agent.
            input_data: The input data for the agent.
            query_id: Optional query ID.
            model_name: Optional model name.

        Returns:
            The created agent log instance.
        """
        log_data = {
            "agent_name": agent_name,
            "input_data": input_data,
            "status": "pending",
        }
        if query_id:
            log_data["query_id"] = query_id
        if model_name:
            log_data["model_name"] = model_name
            
        return await self.create(log_data)

    async def mark_completed(
        self,
        log_id: uuid.UUID,
        output_data: Dict[str, Any],
        execution_time_ms: float,
        tokens_used: int | None = None,
    ) -> AgentLog | None:
        """Mark an agent log as completed.

        Args:
            log_id: The UUID of the log.
            output_data: The output data from the agent.
            execution_time_ms: The execution time in milliseconds.
            tokens_used: Optional number of tokens used.

        Returns:
            The updated agent log or None if not found.
        """
        update_data = {
            "status": "completed",
            "output_data": output_data,
            "execution_time_ms": execution_time_ms,
            "completed_at": datetime.utcnow(),
        }
        if tokens_used is not None:
            update_data["tokens_used"] = tokens_used
            
        return await self.update(log_id, update_data)

    async def mark_failed(
        self,
        log_id: uuid.UUID,
        error_message: str,
    ) -> AgentLog | None:
        """Mark an agent log as failed.

        Args:
            log_id: The UUID of the log.
            error_message: The error message.

        Returns:
            The updated agent log or None if not found.
        """
        return await self.update(
            log_id,
            {
                "status": "failed",
                "error_message": error_message,
                "completed_at": datetime.utcnow(),
            },
        )

    async def get_agent_statistics(
        self,
        agent_name: str | None = None,
        hours: int = 24,
    ) -> Dict[str, Any]:
        """Get agent execution statistics.

        Args:
            agent_name: Optional agent name to filter by.
            hours: Number of hours to look back.

        Returns:
            Dictionary with statistics.
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        
        # Base filter
        base_filter = AgentLog.created_at >= since
        if agent_name:
            base_filter = (AgentLog.created_at >= since) & (AgentLog.agent_name == agent_name)

        # Total count
        count_stmt = select(func.count()).select_from(AgentLog).where(base_filter)
        count_result = await self.session.execute(count_stmt)
        total_count = count_result.scalar_one()

        # Success count
        success_stmt = (
            select(func.count())
            .select_from(AgentLog)
            .where(base_filter)
            .where(AgentLog.status == "completed")
        )
        success_result = await self.session.execute(success_stmt)
        success_count = success_result.scalar_one()

        # Failed count
        failed_stmt = (
            select(func.count())
            .select_from(AgentLog)
            .where(base_filter)
            .where(AgentLog.status == "failed")
        )
        failed_result = await self.session.execute(failed_stmt)
        failed_count = failed_result.scalar_one()

        # Average execution time
        avg_time_stmt = (
            select(func.avg(AgentLog.execution_time_ms))
            .where(base_filter)
            .where(AgentLog.status == "completed")
        )
        avg_time_result = await self.session.execute(avg_time_stmt)
        avg_execution_time = avg_time_result.scalar_one_or_none()

        # Total tokens used
        tokens_stmt = (
            select(func.sum(AgentLog.tokens_used))
            .where(base_filter)
            .where(AgentLog.tokens_used.is_not(None))
        )
        tokens_result = await self.session.execute(tokens_stmt)
        total_tokens = tokens_result.scalar_one_or_none() or 0

        return {
            "total_executions": total_count,
            "successful_executions": success_count,
            "failed_executions": failed_count,
            "success_rate": success_count / total_count if total_count > 0 else 0,
            "average_execution_time_ms": avg_execution_time,
            "total_tokens_used": total_tokens,
            "time_window_hours": hours,
        }

    async def get_agent_performance_by_name(
        self,
        hours: int = 24,
    ) -> List[Dict[str, Any]]:
        """Get performance statistics grouped by agent name.

        Args:
            hours: Number of hours to look back.

        Returns:
            List of dictionaries with per-agent statistics.
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        
        stmt = (
            select(
                AgentLog.agent_name,
                func.count().label("total"),
                func.sum(
                    func.cast(AgentLog.status == "completed", type_=int)
                ).label("successful"),
                func.avg(AgentLog.execution_time_ms).label("avg_time"),
                func.sum(AgentLog.tokens_used).label("total_tokens"),
            )
            .where(AgentLog.created_at >= since)
            .group_by(AgentLog.agent_name)
        )
        
        result = await self.session.execute(stmt)
        rows = result.fetchall()
        
        return [
            {
                "agent_name": row.agent_name,
                "total_executions": row.total,
                "successful_executions": row.successful or 0,
                "success_rate": (row.successful or 0) / row.total if row.total > 0 else 0,
                "average_execution_time_ms": row.avg_time,
                "total_tokens_used": row.total_tokens or 0,
            }
            for row in rows
        ]