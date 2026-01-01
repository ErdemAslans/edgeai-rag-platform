"""
CrewAI-based agents for multi-agent collaboration.

CrewAI enables multiple AI agents to work together, each with specialized roles,
to accomplish complex tasks through collaboration.
"""
import asyncio
from typing import Any, Dict, List, Optional
from enum import Enum
import json

try:
    from crewai import Agent, Task, Crew, Process
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False
    # Create dummy classes for type hints
    Agent = Any
    Task = Any
    Crew = Any
    Process = Any

from src.services.llm_service import LLMService, get_llm_service


class CrewRole(str, Enum):
    """Roles for CrewAI agents."""
    RESEARCHER = "researcher"
    ANALYST = "analyst"
    WRITER = "writer"
    CRITIC = "critic"
    COORDINATOR = "coordinator"


class CrewAIAgentWrapper:
    """
    Wrapper for CrewAI agents to integrate with our system.
    
    This provides a unified interface for CrewAI-based multi-agent
    collaboration within our RAG platform.
    """
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm_service = llm_service
        self._agents: Dict[str, Agent] = {}
        self._crews: Dict[str, Crew] = {}
        
    async def initialize(self):
        """Initialize the CrewAI wrapper with LLM service."""
        if self.llm_service is None:
            self.llm_service = get_llm_service()
    
    def _get_llm_config(self) -> Dict[str, Any]:
        """Get LLM configuration for CrewAI agents."""
        # CrewAI uses its own LLM configuration
        # We'll use environment variables or pass config
        return {
            "model": "groq/llama-3.3-70b-versatile",
            "temperature": 0.7
        }


