"""LangGraph-based agents for graph workflow processing."""

from typing import Dict, Any, List, TypedDict, Annotated, Sequence, Optional
from enum import Enum
import operator

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
import structlog

from src.services.llm_service import LLMService, get_llm_service

logger = structlog.get_logger()


class AgentFramework(str, Enum):
    """Agent framework types."""
    LANGGRAPH = "langgraph"
    CREWAI = "crewai"
    GENAI = "genai"  # Custom/native


# LangGraph State Types
class ResearchState(TypedDict):
    """State for research workflow."""
    query: str
    context: List[str]
    research_notes: List[str]
    final_answer: str
    current_step: str
    iteration: int
    max_iterations: int


class AnalysisState(TypedDict):
    """State for analysis workflow."""
    query: str
    context: List[str]
    entities: List[str]
    themes: List[str]
    summary: str
    analysis: str
    current_step: str


class MultiStepState(TypedDict):
    """State for multi-step reasoning."""
    query: str
    context: List[str]
    steps: List[Dict[str, str]]
    current_step: int
    final_answer: str
    reasoning_chain: List[str]


class LangGraphResearchAgent:
    """LangGraph-based research agent with iterative refinement."""

    name = "langgraph_research"
    description = "Research agent using LangGraph for iterative document research"
    framework = AgentFramework.LANGGRAPH

    def __init__(self, llm_service: LLMService | None = None):
        """Initialize the research agent."""
        self.llm_service = llm_service
        self.graph = None
        self._initialized = False

    async def initialize(self):
        """Initialize the agent asynchronously."""
        if self._initialized:
            return
        if self.llm_service is None:
            self.llm_service = get_llm_service()
        self.graph = self._build_graph()
        self._initialized = True

    def _build_graph(self) -> StateGraph:
        """Build the research workflow graph."""
        workflow = StateGraph(ResearchState)

        # Add nodes
        workflow.add_node("analyze_query", self._analyze_query)
        workflow.add_node("search_context", self._search_context)
        workflow.add_node("synthesize", self._synthesize)
        workflow.add_node("refine", self._refine)
        workflow.add_node("finalize", self._finalize)

        # Add edges
        workflow.set_entry_point("analyze_query")
        workflow.add_edge("analyze_query", "search_context")
        workflow.add_edge("search_context", "synthesize")
        workflow.add_conditional_edges(
            "synthesize",
            self._should_refine,
            {
                "refine": "refine",
                "finalize": "finalize",
            }
        )
        workflow.add_edge("refine", "search_context")
        workflow.add_edge("finalize", END)

        return workflow.compile()

    async def _analyze_query(self, state: ResearchState) -> ResearchState:
        """Analyze the query to understand research needs."""
        query = state["query"]
        
        prompt = f"""Analyze this research query and identify key aspects to investigate:

Query: {query}

Provide a brief analysis of:
1. Main topic
2. Key questions to answer
3. Type of information needed"""

        response = await self.llm_service.generate(
            prompt=prompt,
            system_prompt="You are a research analyst. Analyze queries to plan research.",
            temperature=0.3,
            max_tokens=300,
        )

        state["research_notes"].append(f"Query Analysis: {response}")
        state["current_step"] = "analyze_query"
        return state

    async def _search_context(self, state: ResearchState) -> ResearchState:
        """Process context for relevant information."""
        context = state["context"]
        query = state["query"]
        
        if not context:
            state["research_notes"].append("No context available for research.")
            return state

        context_text = "\n\n".join(context[:5])  # Use top 5 chunks
        
        prompt = f"""Extract relevant information from these documents for the query:

Query: {query}

Documents:
{context_text}

Extract and summarize the most relevant facts and information."""

        response = await self.llm_service.generate(
            prompt=prompt,
            system_prompt="You are a research assistant extracting relevant information from documents.",
            temperature=0.2,
            max_tokens=500,
        )

        state["research_notes"].append(f"Extracted Info (Iteration {state['iteration']}): {response}")
        state["current_step"] = "search_context"
        return state

    async def _synthesize(self, state: ResearchState) -> ResearchState:
        """Synthesize research findings into an answer."""
        notes = "\n\n".join(state["research_notes"])
        query = state["query"]

        prompt = f"""Based on the research notes, synthesize a comprehensive answer:

Query: {query}

Research Notes:
{notes}

Provide a well-organized answer based on the research."""

        response = await self.llm_service.generate(
            prompt=prompt,
            system_prompt="You are a research synthesizer creating comprehensive answers from research notes.",
            temperature=0.4,
            max_tokens=800,
        )

        state["final_answer"] = response
        state["current_step"] = "synthesize"
        state["iteration"] += 1
        return state

    def _should_refine(self, state: ResearchState) -> str:
        """Decide whether to refine the answer or finalize."""
        # Simple heuristic: refine if answer is short and iterations allow
        if state["iteration"] < state["max_iterations"]:
            if len(state["final_answer"]) < 200:
                return "refine"
        return "finalize"

    async def _refine(self, state: ResearchState) -> ResearchState:
        """Refine the research by identifying gaps."""
        prompt = f"""The current answer may be incomplete. Identify what additional information is needed:

Query: {state['query']}
Current Answer: {state['final_answer']}

What aspects need more research?"""

        response = await self.llm_service.generate(
            prompt=prompt,
            system_prompt="You identify gaps in research answers.",
            temperature=0.3,
            max_tokens=200,
        )

        state["research_notes"].append(f"Refinement needed: {response}")
        state["current_step"] = "refine"
        return state

    async def _finalize(self, state: ResearchState) -> ResearchState:
        """Finalize the research answer."""
        state["current_step"] = "complete"
        return state

    async def execute(
        self,
        query: str,
        context: Optional[str] = None,
        max_iterations: int = 2,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute the research workflow."""
        await self.initialize()
        
        # Convert context string to list if needed
        context_list = context.split("\n\n") if context else []
        
        initial_state: ResearchState = {
            "query": query,
            "context": context_list,
            "research_notes": [],
            "final_answer": "",
            "current_step": "start",
            "iteration": 0,
            "max_iterations": max_iterations,
        }

        try:
            # Run the graph
            final_state = await self.graph.ainvoke(initial_state)
            
            return {
                "result": final_state["final_answer"],
                "agent": self.name,
                "framework": self.framework.value,
                "research_notes": final_state["research_notes"],
                "iterations": final_state["iteration"],
            }
        except Exception as e:
            logger.error("LangGraph research agent failed", error=str(e))
            return {
                "error": str(e),
                "agent": self.name,
                "framework": self.framework.value,
            }

    async def run(
        self,
        query: str,
        context: List[str] | None = None,
        max_iterations: int = 2,
    ) -> Dict[str, Any]:
        """Run the research workflow (legacy interface)."""
        context_str = "\n\n".join(context) if context else None
        return await self.execute(query=query, context=context_str, max_iterations=max_iterations)


class LangGraphAnalysisAgent:
    """LangGraph-based analysis agent for document analysis."""

    name = "langgraph_analysis"
    description = "Analysis agent using LangGraph for structured document analysis"
    framework = AgentFramework.LANGGRAPH

    def __init__(self, llm_service: LLMService | None = None):
        """Initialize the analysis agent."""
        self.llm_service = llm_service
        self.graph = None
        self._initialized = False

    async def initialize(self):
        """Initialize the agent asynchronously."""
        if self._initialized:
            return
        if self.llm_service is None:
            self.llm_service = get_llm_service()
        self.graph = self._build_graph()
        self._initialized = True

    def _build_graph(self) -> StateGraph:
        """Build the analysis workflow graph."""
        workflow = StateGraph(AnalysisState)

        # Add nodes for parallel-like processing
        workflow.add_node("extract_entities", self._extract_entities)
        workflow.add_node("identify_themes", self._identify_themes)
        workflow.add_node("create_summary", self._create_summary)
        workflow.add_node("compile_analysis", self._compile_analysis)

        # Linear flow (could be parallelized in future)
        workflow.set_entry_point("extract_entities")
        workflow.add_edge("extract_entities", "identify_themes")
        workflow.add_edge("identify_themes", "create_summary")
        workflow.add_edge("create_summary", "compile_analysis")
        workflow.add_edge("compile_analysis", END)

        return workflow.compile()

    async def _extract_entities(self, state: AnalysisState) -> AnalysisState:
        """Extract entities from documents."""
        context = "\n\n".join(state["context"][:5]) if state["context"] else "No content provided"

        prompt = f"""Extract key entities from this content:

{context}

List entities in these categories:
- People (names, roles)
- Organizations
- Locations
- Dates/Times
- Key Terms"""

        response = await self.llm_service.generate(
            prompt=prompt,
            system_prompt="You are an entity extraction expert.",
            temperature=0.1,
            max_tokens=400,
        )

        state["entities"] = [response]
        state["current_step"] = "extract_entities"
        return state

    async def _identify_themes(self, state: AnalysisState) -> AnalysisState:
        """Identify main themes in the content."""
        context = "\n\n".join(state["context"][:5]) if state["context"] else "No content provided"

        prompt = f"""Identify the main themes and topics in this content:

{context}

For each theme:
1. Name the theme
2. Briefly explain its significance"""

        response = await self.llm_service.generate(
            prompt=prompt,
            system_prompt="You are a content analyst identifying themes and patterns.",
            temperature=0.2,
            max_tokens=400,
        )

        state["themes"] = [response]
        state["current_step"] = "identify_themes"
        return state

    async def _create_summary(self, state: AnalysisState) -> AnalysisState:
        """Create a summary of the content."""
        context = "\n\n".join(state["context"][:5]) if state["context"] else "No content provided"

        prompt = f"""Create a concise summary of this content:

{context}

Focus on:
- Main points
- Key conclusions
- Important details"""

        response = await self.llm_service.generate(
            prompt=prompt,
            system_prompt="You are an expert summarizer.",
            temperature=0.3,
            max_tokens=300,
        )

        state["summary"] = response
        state["current_step"] = "create_summary"
        return state

    async def _compile_analysis(self, state: AnalysisState) -> AnalysisState:
        """Compile all analysis into final output."""
        entities = "\n".join(state["entities"])
        themes = "\n".join(state["themes"])
        summary = state["summary"]
        query = state["query"]

        prompt = f"""Compile a comprehensive analysis report:

User Query: {query}

## Entities Found:
{entities}

## Themes Identified:
{themes}

## Summary:
{summary}

Create a well-structured analysis report addressing the user's query."""

        response = await self.llm_service.generate(
            prompt=prompt,
            system_prompt="You compile analysis reports from multiple sources.",
            temperature=0.4,
            max_tokens=800,
        )

        state["analysis"] = response
        state["current_step"] = "complete"
        return state

    async def execute(
        self,
        query: str,
        context: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute the analysis workflow."""
        await self.initialize()
        
        # Convert context string to list if needed
        context_list = context.split("\n\n") if context else []
        
        initial_state: AnalysisState = {
            "query": query,
            "context": context_list,
            "entities": [],
            "themes": [],
            "summary": "",
            "analysis": "",
            "current_step": "start",
        }

        try:
            final_state = await self.graph.ainvoke(initial_state)
            
            return {
                "result": final_state["analysis"],
                "agent": self.name,
                "framework": self.framework.value,
                "entities": final_state["entities"],
                "themes": final_state["themes"],
                "summary": final_state["summary"],
            }
        except Exception as e:
            logger.error("LangGraph analysis agent failed", error=str(e))
            return {
                "error": str(e),
                "agent": self.name,
                "framework": self.framework.value,
            }

    async def run(
        self,
        query: str,
        context: List[str] | None = None,
    ) -> Dict[str, Any]:
        """Run the analysis workflow (legacy interface)."""
        context_str = "\n\n".join(context) if context else None
        return await self.execute(query=query, context=context_str)


class LangGraphReasoningAgent:
    """LangGraph-based multi-step reasoning agent."""

    name = "langgraph_reasoning"
    description = "Reasoning agent using LangGraph for step-by-step problem solving"
    framework = AgentFramework.LANGGRAPH

    def __init__(self, llm_service: LLMService | None = None):
        """Initialize the reasoning agent."""
        self.llm_service = llm_service
        self.graph = None
        self._initialized = False

    async def initialize(self):
        """Initialize the agent asynchronously."""
        if self._initialized:
            return
        if self.llm_service is None:
            self.llm_service = get_llm_service()
        self.graph = self._build_graph()
        self._initialized = True

    def _build_graph(self) -> StateGraph:
        """Build the reasoning workflow graph."""
        workflow = StateGraph(MultiStepState)

        workflow.add_node("decompose", self._decompose_problem)
        workflow.add_node("reason_step", self._reason_step)
        workflow.add_node("synthesize_answer", self._synthesize_answer)

        workflow.set_entry_point("decompose")
        workflow.add_edge("decompose", "reason_step")
        workflow.add_conditional_edges(
            "reason_step",
            self._has_more_steps,
            {
                "continue": "reason_step",
                "synthesize": "synthesize_answer",
            }
        )
        workflow.add_edge("synthesize_answer", END)

        return workflow.compile()

    async def _decompose_problem(self, state: MultiStepState) -> MultiStepState:
        """Decompose the problem into steps."""
        query = state["query"]
        context_hint = f"\n\nContext available: {len(state['context'])} documents" if state["context"] else ""

        prompt = f"""Decompose this problem into logical reasoning steps:

Problem: {query}{context_hint}

List 2-4 reasoning steps needed to solve this problem.
Format each step as: "Step N: [description]"
"""

        response = await self.llm_service.generate(
            prompt=prompt,
            system_prompt="You are a logical reasoning expert who breaks down complex problems.",
            temperature=0.2,
            max_tokens=300,
        )

        # Parse steps (simple parsing)
        lines = response.strip().split("\n")
        steps = []
        for line in lines:
            if line.strip().lower().startswith("step"):
                steps.append({"description": line, "result": ""})

        if not steps:
            steps = [{"description": "Step 1: Analyze and answer directly", "result": ""}]

        state["steps"] = steps
        state["current_step"] = 0
        return state

    async def _reason_step(self, state: MultiStepState) -> MultiStepState:
        """Execute one reasoning step."""
        current_idx = state["current_step"]
        if current_idx >= len(state["steps"]):
            return state

        step = state["steps"][current_idx]
        context_text = "\n".join(state["context"][:3]) if state["context"] else "No specific context"
        previous_reasoning = "\n".join(state["reasoning_chain"])

        prompt = f"""Execute this reasoning step:

Problem: {state['query']}

{step['description']}

Previous reasoning:
{previous_reasoning if previous_reasoning else "Starting fresh"}

Relevant context:
{context_text}

Provide your reasoning for this step:"""

        response = await self.llm_service.generate(
            prompt=prompt,
            system_prompt="You are executing step-by-step reasoning.",
            temperature=0.3,
            max_tokens=400,
        )

        state["steps"][current_idx]["result"] = response
        state["reasoning_chain"].append(f"{step['description']}\nResult: {response}")
        state["current_step"] = current_idx + 1
        return state

    def _has_more_steps(self, state: MultiStepState) -> str:
        """Check if there are more steps to process."""
        if state["current_step"] < len(state["steps"]):
            return "continue"
        return "synthesize"

    async def _synthesize_answer(self, state: MultiStepState) -> MultiStepState:
        """Synthesize final answer from reasoning chain."""
        reasoning = "\n\n".join(state["reasoning_chain"])

        prompt = f"""Based on this step-by-step reasoning, provide a final answer:

Problem: {state['query']}

Reasoning Process:
{reasoning}

Final Answer:"""

        response = await self.llm_service.generate(
            prompt=prompt,
            system_prompt="You synthesize final answers from step-by-step reasoning.",
            temperature=0.4,
            max_tokens=500,
        )

        state["final_answer"] = response
        return state

    async def execute(
        self,
        query: str,
        context: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute the reasoning workflow."""
        await self.initialize()
        
        # Convert context string to list if needed
        context_list = context.split("\n\n") if context else []
        
        initial_state: MultiStepState = {
            "query": query,
            "context": context_list,
            "steps": [],
            "current_step": 0,
            "final_answer": "",
            "reasoning_chain": [],
        }

        try:
            final_state = await self.graph.ainvoke(initial_state)
            
            return {
                "result": final_state["final_answer"],
                "agent": self.name,
                "framework": self.framework.value,
                "steps": final_state["steps"],
                "reasoning_trace": "\n\n".join(final_state["reasoning_chain"]),
            }
        except Exception as e:
            logger.error("LangGraph reasoning agent failed", error=str(e))
            return {
                "error": str(e),
                "agent": self.name,
                "framework": self.framework.value,
            }

    async def run(
        self,
        query: str,
        context: List[str] | None = None,
    ) -> Dict[str, Any]:
        """Run the reasoning workflow (legacy interface)."""
        context_str = "\n\n".join(context) if context else None
        return await self.execute(query=query, context=context_str)


# Factory function to get LangGraph agents
def get_langgraph_agent(agent_type: str, llm_service: LLMService | None = None):
    """Get a LangGraph agent by type.
    
    Args:
        agent_type: Type of agent (research, analysis, reasoning)
        llm_service: Optional LLM service instance
        
    Returns:
        The requested LangGraph agent instance
    """
    agents = {
        "research": LangGraphResearchAgent,
        "analysis": LangGraphAnalysisAgent,
        "reasoning": LangGraphReasoningAgent,
    }
    
    if agent_type not in agents:
        raise ValueError(f"Unknown LangGraph agent type: {agent_type}")
    
    return agents[agent_type](llm_service=llm_service)


def list_langgraph_agents() -> List[Dict[str, Any]]:
    """List all available LangGraph agents."""
    return [
        {
            "name": "lg_research",
            "type": "research",
            "description": "Research agent using LangGraph for iterative document research",
            "framework": "langgraph",
            "workflow_type": "iterative_refinement",
        },
        {
            "name": "lg_analysis",
            "type": "analysis",
            "description": "Analysis agent using LangGraph for structured document analysis",
            "framework": "langgraph",
            "workflow_type": "pipeline",
        },
        {
            "name": "lg_reasoning",
            "type": "reasoning",
            "description": "Reasoning agent using LangGraph for step-by-step problem solving",
            "framework": "langgraph",
            "workflow_type": "chain_of_thought",
        },
    ]