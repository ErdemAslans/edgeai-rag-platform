"""Query and chat endpoints with RAG support."""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.api.deps import get_db, CurrentUser
from src.api.v1.schemas.queries import (
    QueryRequest,
    QueryResponse,
    ChatRequest,
    ChatResponse,
    SQLQueryRequest,
    SQLQueryResponse,
    QueryHistoryResponse,
    SourceChunk,
)
from src.db.repositories.query import QueryRepository
from src.db.repositories.chunk import ChunkRepository
from src.db.repositories.document import DocumentRepository
from src.services.llm_service import get_llm_service
from src.services.embedding_service import get_embedding_service

router = APIRouter()
logger = structlog.get_logger()


async def search_relevant_chunks(
    db: AsyncSession,
    query: str,
    user_id: uuid.UUID,
    document_ids: Optional[List[uuid.UUID]] = None,
    limit: int = 5,
) -> List[dict]:
    """Search for relevant document chunks using vector similarity."""
    embedding_service = get_embedding_service()
    chunk_repo = ChunkRepository(db)
    doc_repo = DocumentRepository(db)
    
    # Generate embedding for the query
    query_embedding = await embedding_service.embed_text(query)
    
    # Search for similar chunks
    similar_chunks = await chunk_repo.search_similar(
        embedding=query_embedding,
        limit=limit,
        user_id=user_id,
        document_ids=document_ids,
    )
    
    # Format results with document info
    results = []
    for chunk in similar_chunks:
        doc = await doc_repo.get_by_id(chunk.document_id)
        results.append({
            "chunk_id": str(chunk.id),
            "document_id": str(chunk.document_id),
            "document_name": doc.filename if doc else "Unknown",
            "content": chunk.content,
            "score": getattr(chunk, 'similarity_score', 0.0),
        })
    
    return results


@router.post("/ask", response_model=QueryResponse)
async def ask_question(
    query_data: QueryRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> QueryResponse:
    """Ask a question using RAG (Retrieval Augmented Generation)."""
    query_repo = QueryRepository(db)
    
    # Search for relevant document chunks
    sources = []
    context_text = ""
    
    try:
        # Convert document_ids to UUIDs if provided
        doc_ids = None
        if query_data.document_ids:
            doc_ids = [uuid.UUID(d) if isinstance(d, str) else d for d in query_data.document_ids]
        
        # Search for relevant chunks
        relevant_chunks = await search_relevant_chunks(
            db=db,
            query=query_data.query,
            user_id=current_user.id,
            document_ids=doc_ids,
            limit=5,
        )
        
        if relevant_chunks:
            # Build context from chunks
            context_parts = []
            for i, chunk in enumerate(relevant_chunks, 1):
                context_parts.append(f"[Source {i}: {chunk['document_name']}]\n{chunk['content']}")
                sources.append(SourceChunk(
                    document_id=uuid.UUID(chunk['document_id']),
                    document_name=chunk['document_name'],
                    chunk_id=uuid.UUID(chunk['chunk_id']),
                    content=chunk['content'][:200] + "..." if len(chunk['content']) > 200 else chunk['content'],
                    similarity_score=chunk['score'],
                ))
            
            context_text = "\n\n".join(context_parts)
            logger.info("Found relevant chunks", count=len(relevant_chunks))
    except Exception as e:
        logger.error("Vector search failed", error=str(e))
        # Continue without context
    
    try:
        # Get LLM service
        llm_service = get_llm_service()
        
        # Build prompt with context
        if context_text:
            system_prompt = """You are a helpful AI assistant for the EdgeAI RAG Platform.
You answer questions based on the provided document context.
Always cite your sources when answering.
If the context doesn't contain relevant information, say so clearly."""

            prompt = f"""Based on the following document excerpts, please answer the question.

CONTEXT:
{context_text}

QUESTION: {query_data.query}

Please provide a comprehensive answer based on the context above. If the context doesn't contain enough information, acknowledge that."""
        else:
            system_prompt = """You are a helpful AI assistant for the EdgeAI RAG Platform.
You help users with their questions about documents and data.
Be concise, accurate, and helpful in your responses.
If you don't know something, say so clearly."""
            prompt = query_data.query

        response_text = await llm_service.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=1024,
        )
    except Exception as e:
        logger.error("LLM generation failed", error=str(e))
        response_text = f"I apologize, but I encountered an error processing your question. Please try again. Error: {str(e)}"
    
    # Save query to database
    query_record = await query_repo.create({
        "user_id": current_user.id,
        "query_text": query_data.query,
        "response_text": response_text,
        "agent_used": "rag_agent",
        "context_used": [s.model_dump() for s in sources] if sources else [],
    })
    
    await db.commit()
    
    return QueryResponse(
        query_id=query_record.id,
        query=query_data.query,
        response=response_text,
        sources=sources,
        agent_used="rag_agent",
    )


