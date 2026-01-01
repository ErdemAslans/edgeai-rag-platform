"""Embedding service for generating text embeddings using HuggingFace."""

import asyncio
import hashlib
from typing import List, Dict, Optional
from functools import lru_cache

import structlog

from src.core.retry import embedding_retry

logger = structlog.get_logger()


class EmbeddingCache:
    """Simple in-memory cache for embeddings."""
    
    MAX_ENTRIES = 5000
    
    def __init__(self):
        self._cache: Dict[str, List[float]] = {}
    
    def _hash_text(self, text: str) -> str:
        """Create hash key for text."""
        return hashlib.md5(text.encode()).hexdigest()
    
    def get(self, text: str) -> Optional[List[float]]:
        """Get cached embedding."""
        key = self._hash_text(text)
        return self._cache.get(key)
    
    def set(self, text: str, embedding: List[float]) -> None:
        """Cache an embedding."""
        if len(self._cache) >= self.MAX_ENTRIES:
            keys_to_remove = list(self._cache.keys())[:self.MAX_ENTRIES // 4]
            for key in keys_to_remove:
                del self._cache[key]
        
        key = self._hash_text(text)
        self._cache[key] = embedding
    
    def get_many(self, texts: List[str]) -> Dict[int, List[float]]:
        """Get cached embeddings for multiple texts.
        
        Returns dict mapping index to embedding for cached texts.
        """
        cached = {}
        for i, text in enumerate(texts):
            embedding = self.get(text)
            if embedding is not None:
                cached[i] = embedding
        return cached
    
    def set_many(self, texts: List[str], embeddings: List[List[float]]) -> None:
        """Cache multiple embeddings."""
        for text, embedding in zip(texts, embeddings):
            self.set(text, embedding)
    
    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()
    
    def size(self) -> int:
        """Get cache size."""
        return len(self._cache)


class EmbeddingService:
    """Service for generating text embeddings using HuggingFace sentence-transformers."""

    MODEL_NAME = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIMENSION = 384
    MAX_SEQUENCE_LENGTH = 512

    _instance = None
    _model = None
    _cache = None

    def __new__(cls):
        """Singleton pattern to reuse the model across requests."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._cache = EmbeddingCache()
        return cls._instance

    def __init__(self):
        """Initialize the embedding service."""
        if self._model is None:
            self._load_model()
        if self._cache is None:
            self._cache = EmbeddingCache()

    def _load_model(self) -> None:
        """Load the sentence transformer model."""
        try:
            from sentence_transformers import SentenceTransformer
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(
                "Loading embedding model",
                model_name=self.MODEL_NAME,
                device=device,
                cuda_available=torch.cuda.is_available(),
                gpu_name=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
            )
            
            self._model = SentenceTransformer(self.MODEL_NAME, device=device)
            
            logger.info(
                "Embedding model loaded successfully",
                model_name=self.MODEL_NAME,
                embedding_dimension=self.EMBEDDING_DIMENSION,
                device=self._model.device
            )
        except ImportError:
            logger.error("sentence-transformers library not installed")
            raise ImportError(
                "sentence-transformers library required. "
                "Install with: pip install sentence-transformers"
            )
        except Exception as e:
            logger.error("Failed to load embedding model", error=str(e))
            raise

    def _truncate_text(self, text: str) -> str:
        """Truncate text to max length."""
        max_chars = self.MAX_SEQUENCE_LENGTH * 4
        if len(text) > max_chars:
            return text[:max_chars]
        return text

    async def embed_text(self, text: str, use_cache: bool = True) -> List[float]:
        """Generate embedding for a single text.

        Args:
            text: The text to embed.
            use_cache: Whether to use cache.

        Returns:
            List of floats representing the embedding vector.
        """
        truncated = self._truncate_text(text)

        if use_cache:
            cached = self._cache.get(truncated)
            if cached is not None:
                return cached

        embedding = await self._embed_text_with_retry(truncated)

        if use_cache:
            self._cache.set(truncated, embedding)

        return embedding

    def _embed_text_sync(self, text: str) -> List[float]:
        """Synchronously generate embedding for a single text."""
        embedding = self._model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    @embedding_retry
    async def _embed_text_with_retry(self, text: str) -> List[float]:
        """Generate embedding with retry logic.

        This method wraps the synchronous embedding call with retry
        logic to handle transient failures.

        Args:
            text: The text to embed.

        Returns:
            List of floats representing the embedding vector.
        """
        return await asyncio.to_thread(
            self._embed_text_sync,
            text,
        )

    @embedding_retry
    async def _embed_texts_with_retry(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts with retry logic.

        This method wraps the synchronous batch embedding call with retry
        logic to handle transient failures.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors.
        """
        return await asyncio.to_thread(
            self._embed_texts_sync,
            texts,
        )

    async def embed_texts(self, texts: List[str], use_cache: bool = True) -> List[List[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed.
            use_cache: Whether to use cache.

        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []

        truncated_texts = [self._truncate_text(t) for t in texts]
        
        if use_cache:
            cached = self._cache.get_many(truncated_texts)

            if len(cached) == len(truncated_texts):
                return [cached[i] for i in range(len(truncated_texts))]

            uncached_indices = [i for i in range(len(truncated_texts)) if i not in cached]
            uncached_texts = [truncated_texts[i] for i in uncached_indices]

            if uncached_texts:
                new_embeddings = await self._embed_texts_with_retry(uncached_texts)

                self._cache.set_many(uncached_texts, new_embeddings)

                for idx, emb in zip(uncached_indices, new_embeddings):
                    cached[idx] = emb

            return [cached[i] for i in range(len(truncated_texts))]

        embeddings = await self._embed_texts_with_retry(truncated_texts)
        return embeddings

    def _embed_texts_sync(self, texts: List[str]) -> List[List[float]]:
        """Synchronously generate embeddings for multiple texts."""
        embeddings = self._model.encode(texts, convert_to_numpy=True)
        return [emb.tolist() for emb in embeddings]

    async def embed_query(self, query: str) -> List[float]:
        """Generate embedding for a search query."""
        return await self.embed_text(query, use_cache=True)

    def get_embedding_dimension(self) -> int:
        """Get the dimension of the embedding vectors."""
        return self.EMBEDDING_DIMENSION

    def get_model_name(self) -> str:
        """Get the name of the embedding model."""
        return self.MODEL_NAME
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            "size": self._cache.size(),
            "max_size": EmbeddingCache.MAX_ENTRIES,
        }
    
    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self._cache.clear()


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    """Get the singleton embedding service instance."""
    return EmbeddingService()
