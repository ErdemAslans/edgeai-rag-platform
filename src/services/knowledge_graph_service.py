"""Knowledge Graph service for entity extraction and graph-based QA.

This service provides:
1. Entity extraction from documents using LLM
2. Relation extraction between entities
3. Graph traversal for question answering
4. Entity resolution and deduplication

"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple, Set
import uuid
import re

from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.db.models.knowledge_graph import (
    Entity,
    EntityRelation,
    EntityMention,
    KnowledgeTriple,
)
from src.db.models.document import Document
from src.db.models.chunk import Chunk
from src.services.llm_service import get_llm_service
from src.core.logging import get_logger

logger = get_logger(__name__)


# Entity types supported
ENTITY_TYPES = [
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

# Common relation types
RELATION_TYPES = [
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


class KnowledgeGraphService:
    """Service for knowledge graph operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.llm_service = get_llm_service()

    async def extract_entities_from_chunk(
        self,
        chunk: Chunk,
        document: Document,
    ) -> List[Entity]:
        """Extract entities from a document chunk using LLM.
        
        Args:
            chunk: The chunk to extract from
            document: The parent document
            
        Returns:
            List of extracted entities
        """
        # Build prompt for entity extraction
        prompt = f"""Extract named entities from the following text. 
For each entity, provide:
1. The entity name (as it appears in text)
2. The entity type (one of: {', '.join(ENTITY_TYPES)})
3. A brief description (optional)

Text:
{chunk.content}

Respond in JSON format:
{{
    "entities": [
        {{"name": "Entity Name", "type": "entity_type", "description": "brief description"}},
        ...
    ]
}}

Only include clearly identifiable named entities. Avoid generic terms."""

        try:
            response = await self.llm_service.generate(prompt)
            entities_data = self._parse_json_response(response)
            
            extracted_entities = []
            for entity_data in entities_data.get("entities", []):
                entity = await self._get_or_create_entity(
                    name=entity_data.get("name", ""),
                    entity_type=entity_data.get("type", "other"),
                    description=entity_data.get("description"),
                )
                
                if entity:
                    # Create mention
                    await self._create_mention(
                        entity=entity,
                        document=document,
                        chunk=chunk,
                        mention_text=entity_data.get("name", ""),
                    )
                    extracted_entities.append(entity)
            
            return extracted_entities
            
        except Exception as e:
            logger.error("Entity extraction failed", error=str(e))
            return []

    async def extract_relations(
        self,
        chunk: Chunk,
        entities: List[Entity],
    ) -> List[EntityRelation]:
        """Extract relations between entities in a chunk.
        
        Args:
            chunk: The chunk containing the entities
            entities: Previously extracted entities
            
        Returns:
            List of extracted relations
        """
        if len(entities) < 2:
            return []
        
        entity_names = [e.name for e in entities]
        
        prompt = f"""Given the following text and entities, identify relationships between them.

Text:
{chunk.content}

Entities: {', '.join(entity_names)}

Possible relation types: {', '.join(RELATION_TYPES)}

For each relationship found, provide:
1. Source entity name
2. Relation type
3. Target entity name
4. Whether it's bidirectional (yes/no)

Respond in JSON format:
{{
    "relations": [
        {{"source": "Entity A", "relation": "relation_type", "target": "Entity B", "bidirectional": false}},
        ...
    ]
}}

Only include clearly stated relationships."""

        try:
            response = await self.llm_service.generate(prompt)
            relations_data = self._parse_json_response(response)
            
            extracted_relations = []
            entity_map = {e.name.lower(): e for e in entities}
            
            for rel_data in relations_data.get("relations", []):
                source_name = rel_data.get("source", "").lower()
                target_name = rel_data.get("target", "").lower()
                
                source = entity_map.get(source_name)
                target = entity_map.get(target_name)
                
                if source and target and source.id != target.id:
                    relation = EntityRelation(
                        source_entity_id=source.id,
                        target_entity_id=target.id,
                        relation_type=rel_data.get("relation", "related_to"),
                        is_bidirectional=rel_data.get("bidirectional", False),
                        document_id=chunk.document_id,
                        chunk_id=chunk.id,
                        extraction_method="llm",
                    )
                    self.session.add(relation)
                    extracted_relations.append(relation)
            
            await self.session.flush()
            return extracted_relations
            
        except Exception as e:
            logger.error("Relation extraction failed", error=str(e))
            return []

    async def extract_knowledge_triples(
        self,
        chunk: Chunk,
    ) -> List[KnowledgeTriple]:
        """Extract knowledge triples (subject, predicate, object) from text.
        
        Args:
            chunk: The chunk to extract from
            
        Returns:
            List of extracted knowledge triples
        """
        prompt = f"""Extract factual statements from the following text as knowledge triples.
Each triple should have: subject, predicate (relationship), object.

Text:
{chunk.content}

Respond in JSON format:
{{
    "triples": [
        {{"subject": "Subject", "predicate": "relationship", "object": "Object"}},
        ...
    ]
}}

Only include clear, factual statements. Avoid opinions or uncertain information."""

        try:
            response = await self.llm_service.generate(prompt)
            triples_data = self._parse_json_response(response)
            
            extracted_triples = []
            for triple_data in triples_data.get("triples", []):
                subject = triple_data.get("subject", "").strip()
                predicate = triple_data.get("predicate", "").strip()
                obj = triple_data.get("object", "").strip()
                
                if subject and predicate and obj:
                    triple = KnowledgeTriple(
                        subject=subject,
                        predicate=predicate,
                        object=obj,
                        subject_normalized=self._normalize_text(subject),
                        predicate_normalized=self._normalize_text(predicate),
                        object_normalized=self._normalize_text(obj),
                        document_id=chunk.document_id,
                        chunk_id=chunk.id,
                        source_text=chunk.content[:500] if chunk.content else None,
                        extraction_method="llm",
                    )
                    self.session.add(triple)
                    extracted_triples.append(triple)
            
            await self.session.flush()
            return extracted_triples
            
        except Exception as e:
            logger.error("Triple extraction failed", error=str(e))
            return []

    async def query_graph(
        self,
        query: str,
        max_hops: int = 2,
        top_k: int = 10,
    ) -> Dict[str, Any]:
        """Query the knowledge graph to find relevant information.
        
        Args:
            query: Natural language query
            max_hops: Maximum graph traversal depth
            top_k: Maximum results to return
            
        Returns:
            Query results with entities, relations, and triples
        """
        # Extract entities from query
        query_entities = await self._extract_query_entities(query)
        
        results = {
            "query": query,
            "query_entities": query_entities,
            "matched_entities": [],
            "relations": [],
            "triples": [],
            "paths": [],
        }
        
        # Find matching entities in graph
        matched_entities = []
        for entity_name in query_entities:
            entities = await self._find_entities(entity_name)
            matched_entities.extend(entities)
        
        results["matched_entities"] = [
            {"id": str(e.id), "name": e.name, "type": e.entity_type}
            for e in matched_entities[:top_k]
        ]
        
        # Get relations for matched entities
        if matched_entities:
            relations = await self._get_entity_relations(
                [e.id for e in matched_entities],
                max_hops=max_hops,
            )
            results["relations"] = [
                {
                    "source": r.source_entity.name,
                    "relation": r.relation_type,
                    "target": r.target_entity.name,
                }
                for r in relations[:top_k * 2]
            ]
        
        # Search knowledge triples
        triples = await self._search_triples(query, top_k)
        results["triples"] = [
            {
                "subject": t.subject,
                "predicate": t.predicate,
                "object": t.object,
                "confidence": t.confidence,
            }
            for t in triples
        ]
        
        return results

    async def answer_question(
        self,
        question: str,
    ) -> Dict[str, Any]:
        """Answer a question using the knowledge graph.
        
        Args:
            question: Natural language question
            
        Returns:
            Answer with supporting evidence from the graph
        """
        # Query the graph
        graph_results = await self.query_graph(question)
        
        # Build context from graph results
        context_parts = []
        
        # Add entity info
        for entity in graph_results["matched_entities"][:5]:
            context_parts.append(f"- {entity['name']} ({entity['type']})")
        
        # Add relations
        for rel in graph_results["relations"][:10]:
            context_parts.append(f"- {rel['source']} {rel['relation']} {rel['target']}")
        
        # Add triples
        for triple in graph_results["triples"][:10]:
            context_parts.append(f"- {triple['subject']} {triple['predicate']} {triple['object']}")
        
        if not context_parts:
            return {
                "question": question,
                "answer": "I don't have enough information in the knowledge graph to answer this question.",
                "confidence": 0,
                "sources": [],
            }
        
        # Generate answer using LLM
        context = "\n".join(context_parts)
        prompt = f"""Based on the following knowledge graph information, answer the question.

Knowledge Graph Context:
{context}

Question: {question}

Provide a clear, concise answer based only on the information provided. If the information is insufficient, say so."""

        try:
            answer = await self.llm_service.generate(prompt)
            
            return {
                "question": question,
                "answer": answer,
                "confidence": 0.8 if context_parts else 0,
                "sources": {
                    "entities": graph_results["matched_entities"],
                    "relations": graph_results["relations"],
                    "triples": graph_results["triples"],
                },
            }
        except Exception as e:
            logger.error("Question answering failed", error=str(e))
            return {
                "question": question,
                "answer": "Failed to generate answer.",
                "confidence": 0,
                "sources": [],
            }

    async def get_entity_graph(
        self,
        entity_id: uuid.UUID,
        depth: int = 1,
    ) -> Dict[str, Any]:
        """Get the subgraph around an entity.
        
        Args:
            entity_id: The center entity ID
            depth: How many hops to include
            
        Returns:
            Subgraph with nodes and edges
        """
        entity = await self.session.get(Entity, entity_id)
        if not entity:
            return {"nodes": [], "edges": []}
        
        nodes = {str(entity.id): {
            "id": str(entity.id),
            "name": entity.name,
            "type": entity.entity_type,
        }}
        edges = []
        
        visited = {entity.id}
        to_visit = [(entity.id, 0)]
        
        while to_visit:
            current_id, current_depth = to_visit.pop(0)
            
            if current_depth >= depth:
                continue
            
            # Get relations from this entity
            relations = await self.session.execute(
                select(EntityRelation)
                .where(
                    or_(
                        EntityRelation.source_entity_id == current_id,
                        EntityRelation.target_entity_id == current_id,
                    )
                )
            )
            
            for relation in relations.scalars().all():
                # Add edge
                edges.append({
                    "source": str(relation.source_entity_id),
                    "target": str(relation.target_entity_id),
                    "relation": relation.relation_type,
                })
                
                # Add connected entity if not visited
                connected_id = (
                    relation.target_entity_id
                    if relation.source_entity_id == current_id
                    else relation.source_entity_id
                )
                
                if connected_id not in visited:
                    visited.add(connected_id)
                    connected = await self.session.get(Entity, connected_id)
                    if connected:
                        nodes[str(connected_id)] = {
                            "id": str(connected_id),
                            "name": connected.name,
                            "type": connected.entity_type,
                        }
                        to_visit.append((connected_id, current_depth + 1))
        
        return {
            "nodes": list(nodes.values()),
            "edges": edges,
        }

    async def _get_or_create_entity(
        self,
        name: str,
        entity_type: str,
        description: Optional[str] = None,
    ) -> Optional[Entity]:
        """Get existing entity or create new one."""
        if not name or len(name) < 2:
            return None
        
        normalized = self._normalize_text(name)
        entity_type = entity_type.lower() if entity_type in ENTITY_TYPES else "other"
        
        # Try to find existing
        result = await self.session.execute(
            select(Entity)
            .where(
                and_(
                    Entity.normalized_name == normalized,
                    Entity.entity_type == entity_type,
                )
            )
        )
        entity = result.scalar_one_or_none()
        
        if entity:
            # Update counts
            entity.mention_count += 1
            return entity
        
        # Create new
        entity = Entity(
            name=name,
            normalized_name=normalized,
            entity_type=entity_type,
            description=description,
            mention_count=1,
            document_count=1,
        )
        self.session.add(entity)
        await self.session.flush()
        
        return entity

    async def _create_mention(
        self,
        entity: Entity,
        document: Document,
        chunk: Chunk,
        mention_text: str,
    ) -> EntityMention:
        """Create an entity mention."""
        mention = EntityMention(
            entity_id=entity.id,
            document_id=document.id,
            chunk_id=chunk.id,
            mention_text=mention_text,
            context=chunk.content[:200] if chunk.content else None,
        )
        self.session.add(mention)
        await self.session.flush()
        return mention

    async def _extract_query_entities(self, query: str) -> List[str]:
        """Extract entity names from a query string."""
        # Simple extraction - could use LLM for better results
        # For now, extract capitalized words and quoted phrases
        entities = []
        
        # Quoted phrases
        quoted = re.findall(r'"([^"]+)"', query)
        entities.extend(quoted)
        
        # Capitalized words (simple NER)
        words = query.split()
        for word in words:
            if word[0].isupper() and len(word) > 2 and word not in ["What", "Who", "Where", "When", "How", "Why"]:
                entities.append(word)
        
        return list(set(entities))

    async def _find_entities(
        self,
        name: str,
        limit: int = 5,
    ) -> List[Entity]:
        """Find entities matching a name."""
        normalized = self._normalize_text(name)
        
        result = await self.session.execute(
            select(Entity)
            .where(
                or_(
                    Entity.normalized_name.ilike(f"%{normalized}%"),
                    Entity.name.ilike(f"%{name}%"),
                )
            )
            .order_by(desc(Entity.mention_count))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _get_entity_relations(
        self,
        entity_ids: List[uuid.UUID],
        max_hops: int = 2,
    ) -> List[EntityRelation]:
        """Get relations involving given entities."""
        all_relations = []
        current_ids = set(entity_ids)
        
        for hop in range(max_hops):
            result = await self.session.execute(
                select(EntityRelation)
                .where(
                    or_(
                        EntityRelation.source_entity_id.in_(current_ids),
                        EntityRelation.target_entity_id.in_(current_ids),
                    )
                )
                .limit(50)
            )
            relations = list(result.scalars().all())
            all_relations.extend(relations)
            
            # Add new entity IDs for next hop
            for rel in relations:
                current_ids.add(rel.source_entity_id)
                current_ids.add(rel.target_entity_id)
        
        return all_relations

    async def _search_triples(
        self,
        query: str,
        limit: int = 10,
    ) -> List[KnowledgeTriple]:
        """Search knowledge triples matching a query."""
        normalized = self._normalize_text(query)
        words = normalized.split()
        
        # Search for triples containing query words
        conditions = []
        for word in words:
            if len(word) > 2:
                conditions.append(KnowledgeTriple.subject_normalized.ilike(f"%{word}%"))
                conditions.append(KnowledgeTriple.predicate_normalized.ilike(f"%{word}%"))
                conditions.append(KnowledgeTriple.object_normalized.ilike(f"%{word}%"))
        
        if not conditions:
            return []
        
        result = await self.session.execute(
            select(KnowledgeTriple)
            .where(or_(*conditions))
            .order_by(desc(KnowledgeTriple.confidence))
            .limit(limit)
        )
        return list(result.scalars().all())

    def _normalize_text(self, text: str) -> str:
        """Normalize text for matching."""
        return text.lower().strip()

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON from LLM response."""
        import json
        
        # Try to find JSON in response
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
            
            # Try to find JSON object
            match = re.search(r'\{[\s\S]*\}', response)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
        
        return {}


def get_knowledge_graph_service(session: AsyncSession) -> KnowledgeGraphService:
    """Get knowledge graph service instance."""
    return KnowledgeGraphService(session)