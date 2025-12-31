"""Query Router agent for directing queries to appropriate agents."""

from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass

from src.agents.base import BaseAgent


class AgentType(str, Enum):
    """Available custom agent types for routing."""
    SUMMARIZER = "summarizer"
    SQL_GENERATOR = "sql_generator"
    DOCUMENT_ANALYZER = "document_analyzer"
    RAG_QUERY = "rag_query"


class FrameworkType(str, Enum):
    """Available agent frameworks."""
    CUSTOM = "custom"
    LANGGRAPH = "langgraph"
    CREWAI = "crewai"
    GENAI = "genai"


@dataclass
class RoutingResult:
    """Result of query routing."""
    agent: str
    framework: str
    confidence: float
    reason: str
    fallback_agent: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent": self.agent,
            "framework": self.framework,
            "confidence": self.confidence,
            "reason": self.reason,
            "fallback_agent": self.fallback_agent,
        }


class QueryRouterAgent(BaseAgent):
    """Agent for routing user queries to the appropriate specialized agent."""

    name = "query_router"
    description = "Routes user queries to the most appropriate specialized agent"

    FRAMEWORK_AGENTS = {
        FrameworkType.LANGGRAPH: [
            ("research", ["research", "investigate", "find out", "explore", "deep dive"]),
            ("planning", ["plan", "schedule", "organize", "steps", "roadmap"]),
            ("reasoning", ["reason", "think through", "logic", "deduce", "infer"]),
        ],
        FrameworkType.CREWAI: [
            ("crew_research", ["team research", "collaborative", "multi-agent"]),
            ("crew_qa", ["quality check", "review", "validate", "verify"]),
            ("crew_writer", ["write report", "compose", "draft", "author"]),
        ],
        FrameworkType.GENAI: [
            ("vision", ["image", "picture", "photo", "visual", "see"]),
            ("multimodal", ["multimodal", "mixed content", "various formats"]),
            ("code_gen", ["code", "program", "function", "script", "implement"]),
        ],
    }

    def __init__(self, **kwargs):
        """Initialize the query router agent."""
        super().__init__(temperature=0.1, max_tokens=100, **kwargs)

    @property
    def system_prompt(self) -> str:
        """Get the system prompt for query routing."""
        return """You are a query routing expert. Your task is to analyze user queries and determine which specialized agent should handle them.

Available Custom Agents:
1. summarizer - For summarizing documents, text, or content
2. sql_generator - For generating SQL queries from natural language
3. document_analyzer - For deep analysis of documents, extracting insights
4. rag_query - For general question answering using document context

Available Framework Agents:
- LangGraph: research, planning, reasoning (complex multi-step tasks)
- CrewAI: crew_research, crew_qa, crew_writer (collaborative tasks)
- GenAI: vision, multimodal, code_gen (specialized AI capabilities)

Respond with the agent name only."""

    async def execute(
        self,
        input_data: Dict[str, Any],
        context: List[str] | None = None,
    ) -> Dict[str, Any]:
        """Route the query to the appropriate agent.

        Args:
            input_data: Must contain 'query' key with the user's query.
            context: Optional context (not used for routing).

        Returns:
            Dictionary with routing information.
        """
        query = input_data.get("query", "")
        prefer_framework = input_data.get("prefer_framework", None)
        
        if not query:
            return RoutingResult(
                agent=AgentType.RAG_QUERY.value,
                framework=FrameworkType.CUSTOM.value,
                confidence=0.0,
                reason="No query provided, defaulting to RAG query",
            ).to_dict()

        result = self._quick_route(query, prefer_framework)
        if result:
            return result.to_dict()

        prompt = f"Route this query to the appropriate agent: {query}"
        response = await self.generate_response(prompt)
        
        agent_name = response.strip().lower()
        
        valid_custom = [a.value for a in AgentType]
        if agent_name in valid_custom:
            return RoutingResult(
                agent=agent_name,
                framework=FrameworkType.CUSTOM.value,
                confidence=0.8,
                reason="LLM-based routing",
            ).to_dict()

        return RoutingResult(
            agent=AgentType.RAG_QUERY.value,
            framework=FrameworkType.CUSTOM.value,
            confidence=0.5,
            reason="Fallback to RAG query",
        ).to_dict()

    def _quick_route(
        self,
        query: str,
        prefer_framework: Optional[str] = None,
    ) -> Optional[RoutingResult]:
        """Perform quick keyword-based routing.

        Args:
            query: The user's query.
            prefer_framework: Optional preferred framework.

        Returns:
            RoutingResult if a clear match is found, None otherwise.
        """
        query_lower = query.lower()

        if prefer_framework:
            framework_result = self._route_to_framework(query_lower, prefer_framework)
            if framework_result:
                return framework_result

        sql_keywords = ["sql", "query database", "select from", "insert into", 
                       "database table", "join tables", "where clause"]
        if any(kw in query_lower for kw in sql_keywords):
            return RoutingResult(
                agent=AgentType.SQL_GENERATOR.value,
                framework=FrameworkType.CUSTOM.value,
                confidence=0.95,
                reason="SQL keywords detected",
            )

        summary_keywords = ["summarize", "summary", "summarise", "brief overview",
                          "condense", "shorten", "tldr", "key points", "recap"]
        if any(kw in query_lower for kw in summary_keywords):
            return RoutingResult(
                agent=AgentType.SUMMARIZER.value,
                framework=FrameworkType.CUSTOM.value,
                confidence=0.95,
                reason="Summary keywords detected",
            )

        analysis_keywords = ["analyze", "analyse", "analysis", "insights",
                           "themes", "entities", "extract patterns", "identify"]
        if any(kw in query_lower for kw in analysis_keywords):
            return RoutingResult(
                agent=AgentType.DOCUMENT_ANALYZER.value,
                framework=FrameworkType.CUSTOM.value,
                confidence=0.9,
                reason="Analysis keywords detected",
            )

        for framework, agents in self.FRAMEWORK_AGENTS.items():
            for agent_name, keywords in agents:
                if any(kw in query_lower for kw in keywords):
                    return RoutingResult(
                        agent=agent_name,
                        framework=framework.value,
                        confidence=0.85,
                        reason=f"Framework agent keywords detected ({framework.value})",
                        fallback_agent=AgentType.RAG_QUERY.value,
                    )

        return None

    def _route_to_framework(
        self,
        query: str,
        framework: str,
    ) -> Optional[RoutingResult]:
        """Route to a specific framework's agents.

        Args:
            query: The user's query (lowercase).
            framework: Framework name to route to.

        Returns:
            RoutingResult if a match is found in the framework.
        """
        try:
            framework_type = FrameworkType(framework.lower())
        except ValueError:
            return None

        if framework_type not in self.FRAMEWORK_AGENTS:
            return None

        agents = self.FRAMEWORK_AGENTS[framework_type]
        
        for agent_name, keywords in agents:
            if any(kw in query for kw in keywords):
                return RoutingResult(
                    agent=agent_name,
                    framework=framework_type.value,
                    confidence=0.9,
                    reason=f"Preferred framework routing ({framework_type.value})",
                )

        if agents:
            default_agent = agents[0][0]
            return RoutingResult(
                agent=default_agent,
                framework=framework_type.value,
                confidence=0.6,
                reason=f"Default agent for {framework_type.value}",
            )

        return None

    def get_available_agents(self) -> List[Dict[str, Any]]:
        """Get information about all available agents.

        Returns:
            List of dictionaries with agent information.
        """
        agents = [
            {
                "name": AgentType.SUMMARIZER.value,
                "description": "Summarizes documents and content",
                "framework": FrameworkType.CUSTOM.value,
            },
            {
                "name": AgentType.SQL_GENERATOR.value,
                "description": "Generates SQL queries from natural language",
                "framework": FrameworkType.CUSTOM.value,
            },
            {
                "name": AgentType.DOCUMENT_ANALYZER.value,
                "description": "Analyzes documents for insights and patterns",
                "framework": FrameworkType.CUSTOM.value,
            },
            {
                "name": AgentType.RAG_QUERY.value,
                "description": "Answers questions using document context",
                "framework": FrameworkType.CUSTOM.value,
            },
        ]

        for framework, framework_agents in self.FRAMEWORK_AGENTS.items():
            for agent_name, keywords in framework_agents:
                agents.append({
                    "name": agent_name,
                    "description": f"Framework agent ({framework.value}): {', '.join(keywords[:3])}",
                    "framework": framework.value,
                    "keywords": keywords,
                })

        return agents

    def get_frameworks(self) -> List[Dict[str, Any]]:
        """Get available frameworks and their agents.

        Returns:
            List of framework information.
        """
        frameworks = []
        
        frameworks.append({
            "name": FrameworkType.CUSTOM.value,
            "description": "Custom built-in agents",
            "agents": [a.value for a in AgentType],
        })

        for framework, agents in self.FRAMEWORK_AGENTS.items():
            frameworks.append({
                "name": framework.value,
                "description": f"{framework.value.title()} framework agents",
                "agents": [a[0] for a in agents],
            })

        return frameworks
