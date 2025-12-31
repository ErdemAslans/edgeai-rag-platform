/**
 * Knowledge Graph API client
 */

import apiClient from './client';

// Types
export interface EntityResponse {
  id: string;
  name: string;
  entity_type: string;
  description: string | null;
  mention_count: number;
  document_count: number;
}

export interface RelationResponse {
  source: string;
  relation: string;
  target: string;
  bidirectional: boolean;
}

export interface TripleResponse {
  subject: string;
  predicate: string;
  object: string;
  confidence: number;
}

export interface GraphNode {
  id: string;
  name: string;
  type: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  relation: string;
}

export interface SubgraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface GraphQueryResponse {
  query: string;
  query_entities: string[];
  matched_entities: Record<string, unknown>[];
  relations: Record<string, unknown>[];
  triples: Record<string, unknown>[];
}

export interface QuestionResponse {
  question: string;
  answer: string;
  confidence: number;
  sources: {
    entities?: Record<string, unknown>[];
    relations?: Record<string, unknown>[];
    triples?: Record<string, unknown>[];
  };
}

export interface ExtractEntitiesResponse {
  document_id: string;
  entities_count: number;
  relations_count: number;
  triples_count: number;
  status: string;
}

export interface KnowledgeGraphStats {
  total_entities: number;
  entities_by_type: Record<string, number>;
  total_relations: number;
  total_triples: number;
}

// API Functions

/**
 * Query the knowledge graph with natural language
 */
export async function queryKnowledgeGraph(
  query: string,
  maxHops: number = 2,
  topK: number = 10
): Promise<GraphQueryResponse> {
  const response = await apiClient.post<GraphQueryResponse>(
    '/knowledge-graph/query',
    { query, max_hops: maxHops, top_k: topK }
  );
  return response.data;
}

/**
 * Ask a question and get an answer from the knowledge graph
 */
export async function askQuestion(question: string): Promise<QuestionResponse> {
  const response = await apiClient.post<QuestionResponse>(
    '/knowledge-graph/ask',
    { question }
  );
  return response.data;
}

/**
 * Search for entities
 */
export async function searchEntities(
  query: string,
  entityType?: string,
  limit: number = 20
): Promise<EntityResponse[]> {
  const response = await apiClient.get<EntityResponse[]>(
    '/knowledge-graph/entities',
    { params: { query, entity_type: entityType, limit } }
  );
  return response.data;
}

/**
 * Get entity by ID
 */
export async function getEntity(entityId: string): Promise<EntityResponse> {
  const response = await apiClient.get<EntityResponse>(
    `/knowledge-graph/entities/${entityId}`
  );
  return response.data;
}

/**
 * Get subgraph around an entity
 */
export async function getEntitySubgraph(
  entityId: string,
  depth: number = 1
): Promise<SubgraphResponse> {
  const response = await apiClient.get<SubgraphResponse>(
    `/knowledge-graph/entities/${entityId}/graph`,
    { params: { depth } }
  );
  return response.data;
}

/**
 * Get relations for an entity
 */
export async function getEntityRelations(
  entityId: string
): Promise<RelationResponse[]> {
  const response = await apiClient.get<RelationResponse[]>(
    `/knowledge-graph/entities/${entityId}/relations`
  );
  return response.data;
}

/**
 * Extract entities from a document
 */
export async function extractEntities(
  documentId: string
): Promise<ExtractEntitiesResponse> {
  const response = await apiClient.post<ExtractEntitiesResponse>(
    '/knowledge-graph/extract',
    { document_id: documentId }
  );
  return response.data;
}

/**
 * Get knowledge graph statistics
 */
export async function getKnowledgeGraphStats(): Promise<KnowledgeGraphStats> {
  const response = await apiClient.get<KnowledgeGraphStats>(
    '/knowledge-graph/stats'
  );
  return response.data;
}

/**
 * Get available entity types
 */
export async function getEntityTypes(): Promise<string[]> {
  const response = await apiClient.get<string[]>(
    '/knowledge-graph/entity-types'
  );
  return response.data;
}

/**
 * Get available relation types
 */
export async function getRelationTypes(): Promise<string[]> {
  const response = await apiClient.get<string[]>(
    '/knowledge-graph/relation-types'
  );
  return response.data;
}