class CrewAIResearchCrew:
    """
    A research crew with multiple agents working together.
    
    Agents:
    - Researcher: Finds and gathers information
    - Analyst: Analyzes the gathered information
    - Writer: Synthesizes findings into a coherent report
    """
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm_service = llm_service
        self.framework = "crewai"
        self.name = "research_crew"
        
    async def initialize(self):
        """Initialize the research crew."""
        if self.llm_service is None:
            self.llm_service = get_llm_service()
    
    async def execute(
        self,
        query: str,
        context: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute research task with the crew.

        Since CrewAI may not be fully available or configured,
        we implement a fallback using our LLM service.
        """
        await self.initialize()
        assert self.llm_service is not None

        if CREWAI_AVAILABLE:
            try:
                return await self._execute_with_crewai(query, context, **kwargs)
            except Exception as e:
                # Fallback to simulated crew
                return await self._execute_simulated(query, context, str(e), **kwargs)
        else:
            return await self._execute_simulated(query, context, "CrewAI not installed", **kwargs)
    
    async def _execute_with_crewai(
        self,
        query: str,
        context: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute using actual CrewAI framework."""
        # Create agents
        researcher = Agent(
            role="Senior Research Analyst",
            goal=f"Find comprehensive information about: {query}",
            backstory="""You are a seasoned research analyst with expertise in 
            gathering and synthesizing information from various sources. You have 
            a keen eye for detail and always verify your findings.""",
            verbose=True,
            allow_delegation=False
        )
        
        analyst = Agent(
            role="Data Analyst",
            goal="Analyze research findings and identify key insights",
            backstory="""You are an expert data analyst who excels at finding 
            patterns, connections, and insights in complex information. You 
            provide clear, actionable analysis.""",
            verbose=True,
            allow_delegation=False
        )
        
        writer = Agent(
            role="Technical Writer",
            goal="Create clear, comprehensive reports from research and analysis",
            backstory="""You are a skilled technical writer who transforms 
            complex findings into clear, well-structured reports. You ensure 
            all key points are communicated effectively.""",
            verbose=True,
            allow_delegation=False
        )
        
        # Create tasks
        research_task = Task(
            description=f"""Research the following topic thoroughly:
            
            Query: {query}
            
            {"Context: " + context if context else ""}
            
            Gather all relevant information, facts, and perspectives.
            Focus on accuracy and comprehensiveness.""",
            expected_output="Detailed research findings with sources",
            agent=researcher
        )
        
        analysis_task = Task(
            description="""Analyze the research findings:
            
            1. Identify key themes and patterns
            2. Note any contradictions or gaps
            3. Highlight the most important insights
            4. Provide recommendations based on findings""",
            expected_output="Structured analysis with key insights",
            agent=analyst
        )
        
        writing_task = Task(
            description="""Create a comprehensive report:
            
            1. Executive summary
            2. Key findings
            3. Detailed analysis
            4. Conclusions and recommendations
            
            Make it clear, professional, and actionable.""",
            expected_output="Final research report",
            agent=writer
        )
        
        # Create and run crew
        crew = Crew(
            agents=[researcher, analyst, writer],
            tasks=[research_task, analysis_task, writing_task],
            process=Process.sequential,
            verbose=True
        )
        
        # Run in executor since CrewAI is synchronous
        result = await asyncio.to_thread(crew.kickoff)
        
        return {
            "result": str(result),
            "agent": self.name,
            "framework": self.framework,
            "crew_size": 3,
            "process": "sequential"
        }
    
    async def _execute_simulated(
        self,
        query: str,
        context: Optional[str] = None,
        fallback_reason: str = "",
        **kwargs
    ) -> Dict[str, Any]:
        """Simulated crew execution using LLM service."""
        
        # Phase 1: Research
        research_prompt = f"""You are a Senior Research Analyst. Your task is to research:

Query: {query}

{"Context: " + context if context else ""}

Provide comprehensive research findings including:
1. Key facts and information
2. Different perspectives
3. Relevant data points
4. Source considerations

Be thorough and accurate."""

        research_result = await self.llm_service.generate(
            prompt=research_prompt,
            system_prompt="You are an expert research analyst gathering information."
        )
        
        # Phase 2: Analysis
        analysis_prompt = f"""You are a Data Analyst. Analyze these research findings:

Research Findings:
{research_result}

Provide:
1. Key themes and patterns
2. Important insights
3. Gaps or contradictions
4. Recommendations"""

        analysis_result = await self.llm_service.generate(
            prompt=analysis_prompt,
            system_prompt="You are an expert data analyst identifying insights."
        )
        
        # Phase 3: Report Writing
        writing_prompt = f"""You are a Technical Writer. Create a report from:

Research:
{research_result}

Analysis:
{analysis_result}

Create a clear, professional report with:
1. Executive Summary
2. Key Findings
3. Analysis
4. Conclusions"""

        final_report = await self.llm_service.generate(
            prompt=writing_prompt,
            system_prompt="You are an expert technical writer creating clear reports."
        )
        
        return {
            "result": final_report,
            "agent": self.name,
            "framework": self.framework,
            "crew_size": 3,
            "process": "sequential",
            "simulated": True,
            "fallback_reason": fallback_reason,
            "phases": {
                "research": research_result[:500] + "..." if len(research_result) > 500 else research_result,
                "analysis": analysis_result[:500] + "..." if len(analysis_result) > 500 else analysis_result
            }
        }


class CrewAIQACrew:
    """
    A QA crew for question answering with fact-checking.
    
    Agents:
    - Answerer: Provides initial answers
    - Fact Checker: Verifies the accuracy of answers
    - Refiner: Improves and finalizes the answer
    """
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm_service = llm_service
        self.framework = "crewai"
        self.name = "qa_crew"
        
    async def initialize(self):
        """Initialize the QA crew."""
        if self.llm_service is None:
            self.llm_service = get_llm_service()
    
    async def execute(
        self,
        question: str,
        context: Optional[str] = None,
        sources: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute QA task with the crew."""
        await self.initialize()
        assert self.llm_service is not None

        # Build context from sources if provided
        full_context = context or ""
        if sources:
            source_text = "\n\n".join([
                f"Source {i+1}: {s.get('content', '')}"
                for i, s in enumerate(sources)
            ])
            full_context = f"{full_context}\n\nReference Sources:\n{source_text}"
        
        # Phase 1: Initial Answer
        answer_prompt = f"""You are an expert at answering questions accurately.

Question: {question}

{"Context: " + full_context if full_context else ""}

Provide a comprehensive answer based on the available information.
If you're unsure about something, indicate your confidence level."""

        initial_answer = await self.llm_service.generate(
            prompt=answer_prompt,
            system_prompt="You are an expert question answerer providing accurate responses."
        )
        
        # Phase 2: Fact Checking
        fact_check_prompt = f"""You are a meticulous fact checker.

Question: {question}
Answer to verify: {initial_answer}

{"Available context: " + full_context if full_context else ""}

Check the answer for:
1. Factual accuracy
2. Completeness
3. Potential errors or misleading statements
4. Areas needing clarification

Provide your fact-check report."""

        fact_check = await self.llm_service.generate(
            prompt=fact_check_prompt,
            system_prompt="You are an expert fact checker ensuring accuracy."
        )
        
        # Phase 3: Refinement
        refine_prompt = f"""You are an expert at refining and improving answers.

Original Question: {question}
Initial Answer: {initial_answer}
Fact Check Results: {fact_check}

Create a refined, final answer that:
1. Incorporates fact-check feedback
2. Is clear and accurate
3. Addresses any identified issues
4. Is well-structured and helpful"""

        final_answer = await self.llm_service.generate(
            prompt=refine_prompt,
            system_prompt="You are an expert at creating polished, accurate responses."
        )
        
        return {
            "result": final_answer,
            "agent": self.name,
            "framework": self.framework,
            "crew_size": 3,
            "process": "sequential",
            "phases": {
                "initial_answer": initial_answer[:300] + "..." if len(initial_answer) > 300 else initial_answer,
                "fact_check": fact_check[:300] + "..." if len(fact_check) > 300 else fact_check
            }
        }


class CrewAICodeReviewCrew:
    """
    A code review crew for analyzing and improving code.
    
    Agents:
    - Code Analyzer: Analyzes code structure and patterns
    - Security Reviewer: Checks for security issues
    - Optimizer: Suggests performance improvements
    """
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm_service = llm_service
        self.framework = "crewai"
        self.name = "code_review_crew"
        
    async def initialize(self):
        """Initialize the code review crew."""
        if self.llm_service is None:
            self.llm_service = get_llm_service()
    
    async def execute(
        self,
        code: str,
        language: str = "python",
        focus: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute code review with the crew."""
        await self.initialize()
        assert self.llm_service is not None

        # Phase 1: Code Analysis
        analysis_prompt = f"""You are an expert code analyst reviewing {language} code.

Code to review:
```{language}
{code}
```

{"Focus area: " + focus if focus else ""}

Analyze:
1. Code structure and organization
2. Design patterns used
3. Code quality and readability
4. Potential bugs or issues
5. Best practices adherence"""

        analysis = await self.llm_service.generate(
            prompt=analysis_prompt,
            system_prompt=f"You are an expert {language} code analyst."
        )
        
        # Phase 2: Security Review
        security_prompt = f"""You are a security expert reviewing code.

Code:
```{language}
{code}
```

Previous Analysis:
{analysis}

Check for:
1. Security vulnerabilities
2. Input validation issues
3. Data exposure risks
4. Authentication/authorization problems
5. Injection vulnerabilities"""

        security = await self.llm_service.generate(
            prompt=security_prompt,
            system_prompt="You are a security expert identifying vulnerabilities."
        )
        
        # Phase 3: Optimization
        optimize_prompt = f"""You are a performance optimization expert.

Code:
```{language}
{code}
```

Analysis: {analysis}
Security Review: {security}

Suggest:
1. Performance improvements
2. Memory optimizations
3. Algorithm improvements
4. Code simplifications
5. Final recommendations

Provide actionable suggestions with code examples where helpful."""

        optimization = await self.llm_service.generate(
            prompt=optimize_prompt,
            system_prompt="You are an expert at code optimization."
        )
        
        # Compile final report
        report_prompt = f"""Compile a final code review report:

Code Analysis:
{analysis}

Security Review:
{security}

Optimization Suggestions:
{optimization}

Create a structured report with:
1. Executive Summary
2. Key Issues Found
3. Security Concerns
4. Recommended Improvements
5. Priority Actions"""

        final_report = await self.llm_service.generate(
            prompt=report_prompt,
            system_prompt="Create a clear, actionable code review report."
        )
        
        return {
            "result": final_report,
            "agent": self.name,
            "framework": self.framework,
            "crew_size": 3,
            "language": language,
            "sections": {
                "analysis": analysis,
                "security": security,
                "optimization": optimization
            }
        }


# Factory function to get CrewAI agents
_crewai_agents: Dict[str, Any] = {}
_crewai_lock = asyncio.Lock()

async def get_crewai_agent(agent_type: str) -> Any:
    """
    Get a CrewAI agent by type.
    
    Args:
        agent_type: Type of crew to get (research, qa, code_review)
        
    Returns:
        The requested CrewAI agent/crew
    """
    global _crewai_agents
    
    # Fast path - already initialized
    if agent_type in _crewai_agents:
        return _crewai_agents[agent_type]
    
    # Thread-safe initialization with double-check pattern
    async with _crewai_lock:
        # Double-check after acquiring lock
        if agent_type not in _crewai_agents:
            if agent_type == "research":
                agent = CrewAIResearchCrew()
            elif agent_type == "qa":
                agent = CrewAIQACrew()
            elif agent_type == "code_review":
                agent = CrewAICodeReviewCrew()
            else:
                raise ValueError(f"Unknown CrewAI agent type: {agent_type}")
            
            await agent.initialize()
            _crewai_agents[agent_type] = agent
    
    return _crewai_agents[agent_type]


# List available CrewAI agents
def list_crewai_agents() -> List[Dict[str, Any]]:
    """List all available CrewAI agents."""
    return [
        {
            "name": "research_crew",
            "type": "research",
            "description": "Multi-agent research crew with researcher, analyst, and writer",
            "framework": "crewai",
            "agents": ["researcher", "analyst", "writer"]
        },
        {
            "name": "qa_crew",
            "type": "qa",
            "description": "Question-answering crew with fact-checking capabilities",
            "framework": "crewai",
            "agents": ["answerer", "fact_checker", "refiner"]
        },
        {
            "name": "code_review_crew",
            "type": "code_review",
            "description": "Code review crew for analysis, security, and optimization",
            "framework": "crewai",
            "agents": ["analyzer", "security_reviewer", "optimizer"]
        }
    ]