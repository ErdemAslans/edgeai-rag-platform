"""
Hybrid Agent Orchestrator for EdgeAI RAG Platform.

This orchestrator coordinates agents from three different frameworks:
- LangGraph: Graph-based workflow agents
- CrewAI: Multi-agent collaboration crews
- GenAI: Custom LLM-based agents

It provides a unified interface for executing queries across all frameworks.
"""

import asyncio
import uuid
import time
from typing import Dict, Any, List, Optional, Union
from enum import Enum

import structlog

from src.agents.base import BaseAgent
from src.agents.query_router import QueryRouterAgent, AgentType
from src.agents.document_analyzer import DocumentAnalyzerAgent
from src.agents.summarizer import SummarizerAgent
from src.agents.sql_generator import SQLGeneratorAgent
from src.agents.orchestrator import RAGAgent, OrchestratorMode
from src.services.llm_service import LLMService, get_llm_service

# Import framework-specific agents
from src.agents.langgraph_agents import (
    LangGraphResearchAgent,
    LangGraphAnalysisAgent,
    LangGraphReasoningAgent,
    list_langgraph_agents,
    get_langgraph_agent,
    AgentFramework,
)
from src.agents.crewai_agents import (
    CrewAIResearchCrew,
    CrewAIQACrew,
    CrewAICodeReviewCrew,
    list_crewai_agents,
    get_crewai_agent,
)
from src.agents.genai_agents import (
    GenAIConversationalAgent,
    GenAITaskExecutorAgent,
    GenAIKnowledgeAgent,
    GenAIReasoningAgent,
    GenAICreativeAgent,
    list_genai_agents,
    get_genai_agent,
)

logger = structlog.get_logger()


class HybridFramework(str, Enum):
    """Available agent frameworks."""
    CUSTOM = "custom"  # Original BaseAgent-based agents
    LANGGRAPH = "langgraph"  # LangGraph workflow agents
    CREWAI = "crewai"  # CrewAI multi-agent crews
    GENAI = "genai"  # Custom GenAI agents


class HybridAgentType(str, Enum):
    """All available agent types across frameworks."""
    # Custom agents
    RAG_QUERY = "rag_query"
    SUMMARIZER = "summarizer"
    SQL_GENERATOR = "sql_generator"
    DOCUMENT_ANALYZER = "document_analyzer"
    
    # LangGraph agents
    LG_RESEARCH = "lg_research"
    LG_ANALYSIS = "lg_analysis"
    LG_REASONING = "lg_reasoning"
    
    # CrewAI agents
    CREW_RESEARCH = "crew_research"
    CREW_QA = "crew_qa"
    CREW_CODE_REVIEW = "crew_code_review"
    
    # GenAI agents
    GENAI_CONVERSATIONAL = "genai_conversational"
    GENAI_TASK_EXECUTOR = "genai_task_executor"
    GENAI_KNOWLEDGE = "genai_knowledge"
    GENAI_REASONING = "genai_reasoning"
    GENAI_CREATIVE = "genai_creative"


# Mapping of agent types to frameworks
AGENT_FRAMEWORK_MAP = {
    HybridAgentType.RAG_QUERY: HybridFramework.CUSTOM,
    HybridAgentType.SUMMARIZER: HybridFramework.CUSTOM,
    HybridAgentType.SQL_GENERATOR: HybridFramework.CUSTOM,
    HybridAgentType.DOCUMENT_ANALYZER: HybridFramework.CUSTOM,
    
    HybridAgentType.LG_RESEARCH: HybridFramework.LANGGRAPH,
    HybridAgentType.LG_ANALYSIS: HybridFramework.LANGGRAPH,
    HybridAgentType.LG_REASONING: HybridFramework.LANGGRAPH,
    
    HybridAgentType.CREW_RESEARCH: HybridFramework.CREWAI,
    HybridAgentType.CREW_QA: HybridFramework.CREWAI,
    HybridAgentType.CREW_CODE_REVIEW: HybridFramework.CREWAI,
    
    HybridAgentType.GENAI_CONVERSATIONAL: HybridFramework.GENAI,
    HybridAgentType.GENAI_TASK_EXECUTOR: HybridFramework.GENAI,
    HybridAgentType.GENAI_KNOWLEDGE: HybridFramework.GENAI,
    HybridAgentType.GENAI_REASONING: HybridFramework.GENAI,
    HybridAgentType.GENAI_CREATIVE: HybridFramework.GENAI,
}


