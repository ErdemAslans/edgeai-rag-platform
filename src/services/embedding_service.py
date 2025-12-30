"""Embedding service for generating text embeddings using HuggingFace."""

import asyncio
from typing import List
from functools import lru_cache

import structlog

logger = structlog.get_logger()


class EmbeddingService:
    """Service for generating text embeddings using HuggingFace sentence-transformers."""

    # Model configuration
    MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION = 384
    MAX_SEQUENCE_LENGTH = 256

    _instance = None
    _model = None

    def __new__(cls):
        """Singleton pattern to reuse the model across requests."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the embedding service."""
        if self._model is None:
            self._load_model()

    def _load_model(self) -> None:
        """Load the sentence transformer model."""
        try:
            from sentence_transformers import SentenceTransformer

            logger.info(
                "Loading embedding model",
                model_name=self.MODEL_NAME,
            )
            self._model = SentenceTransformer(self.MODEL_NAME)
            logger.info(
                "Embedding model loaded successfully",
                model_name=self.MODEL_NAME,
                embedding_dimension=self.EMBEDDING_DIMENSION,
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

    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text.

        Args:
            text: The text to embed.

        Returns:
            List of floats representing the embedding vector.
        """
        # Run in executor to avoid blocking the event loop
        embedding = await asyncio.to_thread(
            self._embed_text_sync,
            text,
        )
        return embedding

    def _embed_text_sync(self, text: str) -> List[float]:
        """Synchronously generate embedding for a single text.

        Args:
            text: The text to embed.

        Returns:
            List of floats representing the embedding vector.
        """
        # Truncate text if too long
        if len(text) > self.MAX_SEQUENCE_LENGTH * 4:  # Rough character estimate
            text = text[: self.MAX_SEQUENCE_LENGTH * 4]

        embedding = self._model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []

        # Run in executor to avoid blocking the event loop
        embeddings = await asyncio.to_thread(
            self._embed_texts_sync,
            texts,
        )
        return embeddings

    def _embed_texts_sync(self, texts: List[str]) -> List[List[float]]:
        """Synchronously generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors.
        """
        # Truncate texts if too long
        truncated_texts = []
        for text in texts:
            if len(text) > self.MAX_SEQUENCE_LENGTH * 4:
                text = text[: self.MAX_SEQUENCE_LENGTH * 4]
            truncated_texts.append(text)

        embeddings = self._model.encode(truncated_texts, convert_to_numpy=True)
        return [emb.tolist() for emb in embeddings]

    async def embed_query(self, query: str) -> List[float]:
        """Generate embedding for a search query.

        This is an alias for embed_text, but can be specialized for query encoding
        if the model supports different modes for queries vs documents.

        Args:
            query: The query text to embed.

        Returns:
            List of floats representing the embedding vector.
        """
        return await self.embed_text(query)

    def get_embedding_dimension(self) -> int:
        """Get the dimension of the embedding vectors.

        Returns:
            The embedding dimension (384 for all-MiniLM-L6-v2).
        """
        return self.EMBEDDING_DIMENSION

    def get_model_name(self) -> str:
        """Get the name of the embedding model.

        Returns:
            The model name.
        """
        return self.MODEL_NAME


# Singleton instance getter
@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    """Get the singleton embedding service instance.

    Returns:
        The embedding service instance.
    """
    return EmbeddingService()