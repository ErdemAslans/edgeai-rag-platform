"""Advanced search API endpoints with hybrid search support."""

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query as QueryParam
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db, get_current_user
from src.db.models.user import User
from src.services.hybrid_search_service import get_hybrid_search_service

router = APIRouter(prefix="/search", tags=["search"])


# Request/Response schemas
class SearchRequest(BaseModel):
    """Schema for search request."""
    query: str = Field(..., min_length=1, max_length=1000)
    limit: int = Field(default=10, ge=1, le=50)
    similarity_threshold: float = Field(default=0.3, ge=0, le=1)
    document_ids: Optional[List[uuid.UUID]] = None
    use_hybrid: bool = Field(default=True, description="Use hybrid BM25+Vector search")
    use_query_expansion: bool = Field(default=True, description="Expand query with LLM")
    use_reranking: bool = Field(default=True, description="Rerank with cross-encoder")


class SearchResult(BaseModel):
    """Schema for a single search result."""
    chunk_id: str
    document_id: str
    content: str
    similarity_score: float
    chunk_index: int
    metadata: dict = {}
    search_method: str = "hybrid"
    bm25_score: Optional[float] = None
    vector_score: Optional[float] = None
    rerank_score: Optional[float] = None


class SearchResponse(BaseModel):
    """Schema for search response."""
    query: str
    expanded_query: Optional[str] = None
    results: List[SearchResult]
    total_results: int
    search_method: str
    execution_time_ms: float


class QueryExpansionRequest(BaseModel):
    """Schema for query expansion request."""
    query: str = Field(..., min_length=1, max_length=500)


class QueryExpansionResponse(BaseModel):
    """Schema for query expansion response."""
    original_query: str
    expanded_query: str


