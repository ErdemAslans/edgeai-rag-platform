"""Agent management endpoints."""

import uuid
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

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
from src.agents import get_orchestrator, OrchestratorMode

router = APIRouter()
logger = structlog.get_logger()

# Available agents with their capabilities
AVAILABLE_AGENTS = {
    "query_router": AgentInfo(
        name="query_router",
        description="Routes incoming queries to appropriate specialist agents based on intent",
        status="active",
        capabilities=["intent_classification", "agent_selection", "keyword_routing", "llm_routing"],
    ),
    "document_analyzer": AgentInfo(
        name="document_analyzer",
        description="Performs deep analysis of documents to extract insights, themes, and entities",
        status="active",
        capabilities=["theme_extraction", "entity_recognition", "structure_analysis", "sentiment_analysis"],
    ),
    "summarizer": AgentInfo(
        name="summarizer",
        description="Creates clear, concise summaries of documents or content in various formats",
        status="active",
        capabilities=["short_summary", "long_summary", "bullet_points", "executive_summary"],
    ),
    "sql_generator": AgentInfo(
        name="sql_generator",
        description="Converts natural language questions to SQL queries",
        status="active",
        capabilities=["sql_generation", "schema_understanding", "query_optimization"],
    ),
    "rag_query": AgentInfo(
        name="rag_query",
        description="Answers questions using document context through RAG (Retrieval Augmented Generation)",
        status="active",
        capabilities=["context_retrieval", "question_answering", "source_citation"],
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
    """Execute a specific agent with given input.
    
    The input_data should contain:
    - query: The text query or request for the agent
    - context: Optional list of context strings for RAG-based agents
    - Additional agent-specific parameters
    """
    if agent_name not in AVAILABLE_AGENTS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_name}' not found. Available agents: {list(AVAILABLE_AGENTS.keys())}",
        )
    
    start_time = time.time()
    agent_log_repo = AgentLogRepository(db)
    
    # Log agent execution start
    log_entry = await agent_log_repo.create({
        "agent_name": agent_name,
        "action": "execute",
        "input_data": request.input_data,
        "status": "started",
    })
    
    try:
        # Get orchestrator and execute the agent
        orchestrator = get_orchestrator()
        
        # Extract query and context from input data
        query = request.input_data.get("query", "")
        context = request.input_data.get("context", [])
        
        if not query:
            raise ValueError("Input data must contain a 'query' field")
        
        # Execute through orchestrator with manual mode to use specific agent
        result = await orchestrator.execute(
            query=query,
            context=context if context else None,
            mode=OrchestratorMode.MANUAL,
            agent_name=agent_name,
            input_data=request.input_data,
        )
        
        execution_time_ms = (time.time() - start_time) * 1000
        
        # Build output data
        output_data = {
            "response": result.get("response", ""),
            "agent_result": result.get("agent_result", {}),
            "routing": result.get("routing", {}),
            "success": result.get("success", False),
        }
        
        status_str = "completed" if result.get("success") else "failed"
        
        logger.info(
            "Agent execution completed",
            agent_name=agent_name,
            execution_time_ms=execution_time_ms,
            success=result.get("success"),
        )
        
    except Exception as e:
        execution_time_ms = (time.time() - start_time) * 1000
        output_data = {
            "error": str(e),
            "success": False,
        }
        status_str = "failed"
        
        logger.error(
            "Agent execution failed",
            agent_name=agent_name,
            error=str(e),
            execution_time_ms=execution_time_ms,
        )
    
    # Update log with completion
    await agent_log_repo.update(
        log_entry.id,
        {
            "output_data": output_data,
            "status": status_str,
            "execution_time_ms": execution_time_ms,
            "error_message": output_data.get("error") if status_str == "failed" else None,
        }
    )
    
    await db.commit()
    
    return AgentExecuteResponse(
        execution_id=log_entry.id,
        agent_name=agent_name,
        status=status_str,
        output=output_data,
        execution_time_ms=execution_time_ms,
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