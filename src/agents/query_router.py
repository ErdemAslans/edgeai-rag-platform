"""Query Router agent for directing queries to appropriate agents."""

from typing import Dict, Any, List
from enum import Enum

from src.agents.base import BaseAgent


class AgentType(str, Enum):
    """Available agent types for routing."""
    SUMMARIZER = "summarizer"
    SQL_GENERATOR = "sql_generator"
    DOCUMENT_ANALYZER = "document_analyzer"
    RAG_QUERY = "rag_query"


class QueryRouterAgent(BaseAgent):
    """Agent for routing user queries to the appropriate specialized agent."""

    name = "query_router"
    description = "Routes user queries to the most appropriate specialized agent"

    def __init__(self, **kwargs):
        """Initialize the query router agent."""
        super().__init__(temperature=0.1, max_tokens=100, **kwargs)

    @property
    def system_prompt(self) -> str:
        """Get the system prompt for query routing."""
        return """You are a query routing expert. Your task is to analyze user queries and determine which specialized agent should handle them.

Available agents:
1. summarizer - For summarizing documents, text, or content. Use when the user wants a condensed version of information.
2. sql_generator - For generating SQL queries from natural language. Use when the user wants to query a database.
3. document_analyzer - For deep analysis of documents, extracting insights, themes, entities, and relationships.
4. rag_query - For general question answering that requires searching through documents for relevant information.

Rules:
- If the query mentions "summarize", "summary", "brief", "condense", use summarizer
- If the query mentions "SQL", "query", "database", "table", "select", use sql_generator
- If the query mentions "analyze", "analysis", "insights", "themes", "entities", use document_analyzer
- For general questions about document content, use rag_query

Respond with ONLY the agent name (summarizer, sql_generator, document_analyzer, or rag_query), nothing else."""

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
            Dictionary with 'agent' key indicating the selected agent.
        """
        query = input_data.get("query", "")
        
        if not query:
            return {
                "agent": AgentType.RAG_QUERY.value,
                "confidence": 0.0,
                "reason": "No query provided, defaulting to RAG query",
            }

        # Quick keyword-based routing for obvious cases
        quick_route = self._quick_route(query)
        if quick_route:
            return {
                "agent": quick_route,
                "confidence": 0.9,
                "reason": "Keyword-based routing",
            }

        # Use LLM for ambiguous cases
        prompt = f"Route this query to the appropriate agent: {query}"
        response = await self.generate_response(prompt)
        
        agent_name = response.strip().lower()
        
        # Validate the response
        valid_agents = [a.value for a in AgentType]
        if agent_name not in valid_agents:
            agent_name = AgentType.RAG_QUERY.value

        return {
            "agent": agent_name,
            "confidence": 0.8,
            "reason": "LLM-based routing",
        }

    def _quick_route(self, query: str) -> str | None:
        """Perform quick keyword-based routing.

        Args:
            query: The user's query.

        Returns:
            Agent name if a clear match is found, None otherwise.
        """
        query_lower = query.lower()

        # SQL Generator keywords
        sql_keywords = ["sql", "query", "select", "insert", "update", "delete", 
                       "database", "table", "join", "where clause"]
        if any(kw in query_lower for kw in sql_keywords):
            return AgentType.SQL_GENERATOR.value

        # Summarizer keywords
        summary_keywords = ["summarize", "summary", "summarise", "brief", 
                          "condense", "shorten", "tldr", "key points"]
        if any(kw in query_lower for kw in summary_keywords):
            return AgentType.SUMMARIZER.value

        # Document Analyzer keywords
        analysis_keywords = ["analyze", "analyse", "analysis", "insights",
                           "themes", "entities", "extract", "identify patterns"]
        if any(kw in query_lower for kw in analysis_keywords):
            return AgentType.DOCUMENT_ANALYZER.value

        return None

    def get_available_agents(self) -> List[Dict[str, str]]:
        """Get information about available agents.

        Returns:
            List of dictionaries with agent information.
        """
        return [
            {
                "name": AgentType.SUMMARIZER.value,
                "description": "Summarizes documents and content",
            },
            {
                "name": AgentType.SQL_GENERATOR.value,
                "description": "Generates SQL queries from natural language",
            },
            {
                "name": AgentType.DOCUMENT_ANALYZER.value,
                "description": "Analyzes documents for insights and patterns",
            },
            {
                "name": AgentType.RAG_QUERY.value,
                "description": "Answers questions using document context",
            },
        ]