class HybridOrchestrator:
    """
    Unified orchestrator for all agent frameworks.
    
    This orchestrator manages agents from:
    - Custom framework (BaseAgent-based)
    - LangGraph (graph workflows)
    - CrewAI (multi-agent collaboration)
    - GenAI (custom LLM agents)
    """
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        """Initialize the hybrid orchestrator."""
        self.llm_service = llm_service
        self._initialized = False
        
        # Agent registries by framework
        self.custom_agents: Dict[str, BaseAgent] = {}
        self.langgraph_agents: Dict[str, Any] = {}
        self.crewai_agents: Dict[str, Any] = {}
        self.genai_agents: Dict[str, Any] = {}
        
        # Query router for automatic routing
        self.query_router: Optional[QueryRouterAgent] = None
        
        # Execution history
        self.execution_history: List[Dict[str, Any]] = []
        
    async def initialize(self):
        """Initialize all agent frameworks."""
        if self._initialized:
            return
            
        if self.llm_service is None:
            self.llm_service = get_llm_service()
        
        logger.info("Initializing Hybrid Orchestrator")
        
        # Initialize custom agents
        self.custom_agents = {
            HybridAgentType.RAG_QUERY.value: RAGAgent(llm_service=self.llm_service),
            HybridAgentType.SUMMARIZER.value: SummarizerAgent(llm_service=self.llm_service),
            HybridAgentType.SQL_GENERATOR.value: SQLGeneratorAgent(llm_service=self.llm_service),
            HybridAgentType.DOCUMENT_ANALYZER.value: DocumentAnalyzerAgent(llm_service=self.llm_service),
        }
        
        # Initialize LangGraph agents
        self.langgraph_agents = {
            HybridAgentType.LG_RESEARCH.value: LangGraphResearchAgent(self.llm_service),
            HybridAgentType.LG_ANALYSIS.value: LangGraphAnalysisAgent(self.llm_service),
            HybridAgentType.LG_REASONING.value: LangGraphReasoningAgent(self.llm_service),
        }
        for agent in self.langgraph_agents.values():
            await agent.initialize()
        
        # Initialize CrewAI agents
        self.crewai_agents = {
            HybridAgentType.CREW_RESEARCH.value: CrewAIResearchCrew(self.llm_service),
            HybridAgentType.CREW_QA.value: CrewAIQACrew(self.llm_service),
            HybridAgentType.CREW_CODE_REVIEW.value: CrewAICodeReviewCrew(self.llm_service),
        }
        for agent in self.crewai_agents.values():
            await agent.initialize()
        
        # Initialize GenAI agents
        self.genai_agents = {
            HybridAgentType.GENAI_CONVERSATIONAL.value: GenAIConversationalAgent(self.llm_service),
            HybridAgentType.GENAI_TASK_EXECUTOR.value: GenAITaskExecutorAgent(self.llm_service),
            HybridAgentType.GENAI_KNOWLEDGE.value: GenAIKnowledgeAgent(self.llm_service),
            HybridAgentType.GENAI_REASONING.value: GenAIReasoningAgent(self.llm_service),
            HybridAgentType.GENAI_CREATIVE.value: GenAICreativeAgent(self.llm_service),
        }
        for agent in self.genai_agents.values():
            await agent.initialize()
        
        # Initialize query router
        self.query_router = QueryRouterAgent(llm_service=self.llm_service)
        
        self._initialized = True
        logger.info(
            "Hybrid Orchestrator initialized",
            custom_agents=len(self.custom_agents),
            langgraph_agents=len(self.langgraph_agents),
            crewai_agents=len(self.crewai_agents),
            genai_agents=len(self.genai_agents),
        )
    
    def get_all_agents(self) -> List[Dict[str, Any]]:
        """Get information about all available agents."""
        agents = []
        
        # Custom agents
        for name, agent in self.custom_agents.items():
            agents.append({
                "name": name,
                "framework": HybridFramework.CUSTOM.value,
                "description": agent.description,
                "status": "active",
            })
        
        # LangGraph agents
        for info in list_langgraph_agents():
            agents.append({
                "name": info["name"],
                "framework": HybridFramework.LANGGRAPH.value,
                "description": info["description"],
                "status": "active",
                "workflow_type": info.get("workflow_type"),
            })
        
        # CrewAI agents
        for info in list_crewai_agents():
            agents.append({
                "name": info["name"],
                "framework": HybridFramework.CREWAI.value,
                "description": info["description"],
                "status": "active",
                "crew_agents": info.get("agents"),
            })
        
        # GenAI agents
        for info in list_genai_agents():
            agents.append({
                "name": info["name"],
                "framework": HybridFramework.GENAI.value,
                "description": info["description"],
                "status": "active",
                "capabilities": info.get("capabilities"),
            })
        
        return agents
    
    def get_agents_by_framework(self, framework: HybridFramework) -> List[Dict[str, Any]]:
        """Get agents for a specific framework."""
        all_agents = self.get_all_agents()
        return [a for a in all_agents if a["framework"] == framework.value]
    
    async def smart_route(self, query: str, context: Optional[str] = None) -> Dict[str, Any]:
        """
        Intelligently route a query to the best agent.
        
        Uses the query router plus additional heuristics to select
        the most appropriate agent from any framework.
        """
        await self.initialize()
        
        # Use base query router for initial routing
        base_result = await self.query_router.run(input_data={"query": query})
        
        if base_result["success"]:
            base_agent = base_result["result"]["agent"]
            confidence = base_result["result"]["confidence"]
        else:
            base_agent = AgentType.RAG_QUERY.value
            confidence = 0.5
        
        # Apply additional heuristics to potentially upgrade to advanced agents
        enhanced_routing = await self._enhance_routing(query, base_agent, confidence)
        
        return enhanced_routing
    
    async def _enhance_routing(
        self,
        query: str,
        base_agent: str,
        base_confidence: float
    ) -> Dict[str, Any]:
        """Enhance routing with multi-framework awareness."""
        query_lower = query.lower()
        
        # Keywords for LangGraph agents
        langgraph_keywords = {
            "research": [HybridAgentType.LG_RESEARCH.value, 0.85],
            "investigate": [HybridAgentType.LG_RESEARCH.value, 0.8],
            "analyze deeply": [HybridAgentType.LG_ANALYSIS.value, 0.85],
            "detailed analysis": [HybridAgentType.LG_ANALYSIS.value, 0.85],
            "reason through": [HybridAgentType.LG_REASONING.value, 0.85],
            "step by step": [HybridAgentType.LG_REASONING.value, 0.8],
        }
        
        # Keywords for CrewAI agents
        crewai_keywords = {
            "team": [HybridAgentType.CREW_RESEARCH.value, 0.8],
            "collaborate": [HybridAgentType.CREW_RESEARCH.value, 0.8],
            "fact check": [HybridAgentType.CREW_QA.value, 0.85],
            "verify": [HybridAgentType.CREW_QA.value, 0.8],
            "code review": [HybridAgentType.CREW_CODE_REVIEW.value, 0.9],
            "review code": [HybridAgentType.CREW_CODE_REVIEW.value, 0.9],
        }
        
        # Keywords for GenAI agents
        genai_keywords = {
            "chat": [HybridAgentType.GENAI_CONVERSATIONAL.value, 0.8],
            "conversation": [HybridAgentType.GENAI_CONVERSATIONAL.value, 0.8],
            "task": [HybridAgentType.GENAI_TASK_EXECUTOR.value, 0.75],
            "execute": [HybridAgentType.GENAI_TASK_EXECUTOR.value, 0.75],
            "knowledge base": [HybridAgentType.GENAI_KNOWLEDGE.value, 0.85],
            "creative": [HybridAgentType.GENAI_CREATIVE.value, 0.85],
            "write story": [HybridAgentType.GENAI_CREATIVE.value, 0.9],
            "generate ideas": [HybridAgentType.GENAI_CREATIVE.value, 0.85],
        }
        
        # Check for keyword matches
        best_match = {
            "agent": base_agent,
            "confidence": base_confidence,
            "framework": AGENT_FRAMEWORK_MAP.get(
                HybridAgentType(base_agent) if base_agent in [e.value for e in HybridAgentType] else HybridAgentType.RAG_QUERY,
                HybridFramework.CUSTOM
            ).value,
            "reason": "Base routing",
        }
        
        all_keywords = {**langgraph_keywords, **crewai_keywords, **genai_keywords}
        
        for keyword, (agent, conf) in all_keywords.items():
            if keyword in query_lower and conf > best_match["confidence"]:
                best_match = {
                    "agent": agent,
                    "confidence": conf,
                    "framework": AGENT_FRAMEWORK_MAP[HybridAgentType(agent)].value,
                    "reason": f"Keyword match: '{keyword}'",
                }
        
        return best_match
    
    async def execute(
        self,
        query: str,
        context: Optional[List[str]] = None,
        sources: Optional[List[Dict[str, Any]]] = None,
        mode: OrchestratorMode = OrchestratorMode.AUTO,
        agent_name: Optional[str] = None,
        framework: Optional[HybridFramework] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute a query using the hybrid orchestrator.
        
        Args:
            query: The user's query
            context: Document context chunks for RAG
            sources: Source documents with metadata
            mode: Orchestration mode (auto, manual, pipeline)
            agent_name: Specific agent to use (for manual mode)
            framework: Specific framework to use
            **kwargs: Additional arguments for the agent
            
        Returns:
            Execution result with response and metadata
        """
        await self.initialize()
        
        execution_id = str(uuid.uuid4())
        start_time = time.time()
        
        logger.info(
            "Hybrid orchestrator execution started",
            execution_id=execution_id,
            mode=mode.value,
            query_preview=query[:50] if query else "",
        )
        
        # Determine which agent to use
        if mode == OrchestratorMode.MANUAL and agent_name:
            selected_agent = agent_name
            routing_info = {
                "agent": agent_name,
                "confidence": 1.0,
                "framework": framework.value if framework else self._get_agent_framework(agent_name),
                "reason": "Manual selection",
            }
        elif mode == OrchestratorMode.AUTO:
            routing_info = await self.smart_route(query, context[0] if context else None)
            selected_agent = routing_info["agent"]
        else:
            # Default to RAG
            selected_agent = HybridAgentType.RAG_QUERY.value
            routing_info = {
                "agent": selected_agent,
                "confidence": 0.5,
                "framework": HybridFramework.CUSTOM.value,
                "reason": "Default fallback",
            }
        
        # Execute the selected agent
        agent_framework = routing_info.get("framework", self._get_agent_framework(selected_agent))
        
        try:
            if agent_framework == HybridFramework.CUSTOM.value:
                result = await self._execute_custom_agent(selected_agent, query, context, **kwargs)
            elif agent_framework == HybridFramework.LANGGRAPH.value:
                result = await self._execute_langgraph_agent(selected_agent, query, context, **kwargs)
            elif agent_framework == HybridFramework.CREWAI.value:
                result = await self._execute_crewai_agent(selected_agent, query, context, sources, **kwargs)
            elif agent_framework == HybridFramework.GENAI.value:
                result = await self._execute_genai_agent(selected_agent, query, context, sources, **kwargs)
            else:
                result = {"error": f"Unknown framework: {agent_framework}", "success": False}
        except Exception as e:
            logger.error(f"Agent execution error: {e}", exc_info=True)
            result = {"error": str(e), "success": False}
        
        execution_time = time.time() - start_time
        
        # Build execution result
        execution_result = {
            "execution_id": execution_id,
            "query": query,
            "routing": routing_info,
            "agent_used": selected_agent,
            "framework": agent_framework,
            "execution_time": execution_time,
            "success": result.get("success", False),
        }
        
        # Extract the main response
        if result.get("success", True) and "error" not in result:
            execution_result["response"] = result.get("result", str(result))
            execution_result["agent_result"] = result
        else:
            execution_result["response"] = f"Error: {result.get('error', 'Unknown error')}"
            execution_result["error"] = result.get("error")
        
        # Add framework-specific metadata
        if "phases" in result:
            execution_result["phases"] = result["phases"]
        if "reasoning_trace" in result:
            execution_result["reasoning_trace"] = result["reasoning_trace"]
        if "steps_executed" in result:
            execution_result["steps_executed"] = result["steps_executed"]
        
        # Store in execution history
        self.execution_history.append(execution_result)
        
        logger.info(
            "Hybrid orchestrator execution completed",
            execution_id=execution_id,
            agent_used=selected_agent,
            framework=agent_framework,
            success=execution_result["success"],
            execution_time=execution_time,
        )
        
        return execution_result
    
    async def _execute_custom_agent(
        self,
        agent_name: str,
        query: str,
        context: Optional[List[str]],
        **kwargs
    ) -> Dict[str, Any]:
        """Execute a custom BaseAgent-based agent."""
        if agent_name not in self.custom_agents:
            return {"error": f"Unknown custom agent: {agent_name}", "success": False}
        
        agent = self.custom_agents[agent_name]
        result = await agent.run(input_data={"query": query}, context=context)
        
        if result.get("success"):
            agent_output = result.get("result", {})
            response = (
                agent_output.get("answer") or
                agent_output.get("summary") or
                agent_output.get("analysis") or
                agent_output.get("sql") or
                str(agent_output)
            )
            return {
                "result": response,
                "success": True,
                "agent": agent_name,
                "framework": "custom",
                "details": agent_output,
            }
        else:
            return {"error": result.get("error", "Unknown error"), "success": False}
    
    async def _execute_langgraph_agent(
        self,
        agent_name: str,
        query: str,
        context: Optional[List[str]],
        **kwargs
    ) -> Dict[str, Any]:
        """Execute a LangGraph agent."""
        if agent_name not in self.langgraph_agents:
            return {"error": f"Unknown LangGraph agent: {agent_name}", "success": False}
        
        agent = self.langgraph_agents[agent_name]
        context_str = "\n".join(context) if context else None
        
        result = await agent.execute(query=query, context=context_str, **kwargs)
        result["success"] = True
        return result
    
    async def _execute_crewai_agent(
        self,
        agent_name: str,
        query: str,
        context: Optional[List[str]],
        sources: Optional[List[Dict[str, Any]]],
        **kwargs
    ) -> Dict[str, Any]:
        """Execute a CrewAI agent."""
        if agent_name not in self.crewai_agents:
            return {"error": f"Unknown CrewAI agent: {agent_name}", "success": False}
        
        agent = self.crewai_agents[agent_name]
        context_str = "\n".join(context) if context else None
        
        # Different CrewAI agents have different interfaces
        if agent_name == HybridAgentType.CREW_QA.value:
            result = await agent.execute(question=query, context=context_str, sources=sources, **kwargs)
        elif agent_name == HybridAgentType.CREW_CODE_REVIEW.value:
            # For code review, the query should contain code
            result = await agent.execute(code=query, **kwargs)
        else:
            result = await agent.execute(query=query, context=context_str, **kwargs)
        
        result["success"] = True
        return result
    
    async def _execute_genai_agent(
        self,
        agent_name: str,
        query: str,
        context: Optional[List[str]],
        sources: Optional[List[Dict[str, Any]]],
        **kwargs
    ) -> Dict[str, Any]:
        """Execute a GenAI agent."""
        if agent_name not in self.genai_agents:
            return {"error": f"Unknown GenAI agent: {agent_name}", "success": False}
        
        agent = self.genai_agents[agent_name]
        context_str = "\n".join(context) if context else None
        
        # Different GenAI agents have different interfaces
        if agent_name == HybridAgentType.GENAI_CONVERSATIONAL.value:
            result = await agent.execute(message=query, context=context_str, **kwargs)
        elif agent_name == HybridAgentType.GENAI_TASK_EXECUTOR.value:
            result = await agent.execute(task=query, context=context_str, **kwargs)
        elif agent_name == HybridAgentType.GENAI_KNOWLEDGE.value:
            result = await agent.execute(question=query, sources=sources, **kwargs)
        elif agent_name == HybridAgentType.GENAI_REASONING.value:
            result = await agent.execute(problem=query, context=context_str, **kwargs)
        elif agent_name == HybridAgentType.GENAI_CREATIVE.value:
            result = await agent.execute(prompt=query, **kwargs)
        else:
            return {"error": f"Unknown GenAI agent: {agent_name}", "success": False}
        
        result["success"] = True
        return result
    
    def _get_agent_framework(self, agent_name: str) -> str:
        """Get the framework for an agent."""
        if agent_name in self.custom_agents:
            return HybridFramework.CUSTOM.value
        elif agent_name in self.langgraph_agents:
            return HybridFramework.LANGGRAPH.value
        elif agent_name in self.crewai_agents:
            return HybridFramework.CREWAI.value
        elif agent_name in self.genai_agents:
            return HybridFramework.GENAI.value
        else:
            return HybridFramework.CUSTOM.value
    
    async def execute_multi_framework(
        self,
        query: str,
        frameworks: List[HybridFramework],
        context: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute a query across multiple frameworks and compare results.
        
        Useful for complex queries where different perspectives are valuable.
        """
        await self.initialize()
        
        execution_id = str(uuid.uuid4())
        results = {}
        
        for framework in frameworks:
            agents = self.get_agents_by_framework(framework)
            if agents:
                # Use the first agent from each framework
                agent_name = agents[0]["name"]
                result = await self.execute(
                    query=query,
                    context=context,
                    mode=OrchestratorMode.MANUAL,
                    agent_name=agent_name,
                    framework=framework,
                    **kwargs
                )
                results[framework.value] = result
        
        return {
            "execution_id": execution_id,
            "query": query,
            "multi_framework_results": results,
            "frameworks_used": [f.value for f in frameworks],
        }
    
    def get_execution_history(self) -> List[Dict[str, Any]]:
        """Get the execution history."""
        return self.execution_history
    
    def clear_history(self):
        """Clear the execution history."""
        self.execution_history = []


# Singleton instance
_hybrid_orchestrator: Optional[HybridOrchestrator] = None
_hybrid_orchestrator_lock = asyncio.Lock()


async def get_hybrid_orchestrator() -> HybridOrchestrator:
    """Get the hybrid orchestrator singleton instance."""
    global _hybrid_orchestrator
    
    # Fast path - already initialized
    if _hybrid_orchestrator is not None:
        return _hybrid_orchestrator
    
    # Thread-safe initialization with double-check pattern
    async with _hybrid_orchestrator_lock:
        if _hybrid_orchestrator is None:
            _hybrid_orchestrator = HybridOrchestrator()
            await _hybrid_orchestrator.initialize()
    return _hybrid_orchestrator