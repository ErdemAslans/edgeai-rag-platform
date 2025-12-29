"""Chunk repository for chunk-specific and vector database operations."""

import uuid
from typing import List, Tuple

from sqlalchemy import select, delete, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.chunk import Chunk
from src.db.repositories.base import BaseRepository


class ChunkRepository(BaseRepository[Chunk]):
    """Repository for Chunk model operations including vector search."""

    def __init__(self, session: AsyncSession):
        """Initialize the chunk repository.

        Args:
            session: The async database session.
        """
        super().__init__(Chunk, session)

    async def get_by_document_id(
        self,
        document_id: uuid.UUID,
        skip: int = 0,
        limit: int = 1000,
    ) -> List[Chunk]:
        """Get all chunks for a document.

        Args:
            document_id: The UUID of the document.
            skip: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of chunk instances ordered by chunk_index.
        """
        stmt = (
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .offset(skip)
            .limit(limit)
            .order_by(Chunk.chunk_index.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_by_document_id(self, document_id: uuid.UUID) -> int:
        """Delete all chunks for a document.

        Args:
            document_id: The UUID of the document.

        Returns:
            Number of chunks deleted.
        """
        stmt = delete(Chunk).where(Chunk.document_id == document_id)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def count_by_document(self, document_id: uuid.UUID) -> int:
        """Count chunks for a specific document.

        Args:
            document_id: The UUID of the document.

        Returns:
            Number of chunks.
        """
        stmt = (
            select(func.count())
            .select_from(Chunk)
            .where(Chunk.document_id == document_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def search_similar(
        self,
        embedding: List[float],
        limit: int = 5,
        user_id: uuid.UUID | None = None,
        document_ids: List[uuid.UUID] | None = None,
        similarity_threshold: float = 0.3,
    ) -> List[Chunk]:
        """Search for similar chunks using vector similarity.
        
        Args:
            embedding: The query embedding vector.
            limit: Maximum number of results.
            user_id: Filter by user's documents.
            document_ids: Filter by specific document IDs.
            similarity_threshold: Minimum similarity score.
            
        Returns:
            List of similar chunks with similarity_score attribute.
        """
        embedding_str = f"[{','.join(map(str, embedding))}]"
        
        # Build WHERE clause
        conditions = ["1 - (c.embedding <=> :embedding) >= :threshold"]
        if user_id:
            conditions.append("d.user_id = :user_id")
        if document_ids:
            doc_ids_str = ",".join(f"'{str(doc_id)}'" for doc_id in document_ids)
            conditions.append(f"c.document_id IN ({doc_ids_str})")
        
        where_clause = " AND ".join(conditions)
        
        query = f"""
            SELECT
                c.id, c.document_id, c.chunk_index, c.content,
                c.embedding, c.metadata, c.token_count, c.created_at,
                1 - (c.embedding <=> :embedding) as similarity_score
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE {where_clause}
            ORDER BY c.embedding <=> :embedding
            LIMIT :limit
        """
        
        params = {
            "embedding": embedding_str,
            "threshold": similarity_threshold,
            "limit": limit,
        }
        if user_id:
            params["user_id"] = str(user_id)
        
        result = await self.session.execute(text(query), params)
        rows = result.fetchall()
        
        chunks = []
        for row in rows:
            chunk = Chunk(
                id=row.id,
                document_id=row.document_id,
                chunk_index=row.chunk_index,
                content=row.content,
                embedding=row.embedding,
                metadata=row.metadata,
                token_count=row.token_count,
                created_at=row.created_at,
            )
            # Add similarity score as attribute
            chunk.similarity_score = row.similarity_score
            chunks.append(chunk)
        
        return chunks

    async def similarity_search(
        self,
        query_embedding: List[float],
        limit: int = 5,
        similarity_threshold: float = 0.5,
        document_ids: List[uuid.UUID] | None = None,
    ) -> List[Tuple[Chunk, float]]:
        """Perform similarity search using pgvector cosine distance.

        Args:
            query_embedding: The query embedding vector.
            limit: Maximum number of results to return.
            similarity_threshold: Minimum similarity score (0-1).
            document_ids: Optional list of document IDs to filter by.

        Returns:
            List of tuples containing (chunk, similarity_score).
        """
        # Convert embedding to pgvector format
        embedding_str = f"[{','.join(map(str, query_embedding))}]"
        
        # Build the query using cosine distance operator <=>
        # Cosine distance = 1 - cosine_similarity, so lower is more similar
        # We convert to similarity: similarity = 1 - distance
        if document_ids:
            doc_ids_str = ",".join(f"'{str(doc_id)}'" for doc_id in document_ids)
            stmt = text(f"""
                SELECT 
                    chunks.*,
                    1 - (embedding <=> :embedding) as similarity
                FROM chunks
                WHERE document_id IN ({doc_ids_str})
                AND 1 - (embedding <=> :embedding) >= :threshold
                ORDER BY embedding <=> :embedding
                LIMIT :limit
            """)
        else:
            stmt = text("""
                SELECT 
                    chunks.*,
                    1 - (embedding <=> :embedding) as similarity
                FROM chunks
                WHERE 1 - (embedding <=> :embedding) >= :threshold
                ORDER BY embedding <=> :embedding
                LIMIT :limit
            """)

        result = await self.session.execute(
            stmt,
            {
                "embedding": embedding_str,
                "threshold": similarity_threshold,
                "limit": limit,
            },
        )
        
        rows = result.fetchall()
        chunks_with_scores = []
        
        for row in rows:
            # Reconstruct chunk from row data
            chunk = Chunk(
                id=row.id,
                document_id=row.document_id,
                chunk_index=row.chunk_index,
                content=row.content,
                embedding=row.embedding,
                metadata=row.metadata,
                token_count=row.token_count,
                created_at=row.created_at,
            )
            chunks_with_scores.append((chunk, row.similarity))
        
        return chunks_with_scores

    async def similarity_search_with_user_filter(
        self,
        query_embedding: List[float],
        user_id: uuid.UUID,
        limit: int = 5,
        similarity_threshold: float = 0.5,
    ) -> List[Tuple[Chunk, float]]:
        """Perform similarity search filtered by user's documents.

        Args:
            query_embedding: The query embedding vector.
            user_id: The UUID of the user to filter documents.
            limit: Maximum number of results to return.
            similarity_threshold: Minimum similarity score (0-1).

        Returns:
            List of tuples containing (chunk, similarity_score).
        """
        embedding_str = f"[{','.join(map(str, query_embedding))}]"
        
        stmt = text("""
            SELECT 
                c.*,
                1 - (c.embedding <=> :embedding) as similarity
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE d.user_id = :user_id
            AND 1 - (c.embedding <=> :embedding) >= :threshold
            ORDER BY c.embedding <=> :embedding
            LIMIT :limit
        """)

        result = await self.session.execute(
            stmt,
            {
                "embedding": embedding_str,
                "user_id": str(user_id),
                "threshold": similarity_threshold,
                "limit": limit,
            },
        )
        
        rows = result.fetchall()
        chunks_with_scores = []
        
        for row in rows:
            chunk = Chunk(
                id=row.id,
                document_id=row.document_id,
                chunk_index=row.chunk_index,
                content=row.content,
                embedding=row.embedding,
                metadata=row.metadata,
                token_count=row.token_count,
                created_at=row.created_at,
            )
            chunks_with_scores.append((chunk, row.similarity))
        
        return chunks_with_scores

    async def batch_create_with_embeddings(
        self,
        chunks_data: List[dict],
    ) -> List[Chunk]:
        """Create multiple chunks with embeddings in a batch.

        Args:
            chunks_data: List of dictionaries containing chunk data with embeddings.

        Returns:
            List of created chunk instances.
        """
        return await self.create_many(chunks_data)

    async def get_chunks_without_embeddings(
        self,
        limit: int = 100,
    ) -> List[Chunk]:
        """Get chunks that don't have embeddings yet.

        Args:
            limit: Maximum number of chunks to return.

        Returns:
            List of chunks without embeddings.
        """
        stmt = (
            select(Chunk)
            .where(Chunk.embedding.is_(None))
            .limit(limit)
            .order_by(Chunk.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_embedding(
        self,
        chunk_id: uuid.UUID,
        embedding: List[float],
    ) -> Chunk | None:
        """Update the embedding for a chunk.

        Args:
            chunk_id: The UUID of the chunk.
            embedding: The embedding vector.

        Returns:
            The updated chunk or None if not found.
        """
        return await self.update(chunk_id, {"embedding": embedding})