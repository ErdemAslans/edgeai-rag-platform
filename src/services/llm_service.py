"""LLM service for interacting with language models (Groq/Ollama)."""

import asyncio
from typing import List, Dict, Any, AsyncGenerator
from enum import Enum

import structlog

from src.config import settings

logger = structlog.get_logger()


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    GROQ = "groq"
    OLLAMA = "ollama"


class LLMService:
    """Service for interacting with LLM providers (Groq or Ollama)."""

    def __init__(self, provider: LLMProvider | None = None):
        """Initialize the LLM service.

        Args:
            provider: The LLM provider to use. Defaults to settings configuration.
        """
        self.provider = provider or LLMProvider(settings.LLM_PROVIDER)
        self._client = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize the appropriate LLM client."""
        if self.provider == LLMProvider.GROQ:
            self._initialize_groq()
        elif self.provider == LLMProvider.OLLAMA:
            self._initialize_ollama()
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def _initialize_groq(self) -> None:
        """Initialize Groq client."""
        try:
            from groq import Groq, AsyncGroq

            if not settings.GROQ_API_KEY:
                logger.warning("GROQ_API_KEY not set, Groq client not initialized")
                return

            self._client = AsyncGroq(api_key=settings.GROQ_API_KEY)
            self._sync_client = Groq(api_key=settings.GROQ_API_KEY)
            self.model = settings.GROQ_MODEL
            logger.info("Groq client initialized", model=self.model)
        except ImportError:
            logger.error("groq library not installed")
            raise ImportError(
                "groq library required. Install with: pip install groq"
            )

    def _initialize_ollama(self) -> None:
        """Initialize Ollama client."""
        try:
            import ollama

            self._client = ollama
            self.model = settings.OLLAMA_MODEL
            self.base_url = settings.OLLAMA_BASE_URL
            logger.info(
                "Ollama client initialized",
                model=self.model,
                base_url=self.base_url,
            )
        except ImportError:
            logger.error("ollama library not installed")
            raise ImportError(
                "ollama library required. Install with: pip install ollama"
            )

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Generate a response from the LLM.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt for context.
            temperature: Sampling temperature (0-1).
            max_tokens: Maximum tokens in response.

        Returns:
            The generated text response.
        """
        if self.provider == LLMProvider.GROQ:
            return await self._generate_groq(
                prompt, system_prompt, temperature, max_tokens
            )
        elif self.provider == LLMProvider.OLLAMA:
            return await self._generate_ollama(
                prompt, system_prompt, temperature, max_tokens
            )
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    async def _generate_groq(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Generate response using Groq API.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens.

        Returns:
            Generated text.
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error("Groq API error", error=str(e))
            raise

    async def _generate_ollama(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Generate response using Ollama API.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens.

        Returns:
            Generated text.
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            # Run in executor since ollama library is synchronous
            response = await asyncio.to_thread(
                lambda: self._client.chat(
                    model=self.model,
                    messages=messages,
                    options={
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                ),
            )
            return response["message"]["content"]
        except Exception as e:
            logger.error("Ollama API error", error=str(e))
            raise

    async def generate_with_context(
        self,
        query: str,
        context: List[str],
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> str:
        """Generate a response using RAG context.

        Args:
            query: The user query.
            context: List of context passages from vector search.
            system_prompt: Optional system prompt override.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens.

        Returns:
            Generated response incorporating context.
        """
        if not system_prompt:
            system_prompt = """You are a helpful AI assistant. Use the provided context to answer the user's question accurately. 
If the context doesn't contain relevant information, say so and provide what help you can.
Always cite which parts of the context you used in your answer."""

        context_text = "\n\n---\n\n".join(
            f"Context {i+1}:\n{ctx}" for i, ctx in enumerate(context)
        )

        prompt = f"""Context information:
{context_text}

User Question: {query}

Please provide a helpful answer based on the context above."""

        return await self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        """Stream a response from the LLM.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens.

        Yields:
            Generated text chunks.
        """
        if self.provider == LLMProvider.GROQ:
            async for chunk in self._stream_groq(
                prompt, system_prompt, temperature, max_tokens
            ):
                yield chunk
        elif self.provider == LLMProvider.OLLAMA:
            async for chunk in self._stream_ollama(
                prompt, system_prompt, temperature, max_tokens
            ):
                yield chunk

    async def _stream_groq(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        max_tokens: int,
    ) -> AsyncGenerator[str, None]:
        """Stream response using Groq API."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            stream = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error("Groq streaming error", error=str(e))
            raise

    async def _stream_ollama(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        max_tokens: int,
    ) -> AsyncGenerator[str, None]:
        """Stream response using Ollama API."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            # Ollama streaming needs special handling
            def stream_sync():
                return self._client.chat(
                    model=self.model,
                    messages=messages,
                    options={
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                    stream=True,
                )

            stream = await asyncio.to_thread(stream_sync)
            for chunk in stream:
                if "message" in chunk and "content" in chunk["message"]:
                    yield chunk["message"]["content"]
        except Exception as e:
            logger.error("Ollama streaming error", error=str(e))
            raise

    def get_provider(self) -> str:
        """Get the current LLM provider name.

        Returns:
            The provider name.
        """
        return self.provider.value

    def get_model(self) -> str:
        """Get the current model name.

        Returns:
            The model name.
        """
        return self.model


def get_llm_service(provider: LLMProvider | None = None) -> LLMService:
    """Get an LLM service instance.

    Args:
        provider: Optional provider override.

    Returns:
        LLM service instance.
    """
    return LLMService(provider=provider)