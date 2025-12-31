"""Dashboard endpoints for statistics and activity."""

import uuid
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db, get_current_user
from src.db.models.user import User
from src.db.models.document import Document
from src.db.models.query import Query
from src.db.models.agent_log import AgentLog

router = APIRouter()


class DashboardStats(BaseModel):
    total_documents: int
    queries_today: int
    active_agents: int
    avg_response_time: float


class RecentActivity(BaseModel):
    id: str
    type: str
    description: str
    timestamp: datetime


class DashboardResponse(BaseModel):
    stats: DashboardStats
    recent_activity: List[RecentActivity]


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DashboardStats:
    """Get dashboard statistics for the current user."""
    user_id = current_user.id
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    doc_count_stmt = (
        select(func.count())
        .select_from(Document)
        .where(Document.user_id == user_id)
    )
    doc_result = await db.execute(doc_count_stmt)
    total_documents = doc_result.scalar_one()
    
    queries_today_stmt = (
        select(func.count())
        .select_from(Query)
        .where(Query.user_id == user_id)
        .where(Query.created_at >= today_start)
    )
    queries_result = await db.execute(queries_today_stmt)
    queries_today = queries_result.scalar_one()
    
    active_agents = 4
    
    avg_stmt = (
        select(func.avg(Query.response_time_ms))
        .where(Query.user_id == user_id)
    )
    avg_result = await db.execute(avg_stmt)
    avg_response_time_ms = avg_result.scalar_one_or_none() or 0
    avg_response_time = round(avg_response_time_ms / 1000, 2) if avg_response_time_ms else 0
    
    return DashboardStats(
        total_documents=total_documents,
        queries_today=queries_today,
        active_agents=active_agents,
        avg_response_time=avg_response_time,
    )


@router.get("/activity", response_model=List[RecentActivity])
async def get_recent_activity(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[RecentActivity]:
    """Get recent activity for the current user."""
    user_id = current_user.id
    activities: List[RecentActivity] = []
    
    doc_stmt = (
        select(Document)
        .where(Document.user_id == user_id)
        .order_by(Document.created_at.desc())
        .limit(limit)
    )
    doc_result = await db.execute(doc_stmt)
    documents = doc_result.scalars().all()
    
    for doc in documents:
        activities.append(RecentActivity(
            id=str(doc.id),
            type="upload",
            description=f'Uploaded "{doc.filename}"',
            timestamp=doc.created_at,
        ))
    
    query_stmt = (
        select(Query)
        .where(Query.user_id == user_id)
        .order_by(Query.created_at.desc())
        .limit(limit)
    )
    query_result = await db.execute(query_stmt)
    queries = query_result.scalars().all()
    
    for query in queries:
        query_preview = query.query_text[:50] + "..." if len(query.query_text) > 50 else query.query_text
        activities.append(RecentActivity(
            id=str(query.id),
            type="query",
            description=f'Asked: "{query_preview}"',
            timestamp=query.created_at,
        ))
    
    agent_stmt = (
        select(AgentLog)
        .where(AgentLog.user_id == user_id)
        .order_by(AgentLog.created_at.desc())
        .limit(limit)
    )
    agent_result = await db.execute(agent_stmt)
    agent_logs = agent_result.scalars().all()
    
    for log in agent_logs:
        activities.append(RecentActivity(
            id=str(log.id),
            type="agent_execution",
            description=f'{log.agent_name} agent executed',
            timestamp=log.created_at,
        ))
    
    activities.sort(key=lambda x: x.timestamp, reverse=True)
    return activities[:limit]


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DashboardResponse:
    """Get complete dashboard data."""
    stats = await get_dashboard_stats(db=db, current_user=current_user)
    activity = await get_recent_activity(limit=5, db=db, current_user=current_user)
    
    return DashboardResponse(
        stats=stats,
        recent_activity=activity,
    )