@router.post("/chat", response_model=ChatResponse)
async def chat_with_context(
    chat_data: ChatRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """Chat with context from previous messages."""
    query_repo = QueryRepository(db)
    
    try:
        # Get LLM service
        llm_service = get_llm_service()
        
        # Generate response using LLM
        system_prompt = """You are a helpful AI assistant for the EdgeAI RAG Platform.
You are having a conversation with a user. Be friendly, helpful, and informative.
Answer questions clearly and provide relevant details when asked."""

        response_text = await llm_service.generate(
            prompt=chat_data.message,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=1024,
        )
    except Exception as e:
        logger.error("LLM generation failed", error=str(e))
        response_text = f"I apologize, but I encountered an error processing your message. Please try again. Error: {str(e)}"
    
    # Save query to database
    query_record = await query_repo.create({
        "user_id": current_user.id,
        "query_text": chat_data.message,
        "response_text": response_text,
        "agent_used": "document_analyzer",
        "context_used": [],
    })
    
    await db.commit()
    
    return ChatResponse(
        message_id=query_record.id,
        response=response_text,
        context_used=[],
    )


@router.post("/sql", response_model=SQLQueryResponse)
async def natural_language_to_sql(
    sql_request: SQLQueryRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> SQLQueryResponse:
    """Convert natural language to SQL query."""
    query_repo = QueryRepository(db)
    
    try:
        # Get LLM service
        llm_service = get_llm_service()
        
        system_prompt = """You are an expert SQL query generator. Convert natural language
questions into valid SQL queries. Follow these rules:
- Generate only valid SQL syntax
- Use appropriate JOINs when needed
- Add comments explaining the query logic
- Consider performance implications
- Output the SQL query followed by a brief explanation"""

        prompt = f"Convert this to SQL: {sql_request.query}"
        if sql_request.schema_context:
            prompt += f"\n\nDatabase schema context: {sql_request.schema_context}"

        generated_response = await llm_service.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=512,
        )
        
        # Try to extract SQL from response
        generated_sql = generated_response
        explanation = "SQL query generated from natural language"
        
    except Exception as e:
        logger.error("SQL generation failed", error=str(e))
        generated_sql = f"-- Error generating SQL: {str(e)}"
        explanation = f"Error: {str(e)}"
    
    # Save query to database
    query_record = await query_repo.create({
        "user_id": current_user.id,
        "query_text": sql_request.query,
        "response_text": generated_sql,
        "agent_used": "sql_generator",
        "context_used": [],
    })
    
    await db.commit()
    
    return SQLQueryResponse(
        query_id=query_record.id,
        natural_language=sql_request.query,
        generated_sql=generated_sql,
        explanation=explanation,
        executed=False,
        results=None,
    )


@router.get("/history", response_model=QueryHistoryResponse)
async def get_query_history(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
) -> QueryHistoryResponse:
    """Get query history for the current user."""
    query_repo = QueryRepository(db)
    
    # Get queries for user
    queries = await query_repo.get_by_user_id(
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    
    # Get total count
    total = await query_repo.count_by_user(user_id=current_user.id)
    
    return QueryHistoryResponse(
        queries=[
            QueryResponse(
                query_id=q.id,
                query=q.query_text,
                response=q.response_text or "",
                sources=[],
                agent_used=q.agent_used or "unknown",
            )
            for q in queries
        ],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{query_id}", response_model=QueryResponse)
async def get_query(
    query_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> QueryResponse:
    """Get a specific query by ID."""
    query_repo = QueryRepository(db)
    query_record = await query_repo.get_by_id(query_id)
    
    if not query_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query not found",
        )
    
    if query_record.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this query",
        )
    
    return QueryResponse(
        query_id=query_record.id,
        query=query_record.query_text,
        response=query_record.response_text or "",
        sources=[],
        agent_used=query_record.agent_used or "unknown",
    )