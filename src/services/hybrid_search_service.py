"""Hybrid Search Service combining BM25 and Vector Search with Reranking.

This service implements:
1. BM25 keyword search for lexical matching
2. Vector similarity search for semantic matching
3. Reciprocal Rank Fusion (RRF) for combining results
4. Cross-encoder reranking for improved relevance
5. LLM-based query expansion
"""

import asyncio
import math
import re
from collections import defaultdict
from typing import List, Tuple, Dict, Any, Optional
import uuid

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.db.models.chunk import Chunk
from src.db.models.document import Document
from src.db.repositories.chunk import ChunkRepository
from src.services.embedding_service import get_embedding_service
from src.services.llm_service import get_llm_service

logger = structlog.get_logger()


class BM25Index:
    """Simple BM25 index for keyword search."""
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """Initialize BM25 parameters.
        
        Args:
            k1: Term frequency saturation parameter
            b: Length normalization parameter
        """
        self.k1 = k1
        self.b = b
        self.doc_freqs: Dict[str, int] = defaultdict(int)
        self.doc_lengths: Dict[str, int] = {}
        self.avg_doc_length: float = 0
        self.corpus_size: int = 0
        self.doc_terms: Dict[str, Dict[str, int]] = {}
    
    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Simple tokenizer for text."""
        text = text.lower()
        # Remove punctuation and split
        tokens = re.findall(r'\b\w+\b', text)
        # Filter out very short tokens
        return [t for t in tokens if len(t) > 1]
    
    def add_document(self, doc_id: str, text: str) -> None:
        """Add a document to the index."""
        tokens = self.tokenize(text)
        self.doc_lengths[doc_id] = len(tokens)
        
        # Count term frequencies
        term_freq: Dict[str, int] = defaultdict(int)
        for token in tokens:
            term_freq[token] += 1
        
        self.doc_terms[doc_id] = dict(term_freq)
        
        # Update document frequencies
        for term in term_freq:
            self.doc_freqs[term] += 1
        
        self.corpus_size += 1
        self._update_avg_length()
    
    def _update_avg_length(self) -> None:
        """Update average document length."""
        if self.corpus_size > 0:
            self.avg_doc_length = sum(self.doc_lengths.values()) / self.corpus_size
    
    def get_scores(self, query: str) -> Dict[str, float]:
        """Calculate BM25 scores for all documents given a query."""
        query_tokens = self.tokenize(query)
        scores: Dict[str, float] = defaultdict(float)
        
        for term in query_tokens:
            if term not in self.doc_freqs:
                continue
            
            # IDF calculation
            df = self.doc_freqs[term]
            idf = math.log((self.corpus_size - df + 0.5) / (df + 0.5) + 1)
            
            # Score each document
            for doc_id, term_freqs in self.doc_terms.items():
                if term in term_freqs:
                    tf = term_freqs[term]
                    doc_len = self.doc_lengths[doc_id]
                    
                    # BM25 formula
                    numerator = tf * (self.k1 + 1)
                    denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avg_doc_length)
                    scores[doc_id] += idf * numerator / denominator
        
        return dict(scores)
    
    def search(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """Search and return top-k documents."""
        scores = self.get_scores(query)
        sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_docs[:top_k]


class CrossEncoderReranker:
    """Cross-encoder for reranking search results."""
    
    MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    _instance = None
    _model = None
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the cross-encoder."""
        if self._model is None:
            self._load_model()
    
    def _load_model(self) -> None:
        """Load the cross-encoder model."""
        try:
            from sentence_transformers import CrossEncoder
            logger.info("Loading cross-encoder model", model=self.MODEL_NAME)
            self._model = CrossEncoder(self.MODEL_NAME)
            logger.info("Cross-encoder loaded successfully")
        except ImportError:
            logger.warning(
                "sentence-transformers not available for cross-encoder. "
                "Reranking will be disabled."
            )
            self._model = None
        except Exception as e:
            logger.error("Failed to load cross-encoder", error=str(e))
            self._model = None
    
    async def rerank(
        self,
        query: str,
        documents: List[Tuple[str, str, float]],  # (doc_id, content, score)
        top_k: int = 5,
    ) -> List[Tuple[str, str, float]]:
        """Rerank documents using cross-encoder.
        
        Args:
            query: The search query
            documents: List of (doc_id, content, original_score)
            top_k: Number of top results to return
            
        Returns:
            Reranked list of (doc_id, content, new_score)
        """
        if self._model is None or not documents:
            return documents[:top_k]
        
        # Prepare query-document pairs
        pairs = [(query, doc[1]) for doc in documents]
        
        # Score with cross-encoder
        scores = await asyncio.to_thread(self._model.predict, pairs)
        
        # Combine with documents
        reranked = [
            (doc[0], doc[1], float(score))
            for doc, score in zip(documents, scores)
        ]
        
        # Sort by new scores
        reranked.sort(key=lambda x: x[2], reverse=True)
        
        return reranked[:top_k]


