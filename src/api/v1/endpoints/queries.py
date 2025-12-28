"""Query and chat endpoints."""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db, CurrentUser
from src.api.v1.schemas.queries import (
    QueryRequest,
    QueryResponse,
    ChatRequest,
    ChatResponse,
    SQLQueryRequest,
    SQLQueryResponse,
    QueryHistoryResponse,
)
from src.db.repositories.query import QueryRepository

router = APIRouter()


@router.post("/ask", response_model=QueryResponse)
async def ask_question(
    query_data: QueryRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> QueryResponse:
    """Ask a question using RAG (Retrieval Augmented Generation)."""
    query_repo = QueryRepository(db)
    
    # TODO: Implement RAG pipeline
    # 1. Route query through QueryRouter agent
    # 2. Perform vector search for relevant chunks
    # 3. Build context from retrieved chunks
    # 4. Generate response using LLM
    
    # Placeholder response
    response_text = f"This is a placeholder response for: {query_data.query}"
    
    # Save query to database
    query_record = await query_repo.create({
        "user_id": current_user.id,
        "query_text": query_data.query,
        "response_text": response_text,
        "agent_used": "query_router",
        "context_used": [],
    })
    
    return QueryResponse(
        query_id=query_record.id,
        query=query_data.query,
        response=response_text,
        sources=[],
        agent_used="query_router",
    )


@router.post("/chat", response_model=ChatResponse)
async def chat_with_context(
    chat_data: ChatRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """Chat with context from previous messages."""
    query_repo = QueryRepository(db)
    
    # TODO: Implement chat with context
    # 1. Get conversation history
    # 2. Build context from history and documents
    # 3. Generate response using LLM
    
    # Placeholder response
    response_text = f"Chat response for: {chat_data.message}"
    
    # Save query to database
    query_record = await query_repo.create({
        "user_id": current_user.id,
        "query_text": chat_data.message,
        "response_text": response_text,
        "agent_used": "document_analyzer",
        "context_used": [],
    })
    
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
    
    # TODO: Implement SQL generation
    # 1. Use SQLGenerator agent
    # 2. Validate generated SQL
    # 3. Optionally execute SQL
    
    # Placeholder response
    generated_sql = f"SELECT * FROM table WHERE condition -- Generated from: {sql_request.query}"
    
    # Save query to database
    query_record = await query_repo.create({
        "user_id": current_user.id,
        "query_text": sql_request.query,
        "response_text": generated_sql,
        "agent_used": "sql_generator",
        "context_used": [],
    })
    
    return SQLQueryResponse(
        query_id=query_record.id,
        natural_language=sql_request.query,
        generated_sql=generated_sql,
        explanation="Placeholder explanation for the generated SQL",
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