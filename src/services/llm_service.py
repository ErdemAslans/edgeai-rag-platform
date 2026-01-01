"""LLM service for interacting with language models (Groq/Ollama)."""

import asyncio
import random
from typing import List, Dict, Any, AsyncGenerator
from enum import Enum

import structlog

from src.config import settings

logger = structlog.get_logger()


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    GROQ = "groq"
    OLLAMA = "ollama"


class RetryConfig:
    """Configuration for retry logic."""
    MAX_RETRIES = 3
    BASE_DELAY = 1.0
    MAX_DELAY = 30.0
    EXPONENTIAL_BASE = 2
    JITTER = 0.1


class TokenCounter:
    """Simple token counter for estimating token usage."""
    
    CHARS_PER_TOKEN = 4
    
    @classmethod
    def estimate_tokens(cls, text: str) -> int:
        """Estimate token count for text.
        
        Args:
            text: Text to estimate tokens for.
            
        Returns:
            Estimated token count.
        """
        if not text:
            return 0
        return len(text) // cls.CHARS_PER_TOKEN + 1
    
    @classmethod
    def estimate_message_tokens(cls, messages: List[Dict[str, str]]) -> int:
        """Estimate tokens for a list of messages.
        
        Args:
            messages: List of message dicts with role and content.
            
        Returns:
            Estimated total tokens.
        """
        total = 0
        for msg in messages:
            total += cls.estimate_tokens(msg.get("content", ""))
            total += 4
        return total
    
    @classmethod
    def fits_context(cls, text: str, max_tokens: int = 8000) -> bool:
        """Check if text fits within context window.
        
        Args:
            text: Text to check.
            max_tokens: Maximum allowed tokens.
            
        Returns:
            True if text fits.
        """
        return cls.estimate_tokens(text) <= max_tokens
    
    @classmethod
    def truncate_to_tokens(cls, text: str, max_tokens: int) -> str:
        """Truncate text to fit within token limit.
        
        Args:
            text: Text to truncate.
            max_tokens: Maximum allowed tokens.
            
        Returns:
            Truncated text.
        """
        max_chars = max_tokens * cls.CHARS_PER_TOKEN
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "..."


class LLMService:
    """Service for interacting with LLM providers (Groq or Ollama)."""

    def __init__(self, provider: LLMProvider | None = None):
        """Initialize the LLM service.

        Args:
            provider: The LLM provider to use. Defaults to settings configuration.
        """
        self.provider = provider or LLMProvider(settings.LLM_PROVIDER)
        self._client: Any = None
        self.token_counter = TokenCounter()
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

    async def _retry_with_backoff(self, func, *args, **kwargs) -> Any:
        """Execute function with exponential backoff retry.
        
        Args:
            func: Async function to execute.
            *args: Arguments for function.
            **kwargs: Keyword arguments for function.
            
        Returns:
            Function result.
            
        Raises:
            Last exception if all retries fail.
        """
        last_exception = None
        
        for attempt in range(RetryConfig.MAX_RETRIES):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if attempt == RetryConfig.MAX_RETRIES - 1:
                    logger.error(
                        "All retry attempts failed",
                        attempts=RetryConfig.MAX_RETRIES,
                        error=str(e),
                    )
                    raise
                
                delay = min(
                    RetryConfig.BASE_DELAY * (RetryConfig.EXPONENTIAL_BASE ** attempt),
                    RetryConfig.MAX_DELAY,
                )
                jitter = delay * RetryConfig.JITTER * random.random()
                delay += jitter
                
                logger.warning(
                    "LLM request failed, retrying",
                    attempt=attempt + 1,
                    delay=delay,
                    error=str(e),
                )
                
                await asyncio.sleep(delay)

        if last_exception is not None:
            raise last_exception
        raise RuntimeError("Retry failed with no exception recorded")

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Generate a response from the LLM with retry logic.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt for context.
            temperature: Sampling temperature (0-1).
            max_tokens: Maximum tokens in response.

        Returns:
            The generated text response.
        """
        if self.provider == LLMProvider.GROQ:
            return await self._retry_with_backoff(
                self._generate_groq,
                prompt, system_prompt, temperature, max_tokens
            )
        elif self.provider == LLMProvider.OLLAMA:
            return await self._retry_with_backoff(
                self._generate_ollama,
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
        """Generate response using Groq API."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    async def _generate_ollama(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Generate response using Ollama API."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

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

    async def generate_with_context(
        self,
        query: str,
        context: List[str],
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
        max_context_tokens: int = 6000,
    ) -> str:
        """Generate a response using RAG context.

        Args:
            query: The user query.
            context: List of context passages from vector search.
            system_prompt: Optional system prompt override.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens.
            max_context_tokens: Maximum tokens for context.

        Returns:
            Generated response incorporating context.
        """
        if not system_prompt:
            system_prompt = """You are a helpful AI assistant. Use the provided context to answer the user's question accurately. 
If the context doesn't contain relevant information, say so and provide what help you can.
Always cite which parts of the context you used in your answer."""

        filtered_context = []
        current_tokens = 0
        
        for ctx in context:
            ctx_tokens = self.token_counter.estimate_tokens(ctx)
            if current_tokens + ctx_tokens <= max_context_tokens:
                filtered_context.append(ctx)
                current_tokens += ctx_tokens
            else:
                break

        context_text = "\n\n---\n\n".join(
            f"Context {i+1}:\n{ctx}" for i, ctx in enumerate(filtered_context)
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
        """Get the current LLM provider name."""
        return self.provider.value

    def get_model(self) -> str:
        """Get the current model name."""
        return self.model


def get_llm_service(provider: LLMProvider | None = None) -> LLMService:
    """Get an LLM service instance.

    Args:
        provider: Optional provider override.

    Returns:
        LLM service instance.
    """
    return LLMService(provider=provider)
