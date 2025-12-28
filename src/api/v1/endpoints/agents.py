"""Agent management endpoints."""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db, CurrentUser
from src.api.v1.schemas.agents import (
    AgentInfo,
    AgentListResponse,
    AgentExecuteRequest,
    AgentExecuteResponse,
    AgentLogResponse,
    AgentLogsListResponse,
)
from src.db.repositories.agent_log import AgentLogRepository

router = APIRouter()

# Available agents
AVAILABLE_AGENTS = {
    "query_router": AgentInfo(
        name="query_router",
        description="Routes incoming queries to appropriate specialist agents",
        status="active",
        capabilities=["intent_classification", "agent_selection"],
    ),
    "document_analyzer": AgentInfo(
        name="document_analyzer",
        description="Extracts and analyzes information from documents",
        status="active",
        capabilities=["vector_search", "document_reading", "context_building"],
    ),
    "summarizer": AgentInfo(
        name="summarizer",
        description="Creates concise summaries of documents or content",
        status="active",
        capabilities=["document_reading", "summary_generation"],
    ),
    "sql_generator": AgentInfo(
        name="sql_generator",
        description="Converts natural language to SQL queries",
        status="active",
        capabilities=["schema_inspection", "sql_generation", "sql_validation"],
    ),
}


@router.get("/", response_model=AgentListResponse)
async def list_agents(
    current_user: CurrentUser,
) -> AgentListResponse:
    """List all available agents."""
    return AgentListResponse(
        agents=list(AVAILABLE_AGENTS.values()),
        total=len(AVAILABLE_AGENTS),
    )


@router.get("/{agent_name}/status", response_model=AgentInfo)
async def get_agent_status(
    agent_name: str,
    current_user: CurrentUser,
) -> AgentInfo:
    """Get status of a specific agent."""
    if agent_name not in AVAILABLE_AGENTS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_name}' not found",
        )
    
    return AVAILABLE_AGENTS[agent_name]


@router.post("/{agent_name}/execute", response_model=AgentExecuteResponse)
async def execute_agent(
    agent_name: str,
    request: AgentExecuteRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> AgentExecuteResponse:
    """Execute a specific agent with given input."""
    if agent_name not in AVAILABLE_AGENTS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_name}' not found",
        )
    
    agent_log_repo = AgentLogRepository(db)
    
    # Log agent execution start
    log_entry = await agent_log_repo.create({
        "agent_name": agent_name,
        "action": "execute",
        "input_data": request.input_data,
        "status": "started",
    })
    
    # TODO: Implement actual agent execution
    # 1. Get the appropriate agent
    # 2. Execute with input data
    # 3. Return results
    
    # Placeholder response
    output_data = {
        "message": f"Agent '{agent_name}' executed successfully",
        "input_received": request.input_data,
    }
    
    # Update log with completion
    await agent_log_repo.update(
        log_entry.id,
        {
            "output_data": output_data,
            "status": "completed",
            "execution_time_ms": 100.0,  # Placeholder
        }
    )
    
    return AgentExecuteResponse(
        execution_id=log_entry.id,
        agent_name=agent_name,
        status="completed",
        output=output_data,
        execution_time_ms=100.0,
    )


@router.get("/logs", response_model=AgentLogsListResponse)
async def get_agent_logs(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    agent_name: Optional[str] = Query(None),
) -> AgentLogsListResponse:
    """Get agent execution logs."""
    agent_log_repo = AgentLogRepository(db)
    
    logs, total = await agent_log_repo.get_logs(
        skip=skip,
        limit=limit,
        agent_name=agent_name,
    )
    
    return AgentLogsListResponse(
        logs=[
            AgentLogResponse(
                id=log.id,
                agent_name=log.agent_name,
                action=log.action,
                status=log.status,
                execution_time_ms=log.execution_time_ms,
                created_at=log.created_at,
                error_message=log.error_message,
            )
            for log in logs
        ],
        total=total,
        skip=skip,
        limit=limit,
    )