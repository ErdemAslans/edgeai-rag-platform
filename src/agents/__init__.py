"""Agents package for AI agent implementations."""

from src.agents.base import BaseAgent
from src.agents.query_router import QueryRouterAgent, AgentType
from src.agents.document_analyzer import DocumentAnalyzerAgent
from src.agents.summarizer import SummarizerAgent
from src.agents.sql_generator import SQLGeneratorAgent
from src.agents.orchestrator import (
    AgentOrchestrator,
    OrchestratorMode,
    RAGAgent,
    get_orchestrator,
)

# LangGraph agents
from src.agents.langgraph_agents import (
    LangGraphResearchAgent,
    LangGraphAnalysisAgent,
    LangGraphReasoningAgent,
    AgentFramework,
    list_langgraph_agents,
    get_langgraph_agent,
)

# CrewAI agents
from src.agents.crewai_agents import (
    CrewAIResearchCrew,
    CrewAIQACrew,
    CrewAICodeReviewCrew,
    list_crewai_agents,
    get_crewai_agent,
)

# GenAI agents
from src.agents.genai_agents import (
    GenAIConversationalAgent,
    GenAITaskExecutorAgent,
    GenAIKnowledgeAgent,
    GenAIReasoningAgent,
    GenAICreativeAgent,
    list_genai_agents,
    get_genai_agent,
)

# Hybrid orchestrator
from src.agents.hybrid_orchestrator import (
    HybridOrchestrator,
    HybridFramework,
    HybridAgentType,
    get_hybrid_orchestrator,
)

__all__ = [
    # Base
    "BaseAgent",
    "QueryRouterAgent",
    "AgentType",
    "DocumentAnalyzerAgent",
    "SummarizerAgent",
    "SQLGeneratorAgent",
    # Original orchestrator
    "AgentOrchestrator",
    "OrchestratorMode",
    "RAGAgent",
    "get_orchestrator",
    # LangGraph
    "LangGraphResearchAgent",
    "LangGraphAnalysisAgent",
    "LangGraphReasoningAgent",
    "AgentFramework",
    "list_langgraph_agents",
    "get_langgraph_agent",
    # CrewAI
    "CrewAIResearchCrew",
    "CrewAIQACrew",
    "CrewAICodeReviewCrew",
    "list_crewai_agents",
    "get_crewai_agent",
    # GenAI
    "GenAIConversationalAgent",
    "GenAITaskExecutorAgent",
    "GenAIKnowledgeAgent",
    "GenAIReasoningAgent",
    "GenAICreativeAgent",
    "list_genai_agents",
    "get_genai_agent",
    # Hybrid orchestrator
    "HybridOrchestrator",
    "HybridFramework",
    "HybridAgentType",
    "get_hybrid_orchestrator",
]