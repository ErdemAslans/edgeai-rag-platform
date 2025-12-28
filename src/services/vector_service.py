"""Vector service for managing embeddings and similarity search."""

import uuid
from typing import List, Tuple, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.db.repositories.chunk import ChunkRepository
from src.db.repositories.document import DocumentRepository
from src.db.models.chunk import Chunk
from src.services.embedding_service import get_embedding_service

logger = structlog.get_logger()


class VectorService:
    """Service for vector storage and similarity search operations."""

    # Chunking configuration
    CHUNK_SIZE = 512  # Characters per chunk
    CHUNK_OVERLAP = 50  # Overlap between chunks

    def __init__(self, session: AsyncSession):
        """Initialize the vector service.

        Args:
            session: The async database session.
        """
        self.session = session
        self.chunk_repo = ChunkRepository(session)
        self.document_repo = DocumentRepository(session)
        self.embedding_service = get_embedding_service()

    async def process_document(
        self,
        document_id: uuid.UUID,
        content: str,
    ) -> List[Chunk]:
        """Process a document: chunk, embed, and store vectors.

        Args:
            document_id: The document's UUID.
            content: The document's text content.

        Returns:
            List of created chunk instances.
        """
        logger.info(
            "Processing document for vector storage",
            document_id=str(document_id),
            content_length=len(content),
        )

        # Update document status to processing
        await self.document_repo.update_status(document_id, "processing")

        try:
            # Chunk the document
            chunks_text = self._chunk_text(content)
            logger.info(
                "Document chunked",
                document_id=str(document_id),
                chunk_count=len(chunks_text),
            )

            # Generate embeddings for all chunks
            embeddings = await self.embedding_service.embed_texts(chunks_text)

            # Create chunk records with embeddings
            chunks_data = []
            for idx, (text, embedding) in enumerate(zip(chunks_text, embeddings)):
                chunks_data.append({
                    "document_id": document_id,
                    "chunk_index": idx,
                    "content": text,
                    "embedding": embedding,
                    "token_count": len(text.split()),  # Rough token estimate
                    "metadata": {
                        "char_count": len(text),
                        "position": idx,
                        "total_chunks": len(chunks_text),
                    },
                })

            # Batch create chunks
            chunks = await self.chunk_repo.batch_create_with_embeddings(chunks_data)

            # Update document status and chunk count
            await self.document_repo.update_chunk_count(document_id, len(chunks))
            await self.document_repo.update_status(document_id, "completed")

            await self.session.commit()

            logger.info(
                "Document processed successfully",
                document_id=str(document_id),
                chunks_created=len(chunks),
            )

            return chunks

        except Exception as e:
            logger.error(
                "Failed to process document",
                document_id=str(document_id),
                error=str(e),
            )
            await self.document_repo.update_status(
                document_id, "failed", error_message=str(e)
            )
            await self.session.commit()
            raise

    def _chunk_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks.

        Args:
            text: The text to chunk.

        Returns:
            List of text chunks.
        """
        if not text or not text.strip():
            return []

        chunks = []
        start = 0
        text_length = len(text)

        while start < text_length:
            end = start + self.CHUNK_SIZE

            # Try to break at sentence boundary if possible
            if end < text_length:
                # Look for sentence endings
                for boundary in [". ", ".\n", "? ", "?\n", "! ", "!\n"]:
                    boundary_pos = text.rfind(boundary, start, end)
                    if boundary_pos > start:
                        end = boundary_pos + len(boundary)
                        break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move start position with overlap
            start = end - self.CHUNK_OVERLAP if end < text_length else end

        return chunks

    async def similarity_search(
        self,
        query: str,
        limit: int = 5,
        similarity_threshold: float = 0.5,
        document_ids: List[uuid.UUID] | None = None,
    ) -> List[Tuple[Chunk, float]]:
        """Perform similarity search across all chunks.

        Args:
            query: The search query.
            limit: Maximum number of results.
            similarity_threshold: Minimum similarity score.
            document_ids: Optional list of document IDs to filter.

        Returns:
            List of (chunk, similarity_score) tuples.
        """
        # Generate query embedding
        query_embedding = await self.embedding_service.embed_query(query)

        # Perform vector search
        results = await self.chunk_repo.similarity_search(
            query_embedding=query_embedding,
            limit=limit,
            similarity_threshold=similarity_threshold,
            document_ids=document_ids,
        )

        logger.info(
            "Similarity search completed",
            query_length=len(query),
            results_count=len(results),
            threshold=similarity_threshold,
        )

        return results

    async def similarity_search_by_user(
        self,
        query: str,
        user_id: uuid.UUID,
        limit: int = 5,
        similarity_threshold: float = 0.5,
    ) -> List[Tuple[Chunk, float]]:
        """Perform similarity search filtered by user's documents.

        Args:
            query: The search query.
            user_id: The user's UUID.
            limit: Maximum number of results.
            similarity_threshold: Minimum similarity score.

        Returns:
            List of (chunk, similarity_score) tuples.
        """
        # Generate query embedding
        query_embedding = await self.embedding_service.embed_query(query)

        # Perform vector search with user filter
        results = await self.chunk_repo.similarity_search_with_user_filter(
            query_embedding=query_embedding,
            user_id=user_id,
            limit=limit,
            similarity_threshold=similarity_threshold,
        )

        logger.info(
            "User-filtered similarity search completed",
            query_length=len(query),
            user_id=str(user_id),
            results_count=len(results),
        )

        return results

    async def get_context_for_query(
        self,
        query: str,
        user_id: uuid.UUID,
        max_chunks: int = 5,
        similarity_threshold: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """Get context passages for a RAG query.

        Args:
            query: The user's query.
            user_id: The user's UUID.
            max_chunks: Maximum number of context chunks.
            similarity_threshold: Minimum similarity score.

        Returns:
            List of context dictionaries with content and metadata.
        """
        results = await self.similarity_search_by_user(
            query=query,
            user_id=user_id,
            limit=max_chunks,
            similarity_threshold=similarity_threshold,
        )

        context = []
        for chunk, score in results:
            context.append({
                "chunk_id": str(chunk.id),
                "document_id": str(chunk.document_id),
                "content": chunk.content,
                "similarity_score": score,
                "chunk_index": chunk.chunk_index,
                "metadata": chunk.metadata,
            })

        return context

    async def delete_document_vectors(self, document_id: uuid.UUID) -> int:
        """Delete all vectors for a document.

        Args:
            document_id: The document's UUID.

        Returns:
            Number of chunks deleted.
        """
        count = await self.chunk_repo.delete_by_document_id(document_id)
        await self.session.commit()
        
        logger.info(
            "Document vectors deleted",
            document_id=str(document_id),
            chunks_deleted=count,
        )
        
        return count

    async def reprocess_document(
        self,
        document_id: uuid.UUID,
        content: str,
    ) -> List[Chunk]:
        """Reprocess a document (delete existing chunks and create new ones).

        Args:
            document_id: The document's UUID.
            content: The document's text content.

        Returns:
            List of newly created chunk instances.
        """
        # Delete existing chunks
        await self.delete_document_vectors(document_id)

        # Process document again
        return await self.process_document(document_id, content)

    def get_embedding_dimension(self) -> int:
        """Get the embedding dimension used by the service.

        Returns:
            The embedding dimension.
        """
        return self.embedding_service.get_embedding_dimension()