"""Agent Orchestrator for coordinating multiple agents."""

import uuid
from typing import Dict, Any, List, Optional
from enum import Enum

import structlog

from src.agents.base import BaseAgent
from src.agents.query_router import QueryRouterAgent, AgentType
from src.agents.document_analyzer import DocumentAnalyzerAgent
from src.agents.summarizer import SummarizerAgent
from src.agents.sql_generator import SQLGeneratorAgent
from src.services.llm_service import LLMService, get_llm_service

logger = structlog.get_logger()


class OrchestratorMode(str, Enum):
    """Orchestrator operation modes."""
    AUTO = "auto"  # Use query router to determine agent
    MANUAL = "manual"  # Use specified agent
    PIPELINE = "pipeline"  # Execute multiple agents in sequence


class RAGAgent(BaseAgent):
    """Agent for RAG-based question answering."""

    name = "rag_query"
    description = "Answers questions using document context through RAG"

    def __init__(self, **kwargs):
        """Initialize the RAG agent."""
        super().__init__(temperature=0.7, max_tokens=1024, **kwargs)

    @property
    def system_prompt(self) -> str:
        """Get the system prompt for RAG queries."""
        return """You are a helpful AI assistant for the EdgeAI RAG Platform.
You answer questions based on the provided document context.
Always cite your sources when answering.
If the context doesn't contain relevant information, say so clearly.
Be concise, accurate, and helpful in your responses."""

    async def execute(
        self,
        input_data: Dict[str, Any],
        context: List[str] | None = None,
    ) -> Dict[str, Any]:
        """Execute RAG-based question answering.

        Args:
            input_data: Must contain 'query' key with the user's question.
            context: Document context chunks for RAG.

        Returns:
            Dictionary with the answer and metadata.
        """
        query = input_data.get("query", "")

        if not query:
            return {
                "answer": "No question provided.",
                "error": "Missing query",
            }

        if not context:
            # Without context, provide general response
            response = await self.generate_response(query)
            return {
                "answer": response,
                "has_context": False,
                "context_chunks": 0,
            }

        # Generate response with context
        response = await self.generate_with_context(query, context)

        return {
            "answer": response,
            "has_context": True,
            "context_chunks": len(context),
        }


