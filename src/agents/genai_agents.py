"""
GenAI (Custom) agents for the EdgeAI RAG Platform.

These are custom-built AI agents using direct LLM calls,
providing specialized functionality without external frameworks.
"""
import asyncio
from typing import Any, Dict, List, Optional
from enum import Enum
import json
import time

from src.services.llm_service import LLMService, get_llm_service
from src.agents.base import BaseAgent


class GenAIAgentType(str, Enum):
    """Types of GenAI agents."""
    CONVERSATIONAL = "conversational"
    TASK_EXECUTOR = "task_executor"
    KNOWLEDGE_BASE = "knowledge_base"
    REASONING = "reasoning"
    CREATIVE = "creative"


class GenAIConversationalAgent:
    """
    A conversational agent for natural dialogue.
    
    Maintains conversation context and provides helpful,
    contextually-aware responses.
    """
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm_service = llm_service
        self.framework = "genai"
        self.name = "conversational_agent"
        self.conversation_history: List[Dict[str, str]] = []
        self.max_history = 10
        
    async def initialize(self):
        """Initialize the agent."""
        if self.llm_service is None:
            self.llm_service = await get_llm_service()
    
    async def execute(
        self,
        message: str,
        context: Optional[str] = None,
        reset_history: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute a conversational turn."""
        await self.initialize()
        start_time = time.time()
        
        if reset_history:
            self.conversation_history = []
        
        # Build conversation context
        history_text = ""
        if self.conversation_history:
            history_text = "\n".join([
                f"{'User' if h['role'] == 'user' else 'Assistant'}: {h['content']}"
                for h in self.conversation_history[-self.max_history:]
            ])
        
        prompt = f"""You are a helpful conversational AI assistant.

{f"Previous conversation:{chr(10)}{history_text}{chr(10)}" if history_text else ""}
{f"Additional context: {context}{chr(10)}" if context else ""}
User: {message}

Provide a helpful, natural response. Be concise but thorough."""

        response = await self.llm_service.generate(
            prompt=prompt,
            system_prompt="You are a helpful, friendly AI assistant engaged in natural conversation."
        )
        
        # Update history
        self.conversation_history.append({"role": "user", "content": message})
        self.conversation_history.append({"role": "assistant", "content": response})
        
        execution_time = time.time() - start_time
        
        return {
            "result": response,
            "agent": self.name,
            "framework": self.framework,
            "execution_time": execution_time,
            "history_length": len(self.conversation_history)
        }
    
    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []


class GenAITaskExecutorAgent:
    """
    A task execution agent that breaks down and executes complex tasks.
    
    Capable of:
    - Task decomposition
    - Step-by-step execution
    - Progress tracking
    - Error handling
    """
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm_service = llm_service
        self.framework = "genai"
        self.name = "task_executor_agent"
        
    async def initialize(self):
        """Initialize the agent."""
        if self.llm_service is None:
            self.llm_service = await get_llm_service()
    
    async def execute(
        self,
        task: str,
        context: Optional[str] = None,
        max_steps: int = 5,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute a complex task with step-by-step approach."""
        await self.initialize()
        start_time = time.time()
        
        # Step 1: Task Analysis
        analysis_prompt = f"""Analyze this task and break it down into clear steps:

Task: {task}

{f"Context: {context}" if context else ""}

Provide:
1. Task understanding
2. Required steps (max {max_steps})
3. Expected outcome
4. Potential challenges

Format as a structured analysis."""

        analysis = await self.llm_service.generate(
            prompt=analysis_prompt,
            system_prompt="You are an expert at task analysis and planning."
        )
        
        # Step 2: Extract steps from analysis
        steps_prompt = f"""Based on this task analysis, list the specific execution steps:

Task: {task}
Analysis: {analysis}

List exactly the steps needed, one per line, in execution order.
Keep each step clear and actionable."""

        steps_text = await self.llm_service.generate(
            prompt=steps_prompt,
            system_prompt="Extract clear, actionable steps."
        )
        
        # Step 3: Execute each step (simulated)
        execution_results = []
        steps = [s.strip() for s in steps_text.split('\n') if s.strip() and not s.strip().startswith('#')][:max_steps]
        
        for i, step in enumerate(steps):
            step_prompt = f"""Execute this step of the task:

Overall Task: {task}
Current Step ({i+1}/{len(steps)}): {step}

Previous Results:
{chr(10).join([f"Step {j+1}: {r['summary']}" for j, r in enumerate(execution_results)]) if execution_results else "No previous steps"}

Provide the result of executing this step."""

            step_result = await self.llm_service.generate(
                prompt=step_prompt,
                system_prompt="Execute the given step and provide results."
            )
            
            execution_results.append({
                "step": i + 1,
                "description": step,
                "result": step_result,
                "summary": step_result[:100] + "..." if len(step_result) > 100 else step_result
            })
        
        # Step 4: Compile final result
        compile_prompt = f"""Compile the final result for this task:

Task: {task}

Execution Results:
{chr(10).join([f"Step {r['step']}: {r['description']}{chr(10)}Result: {r['result']}" for r in execution_results])}

Provide a comprehensive final result that summarizes the task completion."""

        final_result = await self.llm_service.generate(
            prompt=compile_prompt,
            system_prompt="Compile a clear, comprehensive task completion report."
        )
        
        execution_time = time.time() - start_time
        
        return {
            "result": final_result,
            "agent": self.name,
            "framework": self.framework,
            "execution_time": execution_time,
            "steps_executed": len(execution_results),
            "analysis": analysis[:500] + "..." if len(analysis) > 500 else analysis,
            "execution_details": execution_results
        }


class GenAIKnowledgeAgent:
    """
    A knowledge-base agent for RAG-enhanced Q&A.
    
    Integrates with vector search to provide accurate,
    source-backed answers.
    """
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm_service = llm_service
        self.framework = "genai"
        self.name = "knowledge_agent"
        
    async def initialize(self):
        """Initialize the agent."""
        if self.llm_service is None:
            self.llm_service = await get_llm_service()
    
    async def execute(
        self,
        question: str,
        sources: Optional[List[Dict[str, Any]]] = None,
        require_sources: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """Answer questions using knowledge base sources."""
        await self.initialize()
        start_time = time.time()
        
        # Build context from sources
        source_context = ""
        source_references = []
        
        if sources:
            for i, source in enumerate(sources):
                content = source.get('content', '')
                doc_name = source.get('document_name', f'Source {i+1}')
                source_context += f"\n[Source {i+1}: {doc_name}]\n{content}\n"
                source_references.append({
                    "id": i + 1,
                    "name": doc_name,
                    "relevance": source.get('similarity', 0)
                })
        
        if require_sources and not sources:
            return {
                "result": "I need access to knowledge base sources to answer this question accurately. Please ensure documents are uploaded and indexed.",
                "agent": self.name,
                "framework": self.framework,
                "execution_time": time.time() - start_time,
                "sources_used": 0,
                "confidence": 0.0
            }
        
        # Generate answer
        if source_context:
            prompt = f"""Answer this question using ONLY the provided sources.

Question: {question}

Sources:
{source_context}

Instructions:
1. Base your answer strictly on the provided sources
2. Cite sources using [Source N] format
3. If sources don't contain the answer, say so
4. Be accurate and concise"""

            system_prompt = "You are a knowledge assistant that provides accurate answers based on provided sources."
        else:
            prompt = f"""Answer this question to the best of your ability:

Question: {question}

Note: No specific sources were provided, so answer based on general knowledge.
Be clear about the limitations of this response."""

            system_prompt = "You are a helpful assistant answering questions based on general knowledge."
        
        answer = await self.llm_service.generate(
            prompt=prompt,
            system_prompt=system_prompt
        )
        
        # Assess confidence
        confidence_prompt = f"""Rate your confidence in this answer from 0.0 to 1.0:

Question: {question}
Answer: {answer}
Sources Available: {len(sources) if sources else 0}

Just respond with a number between 0.0 and 1.0"""

        try:
            confidence_text = await self.llm_service.generate(
                prompt=confidence_prompt,
                system_prompt="Provide only a confidence score."
            )
            confidence = float(confidence_text.strip())
            confidence = max(0.0, min(1.0, confidence))
        except (ValueError, TypeError):
            confidence = 0.7 if sources else 0.5
        
        execution_time = time.time() - start_time
        
        return {
            "result": answer,
            "agent": self.name,
            "framework": self.framework,
            "execution_time": execution_time,
            "sources_used": len(sources) if sources else 0,
            "source_references": source_references,
            "confidence": confidence
        }


class GenAIReasoningAgent:
    """
    A reasoning agent for complex problem-solving.
    
    Uses chain-of-thought reasoning to solve problems
    step by step with explicit reasoning traces.
    """
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm_service = llm_service
        self.framework = "genai"
        self.name = "reasoning_agent"
        
    async def initialize(self):
        """Initialize the agent."""
        if self.llm_service is None:
            self.llm_service = await get_llm_service()
    
    async def execute(
        self,
        problem: str,
        context: Optional[str] = None,
        reasoning_depth: str = "standard",  # "quick", "standard", "deep"
        **kwargs
    ) -> Dict[str, Any]:
        """Solve a problem with explicit reasoning."""
        await self.initialize()
        start_time = time.time()
        
        depth_instructions = {
            "quick": "Provide brief reasoning with key steps only.",
            "standard": "Show clear step-by-step reasoning.",
            "deep": "Provide exhaustive reasoning, considering multiple approaches and edge cases."
        }
        
        # Step 1: Problem Understanding
        understand_prompt = f"""Analyze this problem:

Problem: {problem}

{f"Context: {context}" if context else ""}

Provide:
1. Problem restatement in your own words
2. Key information and constraints
3. What type of problem this is
4. What approach might work"""

        understanding = await self.llm_service.generate(
            prompt=understand_prompt,
            system_prompt="You are an expert at problem analysis."
        )
        
        # Step 2: Reasoning
        reasoning_prompt = f"""Solve this problem with explicit reasoning:

Problem: {problem}
Understanding: {understanding}

{depth_instructions.get(reasoning_depth, depth_instructions['standard'])}

Show your reasoning process:
- State each step clearly
- Explain why each step follows
- Note any assumptions
- Consider alternatives if relevant"""

        reasoning = await self.llm_service.generate(
            prompt=reasoning_prompt,
            system_prompt="You are an expert problem solver showing clear reasoning."
        )
        
        # Step 3: Solution
        solution_prompt = f"""Provide the final solution:

Problem: {problem}
Reasoning: {reasoning}

Give:
1. Clear final answer
2. Confidence level (high/medium/low)
3. Any caveats or limitations"""

        solution = await self.llm_service.generate(
            prompt=solution_prompt,
            system_prompt="Provide a clear, well-justified solution."
        )
        
        execution_time = time.time() - start_time
        
        return {
            "result": solution,
            "agent": self.name,
            "framework": self.framework,
            "execution_time": execution_time,
            "reasoning_depth": reasoning_depth,
            "understanding": understanding,
            "reasoning_trace": reasoning
        }


class GenAICreativeAgent:
    """
    A creative agent for content generation.
    
    Generates creative content like stories, ideas,
    marketing copy, etc.
    """
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm_service = llm_service
        self.framework = "genai"
        self.name = "creative_agent"
        
    async def initialize(self):
        """Initialize the agent."""
        if self.llm_service is None:
            self.llm_service = await get_llm_service()
    
    async def execute(
        self,
        prompt: str,
        creative_type: str = "general",  # "story", "ideas", "copy", "general"
        style: Optional[str] = None,
        constraints: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate creative content."""
        await self.initialize()
        start_time = time.time()
        
        type_instructions = {
            "story": "Create an engaging narrative with vivid descriptions and compelling characters.",
            "ideas": "Generate innovative, diverse ideas. Think outside the box.",
            "copy": "Write persuasive, engaging marketing copy that connects with the audience.",
            "general": "Create high-quality, creative content."
        }
        
        creative_prompt = f"""Create creative content based on this prompt:

Prompt: {prompt}

Type: {creative_type}
Instructions: {type_instructions.get(creative_type, type_instructions['general'])}

{f"Style: {style}" if style else ""}
{f"Constraints: {constraints}" if constraints else ""}

Be creative, original, and engaging."""

        content = await self.llm_service.generate(
            prompt=creative_prompt,
            system_prompt=f"You are a creative {creative_type} writer with a unique voice.",
            temperature=0.9  # Higher temperature for creativity
        )
        
        # Generate variations if requested
        variations = []
        if kwargs.get('include_variations', False):
            variation_prompt = f"""Create an alternative version of this content:

Original: {content}

Make it different in tone or approach while keeping the same core message."""

            variation = await self.llm_service.generate(
                prompt=variation_prompt,
                system_prompt="Create a creative variation.",
                temperature=0.95
            )
            variations.append(variation)
        
        execution_time = time.time() - start_time
        
        return {
            "result": content,
            "agent": self.name,
            "framework": self.framework,
            "execution_time": execution_time,
            "creative_type": creative_type,
            "style": style,
            "variations": variations if variations else None
        }


# Factory function to get GenAI agents
_genai_agents: Dict[str, Any] = {}

async def get_genai_agent(agent_type: str) -> Any:
    """
    Get a GenAI agent by type.
    
    Args:
        agent_type: Type of agent (conversational, task_executor, knowledge, reasoning, creative)
        
    Returns:
        The requested GenAI agent
    """
    global _genai_agents
    
    if agent_type not in _genai_agents:
        if agent_type == "conversational":
            agent = GenAIConversationalAgent()
        elif agent_type == "task_executor":
            agent = GenAITaskExecutorAgent()
        elif agent_type == "knowledge":
            agent = GenAIKnowledgeAgent()
        elif agent_type == "reasoning":
            agent = GenAIReasoningAgent()
        elif agent_type == "creative":
            agent = GenAICreativeAgent()
        else:
            raise ValueError(f"Unknown GenAI agent type: {agent_type}")
        
        await agent.initialize()
        _genai_agents[agent_type] = agent
    
    return _genai_agents[agent_type]


# List available GenAI agents
def list_genai_agents() -> List[Dict[str, Any]]:
    """List all available GenAI agents."""
    return [
        {
            "name": "conversational_agent",
            "type": "conversational",
            "description": "Natural dialogue agent with conversation memory",
            "framework": "genai",
            "capabilities": ["multi-turn conversation", "context awareness"]
        },
        {
            "name": "task_executor_agent",
            "type": "task_executor",
            "description": "Complex task execution with step-by-step approach",
            "framework": "genai",
            "capabilities": ["task decomposition", "step execution", "progress tracking"]
        },
        {
            "name": "knowledge_agent",
            "type": "knowledge",
            "description": "RAG-enhanced Q&A with source citations",
            "framework": "genai",
            "capabilities": ["source-based answers", "citation", "confidence scoring"]
        },
        {
            "name": "reasoning_agent",
            "type": "reasoning",
            "description": "Chain-of-thought problem solving",
            "framework": "genai",
            "capabilities": ["explicit reasoning", "problem analysis", "multi-depth reasoning"]
        },
        {
            "name": "creative_agent",
            "type": "creative",
            "description": "Creative content generation",
            "framework": "genai",
            "capabilities": ["story writing", "idea generation", "copywriting", "variations"]
        }
    ]