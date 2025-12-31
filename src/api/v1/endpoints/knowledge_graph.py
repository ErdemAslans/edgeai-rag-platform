"""Knowledge Graph API endpoints.

Provides endpoints for:
- Entity extraction from documents
- Graph querying
- Question answering
- Entity and relation management

"""

from typing import Optional, List
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from src.api.deps import get_current_user, get_db
from src.db.models.user import User
from src.services.knowledge_graph_service import get_knowledge_graph_service

router = APIRouter(prefix="/knowledge-graph", tags=["knowledge-graph"])


# Request/Response Models
class EntityResponse(BaseModel):
    id: str
    name: str
    entity_type: str
    description: Optional[str]
    mention_count: int
    document_count: int


class RelationResponse(BaseModel):
    source: str
    relation: str
    target: str
    bidirectional: bool = False


class TripleResponse(BaseModel):
    subject: str
    predicate: str
    object: str
    confidence: float


class GraphQueryRequest(BaseModel):
    query: str
    max_hops: int = Field(default=2, ge=1, le=5)
    top_k: int = Field(default=10, ge=1, le=50)


class GraphQueryResponse(BaseModel):
    query: str
    query_entities: List[str]
    matched_entities: List[dict]
    relations: List[dict]
    triples: List[dict]


class QuestionRequest(BaseModel):
    question: str


class QuestionResponse(BaseModel):
    question: str
    answer: str
    confidence: float
    sources: dict


class SubgraphResponse(BaseModel):
    nodes: List[dict]
    edges: List[dict]


class ExtractEntitiesRequest(BaseModel):
    document_id: str


class ExtractEntitiesResponse(BaseModel):
    document_id: str
    entities_count: int
    relations_count: int
    triples_count: int
    status: str