class AgentOrchestrator:
    """Orchestrator for coordinating multiple AI agents."""

    def __init__(
        self,
        llm_service: LLMService | None = None,
    ):
        """Initialize the orchestrator.

        Args:
            llm_service: Optional LLM service instance.
        """
        self.llm_service = llm_service or get_llm_service()
        
        # Initialize all agents
        self.agents: Dict[str, BaseAgent] = {
            AgentType.SUMMARIZER.value: SummarizerAgent(llm_service=self.llm_service),
            AgentType.SQL_GENERATOR.value: SQLGeneratorAgent(llm_service=self.llm_service),
            AgentType.DOCUMENT_ANALYZER.value: DocumentAnalyzerAgent(llm_service=self.llm_service),
            AgentType.RAG_QUERY.value: RAGAgent(llm_service=self.llm_service),
        }
        
        # Query router for automatic routing
        self.query_router = QueryRouterAgent(llm_service=self.llm_service)
        
        # Execution history for this session
        self.execution_history: List[Dict[str, Any]] = []

    def get_available_agents(self) -> List[Dict[str, str]]:
        """Get list of available agents.

        Returns:
            List of agent information dictionaries.
        """
        return [
            {
                "name": name,
                "description": agent.description,
                "status": "active",
            }
            for name, agent in self.agents.items()
        ]

    async def route_query(self, query: str) -> Dict[str, Any]:
        """Route a query to the appropriate agent.

        Args:
            query: The user's query.

        Returns:
            Routing result with selected agent and confidence.
        """
        result = await self.query_router.run(
            input_data={"query": query}
        )
        
        if result["success"]:
            return result["result"]
        else:
            # Default to RAG on routing failure
            return {
                "agent": AgentType.RAG_QUERY.value,
                "confidence": 0.0,
                "reason": f"Routing failed: {result.get('error', 'Unknown error')}",
            }

    async def execute(
        self,
        query: str,
        context: List[str] | None = None,
        mode: OrchestratorMode = OrchestratorMode.AUTO,
        agent_name: str | None = None,
        input_data: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Execute a query using the orchestrator.

        Args:
            query: The user's query.
            context: Optional document context for RAG.
            mode: Orchestration mode (auto, manual, pipeline).
            agent_name: Specific agent to use (for manual mode).
            input_data: Additional input data for the agent.

        Returns:
            Execution result with response and metadata.
        """
        execution_id = str(uuid.uuid4())
        
        logger.info(
            "Orchestrator execution started",
            execution_id=execution_id,
            mode=mode.value,
            query_preview=query[:50],
        )

        # Prepare input data
        full_input_data = input_data or {}
        full_input_data["query"] = query

        # Determine which agent to use
        if mode == OrchestratorMode.AUTO:
            routing_result = await self.route_query(query)
            selected_agent = routing_result["agent"]
            routing_info = routing_result
        elif mode == OrchestratorMode.MANUAL and agent_name:
            selected_agent = agent_name
            routing_info = {
                "agent": agent_name,
                "confidence": 1.0,
                "reason": "Manual selection",
            }
        else:
            # Default to RAG
            selected_agent = AgentType.RAG_QUERY.value
            routing_info = {
                "agent": AgentType.RAG_QUERY.value,
                "confidence": 0.5,
                "reason": "Default fallback",
            }

        # Validate agent exists
        if selected_agent not in self.agents:
            logger.warning(
                "Unknown agent selected, falling back to RAG",
                selected_agent=selected_agent,
            )
            selected_agent = AgentType.RAG_QUERY.value

        # Execute the selected agent
        agent = self.agents[selected_agent]
        result = await agent.run(input_data=full_input_data, context=context)

        # Build execution result
        execution_result = {
            "execution_id": execution_id,
            "query": query,
            "routing": routing_info,
            "agent_used": selected_agent,
            "agent_result": result,
            "success": result.get("success", False),
        }

        # Extract the main response
        if result.get("success"):
            agent_output = result.get("result", {})
            # Different agents return different keys
            if "answer" in agent_output:
                execution_result["response"] = agent_output["answer"]
            elif "summary" in agent_output:
                execution_result["response"] = agent_output["summary"]
            elif "analysis" in agent_output:
                execution_result["response"] = agent_output["analysis"]
            elif "sql" in agent_output:
                execution_result["response"] = agent_output["sql"]
                execution_result["explanation"] = agent_output.get("explanation", "")
            else:
                execution_result["response"] = str(agent_output)
        else:
            execution_result["response"] = f"Error: {result.get('error', 'Unknown error')}"

        # Store in execution history
        self.execution_history.append(execution_result)

        logger.info(
            "Orchestrator execution completed",
            execution_id=execution_id,
            agent_used=selected_agent,
            success=execution_result["success"],
        )

        return execution_result

    async def execute_pipeline(
        self,
        query: str,
        context: List[str] | None = None,
        pipeline: List[str] | None = None,
    ) -> Dict[str, Any]:
        """Execute a pipeline of agents sequentially.

        Args:
            query: The user's query.
            context: Optional document context.
            pipeline: List of agent names to execute in order.

        Returns:
            Combined results from all agents in the pipeline.
        """
        if not pipeline:
            # Default pipeline: analyze then summarize
            pipeline = [
                AgentType.DOCUMENT_ANALYZER.value,
                AgentType.SUMMARIZER.value,
            ]

        execution_id = str(uuid.uuid4())
        results = []
        current_context = context or []

        logger.info(
            "Pipeline execution started",
            execution_id=execution_id,
            pipeline=pipeline,
        )

        for i, agent_name in enumerate(pipeline):
            if agent_name not in self.agents:
                logger.warning(f"Skipping unknown agent: {agent_name}")
                continue

            agent = self.agents[agent_name]
            
            # For subsequent agents, use previous output as context
            if i > 0 and results:
                prev_result = results[-1]
                if prev_result.get("success"):
                    prev_output = prev_result.get("result", {})
                    # Extract text content from previous result
                    prev_text = (
                        prev_output.get("analysis") or
                        prev_output.get("summary") or
                        prev_output.get("answer") or
                        str(prev_output)
                    )
                    current_context = [prev_text]

            result = await agent.run(
                input_data={"query": query},
                context=current_context,
            )
            results.append({
                "agent": agent_name,
                "step": i + 1,
                **result,
            })

        # Get final response from last successful result
        final_response = ""
        for result in reversed(results):
            if result.get("success"):
                agent_output = result.get("result", {})
                final_response = (
                    agent_output.get("summary") or
                    agent_output.get("analysis") or
                    agent_output.get("answer") or
                    str(agent_output)
                )
                break

        return {
            "execution_id": execution_id,
            "query": query,
            "pipeline": pipeline,
            "steps": results,
            "final_response": final_response,
            "success": any(r.get("success") for r in results),
        }

    def get_execution_history(self) -> List[Dict[str, Any]]:
        """Get the execution history.

        Returns:
            List of previous execution results.
        """
        return self.execution_history

    def clear_history(self) -> None:
        """Clear the execution history."""
        self.execution_history = []

    def get_agent_info(self, agent_name: str) -> Dict[str, Any] | None:
        """Get information about a specific agent.

        Args:
            agent_name: The agent name.

        Returns:
            Agent information dictionary or None if not found.
        """
        if agent_name in self.agents:
            return self.agents[agent_name].get_info()
        return None


# Singleton instance
_orchestrator: AgentOrchestrator | None = None


def get_orchestrator() -> AgentOrchestrator:
    """Get the orchestrator singleton instance.

    Returns:
        The orchestrator instance.
    """
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator