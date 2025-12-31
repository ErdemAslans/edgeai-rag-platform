"""Knowledge Graph models for entity extraction and graph-based QA.

This module provides:
1. Entity - Extracted entities from documents
2. EntityRelation - Relationships between entities
3. EntityMention - Where entities are mentioned in documents

"""

from datetime import datetime
from typing import Optional, Dict, Any, List
import uuid as uuid_lib

from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    JSON,
    Boolean,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.db.base import Base


class Entity(Base):
    """Represents an extracted entity from documents.
    
    Entities are named things like people, organizations, locations,
    concepts, products, etc. extracted from document content.
    """
    
    __tablename__ = "entities"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    
    # Entity identification
    name = Column(String(500), nullable=False, index=True)
    normalized_name = Column(String(500), nullable=False, index=True)  # Lowercase, cleaned
    entity_type = Column(String(50), nullable=False, index=True)  # person, org, location, concept, etc.
    
    # Additional entity info
    description = Column(Text, nullable=True)
    aliases = Column(JSON, nullable=True, default=list)  # Alternative names
    
    # External IDs (for linking to knowledge bases)
    external_ids = Column(JSON, nullable=True, default=dict)  # {"wikidata": "Q123", "dbpedia": "..."}
    
    # Embedding for semantic similarity
    embedding = Column(JSON, nullable=True)  # Store as JSON, could use pgvector
    
    # Statistics
    mention_count = Column(Integer, default=0)
    document_count = Column(Integer, default=0)
    
    # Metadata
    properties = Column(JSON, nullable=True, default=dict)  # Type-specific properties
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    mentions = relationship(
        "EntityMention",
        back_populates="entity",
        cascade="all, delete-orphan",
    )
    relations_from = relationship(
        "EntityRelation",
        back_populates="source_entity",
        foreign_keys="EntityRelation.source_entity_id",
        cascade="all, delete-orphan",
    )
    relations_to = relationship(
        "EntityRelation",
        back_populates="target_entity",
        foreign_keys="EntityRelation.target_entity_id",
        cascade="all, delete-orphan",
    )
    
    __table_args__ = (
        UniqueConstraint('normalized_name', 'entity_type', name='uq_entity_name_type'),
        Index('ix_entity_type_name', 'entity_type', 'normalized_name'),
    )
    
    def __repr__(self) -> str:
        return f"<Entity(id={self.id}, name={self.name}, type={self.entity_type})>"


class EntityRelation(Base):
    """Represents a relationship between two entities.
    
    Relations capture how entities are connected, e.g.,
    "Person X works_for Organization Y" or
    "Concept A is_part_of Concept B".
    """
    
    __tablename__ = "entity_relations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    
    # Source and target entities
    source_entity_id = Column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_entity_id = Column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Relation type
    relation_type = Column(String(100), nullable=False, index=True)
    
    # Relation properties
    properties = Column(JSON, nullable=True, default=dict)
    
    # Confidence and provenance
    confidence = Column(Float, default=1.0)
    extraction_method = Column(String(50), nullable=True)  # llm, rule, manual
    
    # Source document for this relation
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    chunk_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chunks.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Bidirectional?
    is_bidirectional = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    source_entity = relationship(
        "Entity",
        back_populates="relations_from",
        foreign_keys=[source_entity_id],
    )
    target_entity = relationship(
        "Entity",
        back_populates="relations_to",
        foreign_keys=[target_entity_id],
    )
    document = relationship("Document")
    chunk = relationship("Chunk")
    
    __table_args__ = (
        Index('ix_relation_entities', 'source_entity_id', 'target_entity_id'),
        Index('ix_relation_type_source', 'relation_type', 'source_entity_id'),
    )
    
    def __repr__(self) -> str:
        return f"<EntityRelation(id={self.id}, type={self.relation_type})>"


class EntityMention(Base):
    """Tracks where entities are mentioned in documents.
    
    This enables finding all occurrences of an entity
    and provides context for the mentions.
    """
    
    __tablename__ = "entity_mentions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    
    # Entity being mentioned
    entity_id = Column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Document and chunk where mentioned
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chunks.id", ondelete="CASCADE"),
        nullable=True,
    )
    
    # Mention details
    mention_text = Column(String(500), nullable=False)  # Exact text as it appears
    start_offset = Column(Integer, nullable=True)  # Character offset in chunk
    end_offset = Column(Integer, nullable=True)
    
    # Context around mention
    context = Column(Text, nullable=True)  # Surrounding text for context
    
    # Confidence
    confidence = Column(Float, default=1.0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    entity = relationship("Entity", back_populates="mentions")
    document = relationship("Document")
    chunk = relationship("Chunk")
    
    __table_args__ = (
        Index('ix_mention_entity_doc', 'entity_id', 'document_id'),
    )
    
    def __repr__(self) -> str:
        return f"<EntityMention(id={self.id}, entity={self.entity_id}, text={self.mention_text})>"


class KnowledgeTriple(Base):
    """Stores knowledge triples (subject, predicate, object).
    
    A simplified representation of facts extracted from documents
    that can be used for question answering.
    """
    
    __tablename__ = "knowledge_triples"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    
    # Triple components
    subject = Column(String(500), nullable=False, index=True)
    predicate = Column(String(200), nullable=False, index=True)
    object = Column(String(500), nullable=False, index=True)
    
    # Normalized versions for matching
    subject_normalized = Column(String(500), nullable=False, index=True)
    predicate_normalized = Column(String(200), nullable=False, index=True)
    object_normalized = Column(String(500), nullable=False, index=True)
    
    # Source
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    chunk_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chunks.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Original sentence/context
    source_text = Column(Text, nullable=True)
    
    # Confidence and extraction
    confidence = Column(Float, default=1.0)
    extraction_method = Column(String(50), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    document = relationship("Document")
    chunk = relationship("Chunk")
    
    __table_args__ = (
        Index('ix_triple_subject_pred', 'subject_normalized', 'predicate_normalized'),
        Index('ix_triple_object', 'object_normalized'),
    )
    
    def __repr__(self) -> str:
        return f"<KnowledgeTriple(s={self.subject}, p={self.predicate}, o={self.object})>"