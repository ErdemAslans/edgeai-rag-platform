"""Query service for handling user queries with RAG."""

import uuid
import time
from typing import List, Dict, Any, Tuple
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.db.repositories.query import QueryRepository
from src.db.repositories.agent_log import AgentLogRepository
from src.db.models.query import Query
from src.services.vector_service import VectorService
from src.services.llm_service import LLMService, get_llm_service

logger = structlog.get_logger()


class QueryService:
    """Service for handling user queries with RAG pipeline."""

    def __init__(self, session: AsyncSession):
        """Initialize the query service.

        Args:
            session: The async database session.
        """
        self.session = session
        self.query_repo = QueryRepository(session)
        self.agent_log_repo = AgentLogRepository(session)
        self.vector_service = VectorService(session)
        self.llm_service = get_llm_service()

    async def process_query(
        self,
        user_id: uuid.UUID,
        query_text: str,
        max_context_chunks: int = 5,
        similarity_threshold: float = 0.5,
    ) -> Query:
        """Process a user query using RAG pipeline.

        Args:
            user_id: The user's UUID.
            query_text: The user's query text.
            max_context_chunks: Maximum context chunks to retrieve.
            similarity_threshold: Minimum similarity threshold.

        Returns:
            The query record with response.
        """
        start_time = time.time()

        logger.info(
            "Processing query",
            user_id=str(user_id),
            query_length=len(query_text),
        )

        # Create query record
        query = await self.query_repo.create({
            "user_id": user_id,
            "query_text": query_text,
            "status": "processing",
        })

        try:
            # Retrieve relevant context
            context_results = await self.vector_service.get_context_for_query(
                query=query_text,
                user_id=user_id,
                max_chunks=max_context_chunks,
                similarity_threshold=similarity_threshold,
            )

            # Store context chunks used
            if context_results:
                chunk_refs = [
                    (uuid.UUID(ctx["chunk_id"]), ctx["similarity_score"])
                    for ctx in context_results
                ]
                await self.query_repo.add_query_chunks(query.id, chunk_refs)

            # Extract context texts for LLM
            context_texts = [ctx["content"] for ctx in context_results]

            # Generate response using LLM
            response_text = await self.llm_service.generate_with_context(
                query=query_text,
                context=context_texts,
            )

            # Calculate response time
            response_time_ms = (time.time() - start_time) * 1000

            # Update query with response
            query = await self.query_repo.update(
                query.id,
                {
                    "response_text": response_text,
                    "agent_used": "rag_query",
                    "context_used": context_results,
                    "response_time_ms": response_time_ms,
                },
            )

            await self.session.commit()

            logger.info(
                "Query processed successfully",
                query_id=str(query.id),
                context_chunks=len(context_results),
                response_time_ms=response_time_ms,
            )

            return query

        except Exception as e:
            logger.error(
                "Query processing failed",
                query_id=str(query.id),
                error=str(e),
            )
            await self.query_repo.update(
                query.id,
                {
                    "response_text": f"Error processing query: {str(e)}",
                    "response_time_ms": (time.time() - start_time) * 1000,
                },
            )
            await self.session.commit()
            raise

    async def process_query_with_agent(
        self,
        user_id: uuid.UUID,
        query_text: str,
        agent_name: str,
        agent_config: Dict[str, Any] | None = None,
    ) -> Query:
        """Process a query using a specific agent.

        Args:
            user_id: The user's UUID.
            query_text: The user's query text.
            agent_name: Name of the agent to use.
            agent_config: Optional agent configuration.

        Returns:
            The query record with response.
        """
        start_time = time.time()

        # Create query record
        query = await self.query_repo.create({
            "user_id": user_id,
            "query_text": query_text,
            "agent_used": agent_name,
        })

        # Create agent log
        agent_log = await self.agent_log_repo.create_log(
            agent_name=agent_name,
            input_data={
                "query_text": query_text,
                "config": agent_config or {},
            },
            query_id=query.id,
            model_name=self.llm_service.get_model(),
        )

        try:
            # Route to appropriate agent handler
            response_text, context_used = await self._execute_agent(
                agent_name=agent_name,
                query_text=query_text,
                user_id=user_id,
                config=agent_config,
            )

            response_time_ms = (time.time() - start_time) * 1000

            # Update query
            query = await self.query_repo.update(
                query.id,
                {
                    "response_text": response_text,
                    "context_used": context_used,
                    "response_time_ms": response_time_ms,
                },
            )

            # Update agent log
            await self.agent_log_repo.mark_completed(
                log_id=agent_log.id,
                output_data={"response": response_text[:500]},  # Truncate for log
                execution_time_ms=response_time_ms,
            )

            await self.session.commit()
            return query

        except Exception as e:
            await self.agent_log_repo.mark_failed(
                log_id=agent_log.id,
                error_message=str(e),
            )
            await self.session.commit()
            raise

    async def _execute_agent(
        self,
        agent_name: str,
        query_text: str,
        user_id: uuid.UUID,
        config: Dict[str, Any] | None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Execute a specific agent.

        Args:
            agent_name: Name of the agent.
            query_text: The query text.
            user_id: The user's UUID.
            config: Optional configuration.

        Returns:
            Tuple of (response_text, context_used).
        """
        context_used = []

        if agent_name == "summarizer":
            response = await self._execute_summarizer(query_text, user_id, config)
        elif agent_name == "sql_generator":
            response = await self._execute_sql_generator(query_text, config)
        elif agent_name == "document_analyzer":
            response, context_used = await self._execute_document_analyzer(
                query_text, user_id, config
            )
        elif agent_name == "query_router":
            response = await self._execute_query_router(query_text)
        else:
            # Default RAG query
            context_results = await self.vector_service.get_context_for_query(
                query=query_text,
                user_id=user_id,
            )
            context_used = context_results
            context_texts = [ctx["content"] for ctx in context_results]
            response = await self.llm_service.generate_with_context(
                query=query_text,
                context=context_texts,
            )

        return response, context_used

    async def _execute_summarizer(
        self,
        query_text: str,
        user_id: uuid.UUID,
        config: Dict[str, Any] | None,
    ) -> str:
        """Execute the summarizer agent."""
        system_prompt = """You are a summarization expert. Your task is to create clear, 
concise summaries that capture the key points. Focus on:
- Main ideas and conclusions
- Key facts and figures
- Important relationships and dependencies
Keep summaries well-structured and easy to read."""

        # Get context if this is about documents
        context_results = await self.vector_service.get_context_for_query(
            query=query_text,
            user_id=user_id,
            max_chunks=10,
        )
        
        if context_results:
            context_texts = [ctx["content"] for ctx in context_results]
            prompt = f"""Please summarize the following content:

{chr(10).join(context_texts)}

User request: {query_text}"""
        else:
            prompt = f"Please summarize: {query_text}"

        return await self.llm_service.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=1024,
        )

    async def _execute_sql_generator(
        self,
        query_text: str,
        config: Dict[str, Any] | None,
    ) -> str:
        """Execute the SQL generator agent."""
        schema_info = config.get("schema", "") if config else ""

        system_prompt = """You are an expert SQL query generator. Convert natural language 
questions into valid SQL queries. Follow these rules:
- Generate only valid SQL syntax
- Use appropriate JOINs when needed
- Add comments explaining the query logic
- Consider performance implications
- If the schema is provided, use only those tables and columns"""

        prompt = f"""Generate a SQL query for the following request:

{query_text}

{f'Database Schema:{chr(10)}{schema_info}' if schema_info else 'Note: No schema provided, generate a generic query.'}"""

        return await self.llm_service.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=512,
        )

    async def _execute_document_analyzer(
        self,
        query_text: str,
        user_id: uuid.UUID,
        config: Dict[str, Any] | None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Execute the document analyzer agent."""
        system_prompt = """You are a document analysis expert. Analyze documents to extract:
- Key themes and topics
- Important entities (people, organizations, dates)
- Main arguments or conclusions
- Document structure and organization
- Relationships between concepts
Provide structured, detailed analysis."""

        context_results = await self.vector_service.get_context_for_query(
            query=query_text,
            user_id=user_id,
            max_chunks=10,
        )

        if not context_results:
            return "No relevant documents found for analysis.", []

        context_texts = [ctx["content"] for ctx in context_results]
        
        prompt = f"""Analyze the following document content:

{chr(10).join(context_texts)}

Analysis request: {query_text}"""

        response = await self.llm_service.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=1500,
        )

        return response, context_results

    async def _execute_query_router(self, query_text: str) -> str:
        """Execute the query router to determine the best agent."""
        system_prompt = """You are a query routing expert. Analyze the user's query and 
determine which agent should handle it. Available agents:
- summarizer: For summarizing documents or content
- sql_generator: For generating SQL queries from natural language
- document_analyzer: For deep analysis of document content
- rag_query: For general question answering using document context

Respond with ONLY the agent name, nothing else."""

        response = await self.llm_service.generate(
            prompt=f"Route this query to the appropriate agent: {query_text}",
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=50,
        )

        return response.strip().lower()

    async def get_query_history(
        self,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Query]:
        """Get query history for a user.

        Args:
            user_id: The user's UUID.
            skip: Number of records to skip.
            limit: Maximum number of records.

        Returns:
            List of query records.
        """
        return await self.query_repo.get_by_user_id(user_id, skip=skip, limit=limit)

    async def get_query_by_id(
        self,
        query_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Query | None:
        """Get a specific query by ID.

        Args:
            query_id: The query's UUID.
            user_id: The user's UUID for ownership verification.

        Returns:
            The query record or None.
        """
        query = await self.query_repo.get_by_id(query_id)
        if query and query.user_id == user_id:
            return query
        return None

    async def get_statistics(self, user_id: uuid.UUID) -> Dict[str, Any]:
        """Get query statistics for a user.

        Args:
            user_id: The user's UUID.

        Returns:
            Dictionary with statistics.
        """
        return await self.query_repo.get_query_statistics(user_id)