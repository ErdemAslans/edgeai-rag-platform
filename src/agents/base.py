"""Base agent class for all AI agents."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
import time
import uuid

import structlog

from src.services.llm_service import LLMService, get_llm_service

logger = structlog.get_logger()


class BaseAgent(ABC):
    """Abstract base class for all AI agents."""

    # Agent metadata - override in subclasses
    name: str = "base_agent"
    description: str = "Base agent class"
    
    def __init__(
        self,
        llm_service: LLMService | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ):
        """Initialize the base agent.

        Args:
            llm_service: Optional LLM service instance.
            temperature: Sampling temperature for generation.
            max_tokens: Maximum tokens in response.
        """
        self.llm_service = llm_service or get_llm_service()
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.execution_id: str | None = None

    @abstractmethod
    async def execute(
        self,
        input_data: Dict[str, Any],
        context: List[str] | None = None,
    ) -> Dict[str, Any]:
        """Execute the agent's main task.

        Args:
            input_data: Input data for the agent.
            context: Optional context passages for RAG.

        Returns:
            Dictionary containing the agent's output.
        """
        pass

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Get the system prompt for this agent.

        Returns:
            The system prompt string.
        """
        pass

    async def run(
        self,
        input_data: Dict[str, Any],
        context: List[str] | None = None,
    ) -> Dict[str, Any]:
        """Run the agent with timing and logging.

        Args:
            input_data: Input data for the agent.
            context: Optional context passages.

        Returns:
            Dictionary containing the agent's output and metadata.
        """
        self.execution_id = str(uuid.uuid4())
        start_time = time.time()

        logger.info(
            "Agent execution started",
            agent=self.name,
            execution_id=self.execution_id,
        )

        try:
            result = await self.execute(input_data, context)
            execution_time_ms = (time.time() - start_time) * 1000

            logger.info(
                "Agent execution completed",
                agent=self.name,
                execution_id=self.execution_id,
                execution_time_ms=execution_time_ms,
            )

            return {
                "success": True,
                "agent": self.name,
                "execution_id": self.execution_id,
                "execution_time_ms": execution_time_ms,
                "result": result,
            }

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000

            logger.error(
                "Agent execution failed",
                agent=self.name,
                execution_id=self.execution_id,
                error=str(e),
                execution_time_ms=execution_time_ms,
            )

            return {
                "success": False,
                "agent": self.name,
                "execution_id": self.execution_id,
                "execution_time_ms": execution_time_ms,
                "error": str(e),
            }

    async def generate_response(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        """Generate a response using the LLM.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt override.

        Returns:
            The generated response text.
        """
        return await self.llm_service.generate(
            prompt=prompt,
            system_prompt=system_prompt or self.system_prompt,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

    async def generate_with_context(
        self,
        query: str,
        context: List[str],
        system_prompt: str | None = None,
    ) -> str:
        """Generate a response using context from RAG.

        Args:
            query: The user query.
            context: Context passages.
            system_prompt: Optional system prompt override.

        Returns:
            The generated response text.
        """
        return await self.llm_service.generate_with_context(
            query=query,
            context=context,
            system_prompt=system_prompt or self.system_prompt,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

    def get_info(self) -> Dict[str, Any]:
        """Get agent information.

        Returns:
            Dictionary with agent metadata.
        """
        return {
            "name": self.name,
            "description": self.description,
            "model": self.llm_service.get_model(),
            "provider": self.llm_service.get_provider(),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }