"""Query and chat endpoints with RAG support."""

import uuid
import time
import json
import asyncio
from typing import Annotated, Any, AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.api.deps import (
    get_db,
    get_embedding_service,
    get_llm_service,
    CurrentUser,
    DbSession,
    EmbeddingServiceDep,
    LLMServiceDep,
)
from src.api.v1.schemas.queries import (
    QueryRequest,
    QueryResponse,
    QueryMode,
    AgentFramework,
    ChatRequest,
    ChatResponse,
    SQLQueryRequest,
    SQLQueryResponse,
    QueryHistoryResponse,
    SourceChunk,
    RoutingInfo,
)
from src.core.di import get_container
from src.db.repositories.query import QueryRepository
from src.db.repositories.chunk import ChunkRepository
from src.db.repositories.document import DocumentRepository
from src.db.repositories.agent_log import AgentLogRepository
from src.agents import get_orchestrator, OrchestratorMode, AgentType
from src.agents import get_hybrid_orchestrator, HybridFramework, HybridAgentType

router = APIRouter()
logger = structlog.get_logger()


async def search_relevant_chunks(
    db: AsyncSession,
    query: str,
    user_id: uuid.UUID,
    document_ids: Optional[List[uuid.UUID]] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Search for relevant document chunks using vector similarity.

    Uses the DI container to get the embedding service singleton.
    """
    # Get embedding service from DI container (singleton)
    container = get_container()
    embedding_service = container.resolve("embedding_service")
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
    db: Annotated[AsyncSession, Depends(get_db)],
) -> QueryResponse:
    """Ask a question using smart agent routing.
    
    Supports multiple modes:
    - AUTO: Automatically routes to the best agent based on query content
    - RAG: Forces RAG-based question answering
    - SUMMARIZE: Forces summarization
    - ANALYZE: Forces document analysis
    - SQL: Forces SQL generation
    """
    start_time = time.time()
    query_repo = QueryRepository(db)
    agent_log_repo = AgentLogRepository(db)
    
    # Search for relevant document chunks
    sources = []
    context_texts = []
    
    try:
        # Convert document_ids to UUIDs if provided
        doc_ids = None
        if query_data.document_ids:
            doc_ids = [uuid.UUID(d) if isinstance(d, str) else d for d in query_data.document_ids]
            logger.info("RAG search with document filter", document_ids=[str(d) for d in doc_ids])
        else:
            logger.info("RAG search without document filter (all documents)")
        
        # Search for relevant chunks
        relevant_chunks = await search_relevant_chunks(
            db=db,
            query=query_data.query,
            user_id=current_user.id,
            document_ids=doc_ids,
            limit=query_data.top_k,
        )
        
        logger.info("Vector search completed", chunks_found=len(relevant_chunks))
        
        if relevant_chunks:
            # Build context from chunks
            for i, chunk in enumerate(relevant_chunks, 1):
                logger.debug("Adding chunk to context",
                           chunk_num=i,
                           doc_name=chunk['document_name'],
                           content_preview=chunk['content'][:100])
                context_texts.append(f"[Source {i}: {chunk['document_name']}]\n{chunk['content']}")
                sources.append(SourceChunk(
                    document_id=uuid.UUID(chunk['document_id']),
                    document_name=chunk['document_name'],
                    chunk_id=uuid.UUID(chunk['chunk_id']),
                    content=chunk['content'][:200] + "..." if len(chunk['content']) > 200 else chunk['content'],
                    similarity_score=chunk['score'],
                ))
            
            logger.info("Found relevant chunks", count=len(relevant_chunks))
        else:
            logger.warning("No relevant chunks found for query", query=query_data.query[:50])
    except Exception as e:
        logger.error("Vector search failed", error=str(e), error_type=type(e).__name__)
        import traceback
        logger.error("Vector search traceback", traceback=traceback.format_exc())
        # Continue without context
    
    # Determine orchestrator mode and agent based on query mode
    agent_name = query_data.agent_name
    framework_used = None
    reasoning_trace = None
    phases = None
    
    # Extended mode to agent mapping including all frameworks
    mode_to_agent = {
        QueryMode.RAG: ("rag_query", HybridFramework.CUSTOM),
        QueryMode.SUMMARIZE: ("summarizer", HybridFramework.CUSTOM),
        QueryMode.ANALYZE: ("document_analyzer", HybridFramework.CUSTOM),
        QueryMode.SQL: ("sql_generator", HybridFramework.CUSTOM),
        # LangGraph modes
        QueryMode.LG_RESEARCH: ("lg_research", HybridFramework.LANGGRAPH),
        QueryMode.LG_ANALYSIS: ("lg_analysis", HybridFramework.LANGGRAPH),
        QueryMode.LG_REASONING: ("lg_reasoning", HybridFramework.LANGGRAPH),
        # CrewAI modes
        QueryMode.CREW_RESEARCH: ("crew_research", HybridFramework.CREWAI),
        QueryMode.CREW_QA: ("crew_qa", HybridFramework.CREWAI),
        QueryMode.CREW_CODE_REVIEW: ("crew_code_review", HybridFramework.CREWAI),
        # GenAI modes
        QueryMode.GENAI_CHAT: ("genai_conversational", HybridFramework.GENAI),
        QueryMode.GENAI_TASK: ("genai_task_executor", HybridFramework.GENAI),
        QueryMode.GENAI_KNOWLEDGE: ("genai_knowledge", HybridFramework.GENAI),
        QueryMode.GENAI_REASONING: ("genai_reasoning", HybridFramework.GENAI),
        QueryMode.GENAI_CREATIVE: ("genai_creative", HybridFramework.GENAI),
    }
    
    # Check if we should use hybrid orchestrator
    use_hybrid = query_data.use_hybrid or query_data.mode in [
        QueryMode.LG_RESEARCH, QueryMode.LG_ANALYSIS, QueryMode.LG_REASONING,
        QueryMode.CREW_RESEARCH, QueryMode.CREW_QA, QueryMode.CREW_CODE_REVIEW,
        QueryMode.GENAI_CHAT, QueryMode.GENAI_TASK, QueryMode.GENAI_KNOWLEDGE,
        QueryMode.GENAI_REASONING, QueryMode.GENAI_CREATIVE,
    ]
    
    try:
        if use_hybrid:
            # Use hybrid orchestrator for multi-framework support
            hybrid_orchestrator = await get_hybrid_orchestrator()
            
            # Determine agent and framework
            if query_data.mode != QueryMode.AUTO and query_data.mode in mode_to_agent:
                agent_name, framework = mode_to_agent[query_data.mode]
                orchestrator_mode = OrchestratorMode.MANUAL
            elif query_data.agent_name:
                agent_name = query_data.agent_name
                framework = HybridFramework(query_data.framework.value) if query_data.framework else None
                orchestrator_mode = OrchestratorMode.MANUAL
            else:
                agent_name = None
                framework = None
                orchestrator_mode = OrchestratorMode.AUTO
            
            # Build sources for hybrid orchestrator
            source_data = [
                {"content": s.content, "document_name": s.document_name, "similarity": s.similarity_score}
                for s in sources
            ] if sources else None
            
            result = await hybrid_orchestrator.execute(
                query=query_data.query,
                context=context_texts if context_texts else None,
                sources=source_data,
                mode=orchestrator_mode,
                agent_name=agent_name,
                framework=framework,
            )
            
            response_text = result.get("response", "No response generated")
            agent_used = result.get("agent_used", "unknown")
            framework_used = result.get("framework", "unknown")
            routing_info = result.get("routing", {})
            reasoning_trace = result.get("reasoning_trace")
            phases = result.get("phases")
            
            logger.info(
                "Hybrid orchestrator execution completed",
                agent_used=agent_used,
                framework=framework_used,
                routing_confidence=routing_info.get("confidence", 0),
                success=result.get("success", False),
            )
        else:
            # Use original orchestrator for backward compatibility
            orchestrator = get_orchestrator()
            orchestrator_mode = OrchestratorMode.AUTO
            
            if query_data.mode != QueryMode.AUTO and query_data.mode in mode_to_agent:
                orchestrator_mode = OrchestratorMode.MANUAL
                agent_name = mode_to_agent[query_data.mode][0]
            elif query_data.agent_name:
                orchestrator_mode = OrchestratorMode.MANUAL
            
            result = await orchestrator.execute(
                query=query_data.query,
                context=context_texts if context_texts else None,
                mode=orchestrator_mode,
                agent_name=agent_name,
            )
            
            response_text = result.get("response", "No response generated")
            agent_used = result.get("agent_used", "unknown")
            framework_used = "custom"
            routing_info = result.get("routing", {})
            
            logger.info(
                "Orchestrator execution completed",
                agent_used=agent_used,
                routing_confidence=routing_info.get("confidence", 0),
                success=result.get("success", False),
            )
        
    except Exception as e:
        logger.error("Orchestrator execution failed", error=str(e))
        import traceback
        logger.error("Traceback", traceback=traceback.format_exc())
        response_text = f"I apologize, but I encountered an error processing your question. Please try again. Error: {str(e)}"
        agent_used = "error"
        framework_used = "error"
        routing_info = {"agent": "error", "confidence": 0, "reason": str(e)}
    
    execution_time_ms = (time.time() - start_time) * 1000
    
    # Prepare context for database storage (convert UUIDs to strings)
    context_for_db = []
    for s in sources:
        source_dict = s.model_dump()
        # Convert UUIDs to strings for JSON serialization
        source_dict['document_id'] = str(source_dict['document_id'])
        source_dict['chunk_id'] = str(source_dict['chunk_id'])
        context_for_db.append(source_dict)
    
    # Save query to database
    query_record = await query_repo.create({
        "user_id": current_user.id,
        "query_text": query_data.query,
        "response_text": response_text,
        "agent_used": agent_used,
        "context_used": context_for_db,
        "response_time_ms": execution_time_ms,
    })
    
    # Log agent execution
    await agent_log_repo.create({
        "agent_name": agent_used,
        "user_id": current_user.id,
        "input_data": {"query": query_data.query[:500], "mode": query_data.mode.value},
        "output_data": {"response_preview": response_text[:500]},
        "status": "completed" if "error" not in response_text.lower() else "failed",
        "execution_time_ms": execution_time_ms,
    })
    
    await db.commit()
    
    # Build routing info for response
    routing_response = None
    if routing_info:
        routing_response = RoutingInfo(
            selected_agent=routing_info.get("agent", agent_used),
            confidence=routing_info.get("confidence", 1.0),
            reason=routing_info.get("reason", "Direct execution"),
            framework=routing_info.get("framework", framework_used),
        )
    
    return QueryResponse(
        query_id=query_record.id,
        query=query_data.query,
        response=response_text,
        sources=sources,
        agent_used=agent_used,
        framework=framework_used,
        routing=routing_response,
        execution_time_ms=execution_time_ms,
        reasoning_trace=reasoning_trace,
        phases=phases,
    )


@router.post("/ask/stream")
async def ask_question_stream(
    query_data: QueryRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    """Ask a question with streaming response using Server-Sent Events (SSE).
    
    Returns a stream of events in the format:
    - data: {"type": "chunk", "content": "..."}
    - data: {"type": "sources", "sources": [...]}
    - data: {"type": "metadata", "agent": "...", "framework": "..."}
    - data: {"type": "done"}
    """
    start_time = time.time()
    
    async def generate_stream() -> AsyncGenerator[str, None]:
        """Generate SSE stream."""
        query_repo = QueryRepository(db)
        agent_log_repo = AgentLogRepository(db)
        
        # Search for relevant document chunks
        sources = []
        context_texts = []
        
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
                limit=query_data.top_k,
            )
            
            if relevant_chunks:
                for i, chunk in enumerate(relevant_chunks, 1):
                    context_texts.append(f"[Source {i}: {chunk['document_name']}]\n{chunk['content']}")
                    sources.append({
                        "document_id": chunk['document_id'],
                        "document_name": chunk['document_name'],
                        "chunk_id": chunk['chunk_id'],
                        "content": chunk['content'][:200] + "..." if len(chunk['content']) > 200 else chunk['content'],
                        "similarity_score": chunk['score'],
                    })
                
                # Send sources event
                yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
                
        except Exception as e:
            logger.error("Vector search failed in stream", error=str(e))
            yield f"data: {json.dumps({'type': 'error', 'message': f'Vector search failed: {str(e)}'})}\n\n"
        
        # Get LLM service for streaming from DI container
        try:
            container = get_container()
            llm_service = container.resolve("llm_service")
            
            # Build prompt with context
            if context_texts:
                context_str = "\n\n".join(context_texts)
                prompt = f"""Based on the following context, answer the question.

Context:
{context_str}

Question: {query_data.query}

Please provide a comprehensive answer based on the context provided. If the context doesn't contain enough information, say so."""
            else:
                prompt = query_data.query
            
            system_prompt = """You are a helpful AI assistant for document analysis and question answering.
Provide accurate, well-structured responses based on the context provided.
If you don't have enough information to answer, say so clearly."""
            
            # Stream the response
            full_response = ""
            async for chunk in llm_service.generate_stream(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=1024,
            ):
                full_response += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                await asyncio.sleep(0)  # Allow other tasks to run
            
            # Send metadata
            execution_time_ms = (time.time() - start_time) * 1000
            yield f"data: {json.dumps({'type': 'metadata', 'agent': 'rag_query', 'framework': 'custom', 'execution_time_ms': execution_time_ms})}\n\n"
            
            # Save query to database
            try:
                query_record = await query_repo.create({
                    "user_id": current_user.id,
                    "query_text": query_data.query,
                    "response_text": full_response,
                    "agent_used": "rag_query_stream",
                    "context_used": sources,
                    "response_time_ms": execution_time_ms,
                })
                
                await agent_log_repo.create({
                    "agent_name": "rag_query_stream",
                    "user_id": current_user.id,
                    "input_data": {"query": query_data.query[:500]},
                    "output_data": {"response_preview": full_response[:500]},
                    "status": "completed",
                    "execution_time_ms": execution_time_ms,
                })
                
                await db.commit()
                
                yield f"data: {json.dumps({'type': 'query_id', 'query_id': str(query_record.id)})}\n\n"
            except Exception as e:
                logger.error("Failed to save streaming query", error=str(e))
            
        except Exception as e:
            logger.error("Streaming generation failed", error=str(e))
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        # Send done event
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@router.post("/chat", response_model=ChatResponse)
async def chat_with_context(
    chat_data: ChatRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChatResponse:
    """Chat with smart agent routing and document context."""
    query_repo = QueryRepository(db)
    agent_log_repo = AgentLogRepository(db)
    start_time = time.time()
    
    # Search for relevant document chunks if document_ids provided
    sources = []
    context_texts = []
    
    if chat_data.document_ids:
        try:
            doc_ids = [uuid.UUID(d) if isinstance(d, str) else d for d in chat_data.document_ids]
            relevant_chunks = await search_relevant_chunks(
                db=db,
                query=chat_data.message,
                user_id=current_user.id,
                document_ids=doc_ids,
                limit=5,
            )
            
            for i, chunk in enumerate(relevant_chunks, 1):
                context_texts.append(f"[Source {i}: {chunk['document_name']}]\n{chunk['content']}")
                sources.append(SourceChunk(
                    document_id=uuid.UUID(chunk['document_id']),
                    document_name=chunk['document_name'],
                    chunk_id=uuid.UUID(chunk['chunk_id']),
                    content=chunk['content'][:200] + "..." if len(chunk['content']) > 200 else chunk['content'],
                    similarity_score=chunk['score'],
                ))
        except Exception as e:
            logger.error("Vector search failed in chat", error=str(e))
    
    # Use orchestrator for smart routing
    orchestrator = get_orchestrator()
    
    # Determine mode
    orchestrator_mode = OrchestratorMode.AUTO
    agent_name = None
    
    mode_to_agent = {
        QueryMode.RAG: "rag_query",
        QueryMode.SUMMARIZE: "summarizer",
        QueryMode.ANALYZE: "document_analyzer",
        QueryMode.SQL: "sql_generator",
    }
    
    if chat_data.mode != QueryMode.AUTO:
        orchestrator_mode = OrchestratorMode.MANUAL
        agent_name = mode_to_agent.get(chat_data.mode, "rag_query")
    
    try:
        result = await orchestrator.execute(
            query=chat_data.message,
            context=context_texts if context_texts else None,
            mode=orchestrator_mode,
            agent_name=agent_name,
        )
        
        response_text = result.get("response", "No response generated")
        agent_used = result.get("agent_used", "rag_query")
        routing_info = result.get("routing", {})
        
    except Exception as e:
        logger.error("Orchestrator execution failed in chat", error=str(e))
        response_text = f"I apologize, but I encountered an error processing your message. Please try again. Error: {str(e)}"
        agent_used = "error"
        routing_info = {}
    
    execution_time_ms = (time.time() - start_time) * 1000
    
    # Save query to database
    query_record = await query_repo.create({
        "user_id": current_user.id,
        "query_text": chat_data.message,
        "response_text": response_text,
        "agent_used": agent_used,
        "context_used": [],
        "response_time_ms": execution_time_ms,
    })
    
    # Log agent execution
    await agent_log_repo.create({
        "agent_name": agent_used,
        "user_id": current_user.id,
        "input_data": {"message": chat_data.message[:500], "mode": chat_data.mode.value},
        "output_data": {"response_preview": response_text[:500]},
        "status": "completed",
        "execution_time_ms": execution_time_ms,
    })
    
    await db.commit()
    
    # Build routing info for response
    routing_response = None
    if routing_info:
        routing_response = RoutingInfo(
            selected_agent=routing_info.get("agent", agent_used),
            confidence=routing_info.get("confidence", 1.0),
            reason=routing_info.get("reason", "Direct execution"),
        )
    
    return ChatResponse(
        message_id=query_record.id,
        response=response_text,
        context_used=sources,
        agent_used=agent_used,
        routing=routing_response,
    )


@router.post("/sql", response_model=SQLQueryResponse)
async def natural_language_to_sql(
    sql_request: SQLQueryRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SQLQueryResponse:
    """Convert natural language to SQL query."""
    query_repo = QueryRepository(db)
    
    try:
        # Get LLM service from DI container
        container = get_container()
        llm_service = container.resolve("llm_service")

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
    db: Annotated[AsyncSession, Depends(get_db)],
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
    db: Annotated[AsyncSession, Depends(get_db)],
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