@router.post("/query", response_model=GraphQueryResponse)
async def query_knowledge_graph(
    request: GraphQueryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GraphQueryResponse:
    """Query the knowledge graph with natural language.
    
    Returns entities, relations, and triples matching the query.
    """
    service = get_knowledge_graph_service(db)
    
    result = await service.query_graph(
        query=request.query,
        max_hops=request.max_hops,
        top_k=request.top_k,
    )
    
    return GraphQueryResponse(**result)


@router.post("/ask", response_model=QuestionResponse)
async def ask_question(
    request: QuestionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuestionResponse:
    """Ask a question and get an answer from the knowledge graph.
    
    Uses graph traversal and LLM to generate answers.
    """
    service = get_knowledge_graph_service(db)
    
    result = await service.answer_question(request.question)
    
    return QuestionResponse(**result)


@router.get("/entities", response_model=List[EntityResponse])
async def search_entities(
    query: str = Query(..., min_length=1, description="Search query"),
    entity_type: Optional[str] = Query(default=None, description="Filter by type"),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[EntityResponse]:
    """Search for entities in the knowledge graph.
    
    Returns entities matching the query, optionally filtered by type.
    """
    service = get_knowledge_graph_service(db)
    
    entities = await service._find_entities(query, limit)
    
    # Filter by type if specified
    if entity_type:
        entities = [e for e in entities if e.entity_type == entity_type]
    
    return [
        EntityResponse(
            id=str(e.id),
            name=e.name,
            entity_type=e.entity_type,
            description=e.description,
            mention_count=e.mention_count,
            document_count=e.document_count,
        )
        for e in entities
    ]


@router.get("/entities/{entity_id}", response_model=EntityResponse)
async def get_entity(
    entity_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EntityResponse:
    """Get a specific entity by ID."""
    from src.db.models.knowledge_graph import Entity
    
    entity = await db.get(Entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    
    return EntityResponse(
        id=str(entity.id),
        name=entity.name,
        entity_type=entity.entity_type,
        description=entity.description,
        mention_count=entity.mention_count,
        document_count=entity.document_count,
    )


@router.get("/entities/{entity_id}/graph", response_model=SubgraphResponse)
async def get_entity_subgraph(
    entity_id: uuid.UUID,
    depth: int = Query(default=1, ge=1, le=3),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubgraphResponse:
    """Get the subgraph around an entity.
    
    Returns nodes and edges within the specified depth.
    """
    service = get_knowledge_graph_service(db)
    
    result = await service.get_entity_graph(entity_id, depth)
    
    if not result["nodes"]:
        raise HTTPException(status_code=404, detail="Entity not found")
    
    return SubgraphResponse(**result)


@router.get("/entities/{entity_id}/relations", response_model=List[RelationResponse])
async def get_entity_relations(
    entity_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[RelationResponse]:
    """Get all relations for an entity."""
    service = get_knowledge_graph_service(db)
    
    relations = await service._get_entity_relations([entity_id], max_hops=1)
    
    return [
        RelationResponse(
            source=r.source_entity.name if hasattr(r, 'source_entity') and r.source_entity else str(r.source_entity_id),
            relation=r.relation_type,
            target=r.target_entity.name if hasattr(r, 'target_entity') and r.target_entity else str(r.target_entity_id),
            bidirectional=r.is_bidirectional,
        )
        for r in relations
    ]


@router.post("/extract")
async def extract_entities_from_document(
    request: ExtractEntitiesRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExtractEntitiesResponse:
    """Extract entities and relations from a document.
    
    Runs in background for large documents.
    """
    from src.db.models.document import Document
    from src.db.models.chunk import Chunk
    from sqlalchemy import select
    
    document_id = uuid.UUID(request.document_id)
    
    # Verify document exists
    document = await db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get chunks
    result = await db.execute(
        select(Chunk).where(Chunk.document_id == document_id)
    )
    chunks = list(result.scalars().all())
    
    if not chunks:
        return ExtractEntitiesResponse(
            document_id=str(document_id),
            entities_count=0,
            relations_count=0,
            triples_count=0,
            status="no_chunks",
        )
    
    service = get_knowledge_graph_service(db)
    
    total_entities = 0
    total_relations = 0
    total_triples = 0
    
    # Process each chunk
    for chunk in chunks[:10]:  # Limit to first 10 chunks
        # Extract entities
        entities = await service.extract_entities_from_chunk(chunk, document)
        total_entities += len(entities)
        
        # Extract relations
        if entities:
            relations = await service.extract_relations(chunk, entities)
            total_relations += len(relations)
        
        # Extract triples
        triples = await service.extract_knowledge_triples(chunk)
        total_triples += len(triples)
    
    await db.commit()
    
    return ExtractEntitiesResponse(
        document_id=str(document_id),
        entities_count=total_entities,
        relations_count=total_relations,
        triples_count=total_triples,
        status="completed",
    )


@router.get("/stats")
async def get_knowledge_graph_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get statistics about the knowledge graph."""
    from src.db.models.knowledge_graph import Entity, EntityRelation, KnowledgeTriple
    from sqlalchemy import select, func
    
    # Count entities
    entity_count_result = await db.execute(select(func.count(Entity.id)))
    entity_count = entity_count_result.scalar() or 0
    
    # Count by type
    type_result = await db.execute(
        select(Entity.entity_type, func.count(Entity.id))
        .group_by(Entity.entity_type)
    )
    entities_by_type = {row[0]: row[1] for row in type_result.all()}
    
    # Count relations
    relation_count_result = await db.execute(select(func.count(EntityRelation.id)))
    relation_count = relation_count_result.scalar() or 0
    
    # Count triples
    triple_count_result = await db.execute(select(func.count(KnowledgeTriple.id)))
    triple_count = triple_count_result.scalar() or 0
    
    return {
        "total_entities": entity_count,
        "entities_by_type": entities_by_type,
        "total_relations": relation_count,
        "total_triples": triple_count,
    }


@router.get("/entity-types")
async def get_entity_types(
    current_user: User = Depends(get_current_user),
) -> List[str]:
    """Get available entity types."""
    return [
        "person",
        "organization",
        "location",
        "concept",
        "product",
        "event",
        "date",
        "technology",
        "other",
    ]


@router.get("/relation-types")
async def get_relation_types(
    current_user: User = Depends(get_current_user),
) -> List[str]:
    """Get available relation types."""
    return [
        "works_for",
        "located_in",
        "part_of",
        "related_to",
        "created_by",
        "used_by",
        "depends_on",
        "successor_of",
        "predecessor_of",
        "similar_to",
    ]