class HybridSearchService:
    """Service for hybrid search combining BM25 and vector search."""
    
    # RRF constant (typically 60)
    RRF_K = 60
    
    # Weights for combining scores
    VECTOR_WEIGHT = 0.7
    BM25_WEIGHT = 0.3
    
    def __init__(self, session: AsyncSession):
        """Initialize the hybrid search service."""
        self.session = session
        self.chunk_repo = ChunkRepository(session)
        self.embedding_service = get_embedding_service()
        self.llm_service = get_llm_service()
        self.reranker = CrossEncoderReranker()
        self._bm25_index: Optional[BM25Index] = None
        self._index_doc_ids: set = set()
    
    async def _ensure_bm25_index(
        self,
        user_id: uuid.UUID,
        document_ids: Optional[List[uuid.UUID]] = None,
    ) -> BM25Index:
        """Build or update BM25 index for user's documents."""
        # Get chunks for user
        query = (
            select(Chunk)
            .join(Document, Chunk.document_id == Document.id)
            .where(Document.user_id == user_id)
        )
        
        if document_ids:
            query = query.where(Document.id.in_(document_ids))
        
        result = await self.session.execute(query)
        chunks = result.scalars().all()
        
        # Check if we need to rebuild index
        current_ids = {str(c.id) for c in chunks}
        if self._bm25_index is None or current_ids != self._index_doc_ids:
            self._bm25_index = BM25Index()
            for chunk in chunks:
                self._bm25_index.add_document(str(chunk.id), chunk.content)
            self._index_doc_ids = current_ids
            logger.info("BM25 index rebuilt", chunk_count=len(chunks))
        
        return self._bm25_index
    
    async def expand_query(self, query: str) -> str:
        """Expand query using LLM for better semantic coverage.
        
        Args:
            query: Original query
            
        Returns:
            Expanded query with synonyms and related terms
        """
        expansion_prompt = f"""Given the following search query, generate an expanded version that includes:
1. Synonyms for key terms
2. Related concepts
3. Alternative phrasings

Original query: {query}

Return ONLY the expanded query, no explanations. Keep it concise (under 100 words).
Expanded query:"""
        
        try:
            expanded = await self.llm_service.generate(
                prompt=expansion_prompt,
                max_tokens=150,
                temperature=0.3,
            )
            # Combine original and expanded
            combined = f"{query} {expanded.strip()}"
            logger.info(
                "Query expanded",
                original=query,
                expanded=expanded.strip()[:100],
            )
            return combined
        except Exception as e:
            logger.warning("Query expansion failed, using original", error=str(e))
            return query
    
    async def hybrid_search(
        self,
        query: str,
        user_id: uuid.UUID,
        limit: int = 10,
        similarity_threshold: float = 0.3,
        document_ids: Optional[List[uuid.UUID]] = None,
        use_query_expansion: bool = True,
        use_reranking: bool = True,
    ) -> List[Dict[str, Any]]:
        """Perform hybrid search combining BM25 and vector search.
        
        Args:
            query: Search query
            user_id: User's UUID
            limit: Maximum results to return
            similarity_threshold: Minimum similarity for vector search
            document_ids: Optional filter by document IDs
            use_query_expansion: Whether to expand query with LLM
            use_reranking: Whether to rerank results with cross-encoder
            
        Returns:
            List of search results with scores
        """
        # Optionally expand query
        search_query = query
        if use_query_expansion:
            search_query = await self.expand_query(query)
        
        # Run BM25 and vector search in parallel
        bm25_task = self._bm25_search(search_query, user_id, limit * 2, document_ids)
        vector_task = self._vector_search(
            search_query, user_id, limit * 2, similarity_threshold, document_ids
        )
        
        bm25_results, vector_results = await asyncio.gather(bm25_task, vector_task)
        
        # Combine using Reciprocal Rank Fusion
        combined = self._reciprocal_rank_fusion(
            bm25_results,
            vector_results,
            k=self.RRF_K,
        )
        
        logger.info(
            "Hybrid search completed",
            query_length=len(query),
            bm25_results=len(bm25_results),
            vector_results=len(vector_results),
            combined_results=len(combined),
        )
        
        # Optionally rerank with cross-encoder
        if use_reranking and combined:
            # Prepare for reranking
            docs_for_rerank = [
                (r["chunk_id"], r["content"], r["combined_score"])
                for r in combined[:limit * 2]
            ]
            reranked = await self.reranker.rerank(query, docs_for_rerank, limit)
            
            # Update results with reranked scores
            rerank_map = {doc[0]: doc[2] for doc in reranked}
            for result in combined:
                if result["chunk_id"] in rerank_map:
                    result["rerank_score"] = rerank_map[result["chunk_id"]]
            
            # Sort by rerank score
            combined.sort(
                key=lambda x: x.get("rerank_score", x["combined_score"]),
                reverse=True,
            )
        
        return combined[:limit]
    
    async def _bm25_search(
        self,
        query: str,
        user_id: uuid.UUID,
        limit: int,
        document_ids: Optional[List[uuid.UUID]] = None,
    ) -> List[Dict[str, Any]]:
        """Perform BM25 keyword search."""
        index = await self._ensure_bm25_index(user_id, document_ids)
        
        if index.corpus_size == 0:
            return []
        
        results = index.search(query, limit)
        
        # Fetch chunk details
        chunk_ids = [uuid.UUID(r[0]) for r in results]
        if not chunk_ids:
            return []
        
        chunks_query = select(Chunk).where(Chunk.id.in_(chunk_ids))
        result = await self.session.execute(chunks_query)
        chunks_map = {str(c.id): c for c in result.scalars().all()}
        
        search_results = []
        for chunk_id, score in results:
            if chunk_id in chunks_map:
                chunk = chunks_map[chunk_id]
                search_results.append({
                    "chunk_id": chunk_id,
                    "document_id": str(chunk.document_id),
                    "content": chunk.content,
                    "bm25_score": score,
                    "chunk_index": chunk.chunk_index,
                    "metadata": chunk.metadata,
                })
        
        return search_results
    
    async def _vector_search(
        self,
        query: str,
        user_id: uuid.UUID,
        limit: int,
        similarity_threshold: float,
        document_ids: Optional[List[uuid.UUID]] = None,
    ) -> List[Dict[str, Any]]:
        """Perform vector similarity search."""
        # Generate query embedding
        query_embedding = await self.embedding_service.embed_query(query)
        
        # Perform search
        results = await self.chunk_repo.similarity_search_with_user_filter(
            query_embedding=query_embedding,
            user_id=user_id,
            limit=limit,
            similarity_threshold=similarity_threshold,
        )
        
        search_results = []
        for chunk, score in results:
            search_results.append({
                "chunk_id": str(chunk.id),
                "document_id": str(chunk.document_id),
                "content": chunk.content,
                "vector_score": score,
                "chunk_index": chunk.chunk_index,
                "metadata": chunk.metadata,
            })
        
        return search_results
    
    def _reciprocal_rank_fusion(
        self,
        bm25_results: List[Dict[str, Any]],
        vector_results: List[Dict[str, Any]],
        k: int = 60,
    ) -> List[Dict[str, Any]]:
        """Combine results using Reciprocal Rank Fusion (RRF).
        
        RRF formula: score = sum(1 / (k + rank)) for each result list
        """
        rrf_scores: Dict[str, float] = defaultdict(float)
        all_results: Dict[str, Dict[str, Any]] = {}
        
        # Process BM25 results
        for rank, result in enumerate(bm25_results, 1):
            chunk_id = result["chunk_id"]
            rrf_scores[chunk_id] += self.BM25_WEIGHT * (1 / (k + rank))
            if chunk_id not in all_results:
                all_results[chunk_id] = result.copy()
            else:
                all_results[chunk_id]["bm25_score"] = result.get("bm25_score")
        
        # Process vector results
        for rank, result in enumerate(vector_results, 1):
            chunk_id = result["chunk_id"]
            rrf_scores[chunk_id] += self.VECTOR_WEIGHT * (1 / (k + rank))
            if chunk_id not in all_results:
                all_results[chunk_id] = result.copy()
            else:
                all_results[chunk_id]["vector_score"] = result.get("vector_score")
        
        # Combine and sort
        combined = []
        for chunk_id, score in sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True):
            result = all_results[chunk_id]
            result["combined_score"] = score
            result["rrf_score"] = score
            combined.append(result)
        
        return combined
    
    async def get_context_for_query(
        self,
        query: str,
        user_id: uuid.UUID,
        max_chunks: int = 5,
        use_hybrid: bool = True,
        use_query_expansion: bool = True,
        use_reranking: bool = True,
    ) -> List[Dict[str, Any]]:
        """Get context passages for a RAG query using hybrid search.
        
        Args:
            query: The user's query
            user_id: User's UUID
            max_chunks: Maximum context chunks
            use_hybrid: Whether to use hybrid search (vs pure vector)
            use_query_expansion: Whether to expand query
            use_reranking: Whether to rerank results
            
        Returns:
            List of context dictionaries
        """
        if use_hybrid:
            results = await self.hybrid_search(
                query=query,
                user_id=user_id,
                limit=max_chunks,
                use_query_expansion=use_query_expansion,
                use_reranking=use_reranking,
            )
        else:
            # Fall back to pure vector search
            results = await self._vector_search(
                query=query,
                user_id=user_id,
                limit=max_chunks,
                similarity_threshold=0.3,
            )
        
        # Format for RAG context
        context = []
        for result in results:
            context.append({
                "chunk_id": result["chunk_id"],
                "document_id": result["document_id"],
                "content": result["content"],
                "similarity_score": result.get(
                    "rerank_score",
                    result.get("combined_score", result.get("vector_score", 0))
                ),
                "chunk_index": result["chunk_index"],
                "metadata": result.get("metadata", {}),
                "search_method": "hybrid" if use_hybrid else "vector",
            })
        
        return context


# Factory function
def get_hybrid_search_service(session: AsyncSession) -> HybridSearchService:
    """Get hybrid search service instance."""
    return HybridSearchService(session)