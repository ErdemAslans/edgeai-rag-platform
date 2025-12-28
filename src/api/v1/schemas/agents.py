"""Agent schemas."""

import uuid
from datetime import datetime
from typing import List, Optional, Any, Dict

from pydantic import BaseModel


class AgentInfo(BaseModel):
    """Schema for agent information."""
    name: str
    description: str
    status: str
    capabilities: List[str]


class AgentListResponse(BaseModel):
    """Schema for list of agents."""
    agents: List[AgentInfo]
    total: int


class AgentExecuteRequest(BaseModel):
    """Schema for agent execution request."""
    input_data: Dict[str, Any]
    options: Optional[Dict[str, Any]] = None


class AgentExecuteResponse(BaseModel):
    """Schema for agent execution response."""
    execution_id: uuid.UUID
    agent_name: str
    status: str
    output: Dict[str, Any]
    execution_time_ms: float


class AgentLogResponse(BaseModel):
    """Schema for agent log entry."""
    id: uuid.UUID
    agent_name: str
    action: Optional[str]
    status: str
    execution_time_ms: Optional[float]
    created_at: datetime
    error_message: Optional[str] = None


class AgentLogsListResponse(BaseModel):
    """Schema for paginated agent logs."""
    logs: List[AgentLogResponse]
    total: int
    skip: int
    limit: int