@router.post("", response_model=SearchResponse)
async def hybrid_search(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SearchResponse:
    """Perform hybrid search combining BM25 and vector search.
    
    Features:
    - BM25 keyword search for lexical matching
    - Vector similarity search for semantic matching
    - Reciprocal Rank Fusion for combining results
    - Optional cross-encoder reranking
    - Optional LLM query expansion
    """
    import time
    start_time = time.time()
    
    search_service = get_hybrid_search_service(db)
    
    # Perform search
    if request.use_hybrid:
        results = await search_service.hybrid_search(
            query=request.query,
            user_id=current_user.id,
            limit=request.limit,
            similarity_threshold=request.similarity_threshold,
            document_ids=request.document_ids,
            use_query_expansion=request.use_query_expansion,
            use_reranking=request.use_reranking,
        )
        search_method = "hybrid"
    else:
        # Pure vector search
        results = await search_service._vector_search(
            query=request.query,
            user_id=current_user.id,
            limit=request.limit,
            similarity_threshold=request.similarity_threshold,
            document_ids=request.document_ids,
        )
        search_method = "vector"
    
    execution_time = (time.time() - start_time) * 1000
    
    # Format results
    search_results = []
    for result in results:
        search_results.append(SearchResult(
            chunk_id=result["chunk_id"],
            document_id=result["document_id"],
            content=result["content"],
            similarity_score=result.get(
                "rerank_score",
                result.get("combined_score", result.get("vector_score", 0))
            ),
            chunk_index=result["chunk_index"],
            metadata=result.get("metadata", {}),
            search_method=search_method,
            bm25_score=result.get("bm25_score"),
            vector_score=result.get("vector_score"),
            rerank_score=result.get("rerank_score"),
        ))
    
    return SearchResponse(
        query=request.query,
        results=search_results,
        total_results=len(search_results),
        search_method=search_method,
        execution_time_ms=execution_time,
    )


@router.post("/expand", response_model=QueryExpansionResponse)
async def expand_query(
    request: QueryExpansionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QueryExpansionResponse:
    """Expand a query using LLM for better search coverage.
    
    This endpoint uses an LLM to generate:
    - Synonyms for key terms
    - Related concepts
    - Alternative phrasings
    """
    search_service = get_hybrid_search_service(db)
    expanded = await search_service.expand_query(request.query)
    
    return QueryExpansionResponse(
        original_query=request.query,
        expanded_query=expanded,
    )


@router.get("/context", response_model=List[SearchResult])
async def get_rag_context(
    query: str = QueryParam(..., min_length=1, max_length=1000),
    max_chunks: int = QueryParam(default=5, ge=1, le=20),
    use_hybrid: bool = QueryParam(default=True),
    use_query_expansion: bool = QueryParam(default=True),
    use_reranking: bool = QueryParam(default=True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[SearchResult]:
    """Get context passages for RAG (Retrieval-Augmented Generation).
    
    This endpoint is optimized for getting context to feed into an LLM.
    Returns the most relevant document chunks for the query.
    """
    search_service = get_hybrid_search_service(db)
    
    results = await search_service.get_context_for_query(
        query=query,
        user_id=current_user.id,
        max_chunks=max_chunks,
        use_hybrid=use_hybrid,
        use_query_expansion=use_query_expansion,
        use_reranking=use_reranking,
    )
    
    return [
        SearchResult(
            chunk_id=r["chunk_id"],
            document_id=r["document_id"],
            content=r["content"],
            similarity_score=r["similarity_score"],
            chunk_index=r["chunk_index"],
            metadata=r.get("metadata", {}),
            search_method=r.get("search_method", "hybrid"),
        )
        for r in results
    ]


@router.get("/compare")
async def compare_search_methods(
    query: str = QueryParam(..., min_length=1, max_length=500),
    limit: int = QueryParam(default=5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compare results from different search methods.
    
    Returns results from:
    1. Pure vector search
    2. Pure BM25 search
    3. Hybrid search (combined)
    4. Hybrid + reranking
    
    Useful for evaluating search quality.
    """
    import time
    
    search_service = get_hybrid_search_service(db)
    
    comparison = {}
    
    # Pure vector search
    start = time.time()
    vector_results = await search_service._vector_search(
        query=query,
        user_id=current_user.id,
        limit=limit,
        similarity_threshold=0.3,
    )
    comparison["vector"] = {
        "results": [
            {"chunk_id": r["chunk_id"], "score": r.get("vector_score", 0), "preview": r["content"][:200]}
            for r in vector_results
        ],
        "count": len(vector_results),
        "time_ms": (time.time() - start) * 1000,
    }
    
    # Pure BM25 search
    start = time.time()
    bm25_results = await search_service._bm25_search(
        query=query,
        user_id=current_user.id,
        limit=limit,
    )
    comparison["bm25"] = {
        "results": [
            {"chunk_id": r["chunk_id"], "score": r.get("bm25_score", 0), "preview": r["content"][:200]}
            for r in bm25_results
        ],
        "count": len(bm25_results),
        "time_ms": (time.time() - start) * 1000,
    }
    
    # Hybrid without reranking
    start = time.time()
    hybrid_results = await search_service.hybrid_search(
        query=query,
        user_id=current_user.id,
        limit=limit,
        use_query_expansion=False,
        use_reranking=False,
    )
    comparison["hybrid"] = {
        "results": [
            {"chunk_id": r["chunk_id"], "score": r.get("combined_score", 0), "preview": r["content"][:200]}
            for r in hybrid_results
        ],
        "count": len(hybrid_results),
        "time_ms": (time.time() - start) * 1000,
    }
    
    # Hybrid with reranking
    start = time.time()
    reranked_results = await search_service.hybrid_search(
        query=query,
        user_id=current_user.id,
        limit=limit,
        use_query_expansion=False,
        use_reranking=True,
    )
    comparison["hybrid_reranked"] = {
        "results": [
            {"chunk_id": r["chunk_id"], "score": r.get("rerank_score", r.get("combined_score", 0)), "preview": r["content"][:200]}
            for r in reranked_results
        ],
        "count": len(reranked_results),
        "time_ms": (time.time() - start) * 1000,
    }
    
    return {
        "query": query,
        "comparison": comparison,
        "analysis": _analyze_comparison(comparison),
    }


def _analyze_comparison(comparison: dict) -> dict:
    """Analyze search method comparison results."""
    analysis = {}
    
    # Check overlap between methods
    vector_ids = {r["chunk_id"] for r in comparison["vector"]["results"]}
    bm25_ids = {r["chunk_id"] for r in comparison["bm25"]["results"]}
    hybrid_ids = {r["chunk_id"] for r in comparison["hybrid"]["results"]}
    
    analysis["overlap"] = {
        "vector_bm25": len(vector_ids & bm25_ids),
        "vector_hybrid": len(vector_ids & hybrid_ids),
        "bm25_hybrid": len(bm25_ids & hybrid_ids),
    }
    
    # Performance comparison
    analysis["performance"] = {
        "fastest": min(comparison.items(), key=lambda x: x[1]["time_ms"])[0],
        "slowest": max(comparison.items(), key=lambda x: x[1]["time_ms"])[0],
    }
    
    # Result diversity
    all_ids = vector_ids | bm25_ids | hybrid_ids
    analysis["diversity"] = {
        "total_unique_results": len(all_ids),
        "vector_unique": len(vector_ids - bm25_ids),
        "bm25_unique": len(bm25_ids - vector_ids),
    }
    
    return analysis