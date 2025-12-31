/**
 * Knowledge Graph Explorer Page
 * 
 * Provides:
 * - Graph visualization
 * - Entity search
 * - Question answering
 * - Entity extraction from documents
 */

import React, { useState, useEffect, useCallback } from 'react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Spinner from '../components/ui/Spinner';
import Badge from '../components/ui/Badge';
import Input from '../components/ui/Input';
import {
  queryKnowledgeGraph,
  askQuestion,
  searchEntities,
  getEntitySubgraph,
  getKnowledgeGraphStats,
  GraphQueryResponse,
  QuestionResponse,
  EntityResponse,
  SubgraphResponse,
  KnowledgeGraphStats,
} from '../api/knowledgeGraph';

// Simple force-directed graph visualization
const GraphVisualization: React.FC<{ data: SubgraphResponse }> = ({ data }) => {
  if (!data.nodes.length) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-500">
        No graph data to display
      </div>
    );
  }

  // Simple circle layout for nodes
  const nodePositions: Record<string, { x: number; y: number }> = {};
  const centerX = 200;
  const centerY = 150;
  const radius = 100;
  
  data.nodes.forEach((node, index) => {
    const angle = (2 * Math.PI * index) / data.nodes.length;
    nodePositions[node.id] = {
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle),
    };
  });

  const getNodeColor = (type: string) => {
    const colors: Record<string, string> = {
      person: '#3B82F6',
      organization: '#10B981',
      location: '#F59E0B',
      concept: '#8B5CF6',
      product: '#EC4899',
      technology: '#06B6D4',
      event: '#EF4444',
      date: '#6B7280',
      other: '#9CA3AF',
    };
    return colors[type] || colors.other;
  };

  return (
    <svg viewBox="0 0 400 300" className="w-full h-64">
      {/* Edges */}
      {data.edges.map((edge, index) => {
        const source = nodePositions[edge.source];
        const target = nodePositions[edge.target];
        if (!source || !target) return null;
        
        const midX = (source.x + target.x) / 2;
        const midY = (source.y + target.y) / 2;
        
        return (
          <g key={index}>
            <line
              x1={source.x}
              y1={source.y}
              x2={target.x}
              y2={target.y}
              stroke="#E5E7EB"
              strokeWidth="2"
            />
            <text
              x={midX}
              y={midY - 5}
              textAnchor="middle"
              fontSize="8"
              fill="#6B7280"
            >
              {edge.relation}
            </text>
          </g>
        );
      })}
      
      {/* Nodes */}
      {data.nodes.map((node) => {
        const pos = nodePositions[node.id];
        if (!pos) return null;
        
        return (
          <g key={node.id}>
            <circle
              cx={pos.x}
              cy={pos.y}
              r="20"
              fill={getNodeColor(node.type)}
              className="cursor-pointer hover:opacity-80"
            />
            <text
              x={pos.x}
              y={pos.y + 35}
              textAnchor="middle"
              fontSize="10"
              fill="#374151"
            >
              {node.name.length > 15 ? node.name.substring(0, 15) + '...' : node.name}
            </text>
            <text
              x={pos.x}
              y={pos.y + 4}
              textAnchor="middle"
              fontSize="8"
              fill="white"
            >
              {node.type.substring(0, 3).toUpperCase()}
            </text>
          </g>
        );
      })}
    </svg>
  );
};

const KnowledgeGraph: React.FC = () => {
  // State
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<KnowledgeGraphStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<EntityResponse[]>([]);
  const [searching, setSearching] = useState(false);
  
  // Graph state
  const [selectedEntity, setSelectedEntity] = useState<EntityResponse | null>(null);
  const [graphData, setGraphData] = useState<SubgraphResponse | null>(null);
  const [graphDepth, setGraphDepth] = useState(1);
  
  // Question state
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState<QuestionResponse | null>(null);
  const [askingQuestion, setAskingQuestion] = useState(false);
  
  // Tab state
  const [activeTab, setActiveTab] = useState<'explore' | 'qa' | 'stats'>('explore');

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      setLoading(true);
      const data = await getKnowledgeGraphStats();
      setStats(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load stats');
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    
    try {
      setSearching(true);
      const results = await searchEntities(searchQuery);
      setSearchResults(results);
    } catch (err) {
      setError('Search failed');
    } finally {
      setSearching(false);
    }
  };

  const handleSelectEntity = async (entity: EntityResponse) => {
    setSelectedEntity(entity);
    
    try {
      const graph = await getEntitySubgraph(entity.id, graphDepth);
      setGraphData(graph);
    } catch (err) {
      setError('Failed to load entity graph');
    }
  };

  const handleAskQuestion = async () => {
    if (!question.trim()) return;
    
    try {
      setAskingQuestion(true);
      setAnswer(null);
      const result = await askQuestion(question);
      setAnswer(result);
    } catch (err) {
      setError('Failed to get answer');
    } finally {
      setAskingQuestion(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Knowledge Graph</h1>
          <p className="text-gray-600">Explore entities, relations, and ask questions</p>
        </div>
        <div className="flex items-center gap-2">
          {stats && (
            <>
              <Badge variant="neutral">{stats.total_entities} Entities</Badge>
              <Badge variant="neutral">{stats.total_relations} Relations</Badge>
              <Badge variant="neutral">{stats.total_triples} Triples</Badge>
            </>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 text-red-600 p-4 rounded-lg">
          {error}
          <button onClick={() => setError(null)} className="ml-2 text-red-800">×</button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b">
        {(['explore', 'qa', 'stats'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 font-medium capitalize transition-colors ${
              activeTab === tab
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            {tab === 'qa' ? 'Q&A' : tab}
          </button>
        ))}
      </div>

      {/* Explore Tab */}
      {activeTab === 'explore' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Search Panel */}
          <Card className="p-4">
            <h3 className="font-semibold mb-4">Search Entities</h3>
            <div className="flex gap-2 mb-4">
              <Input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search entities..."
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              />
              <Button onClick={handleSearch} disabled={searching}>
                {searching ? <Spinner size="sm" /> : 'Search'}
              </Button>
            </div>
            
            {/* Search Results */}
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {searchResults.map((entity) => (
                <div
                  key={entity.id}
                  onClick={() => handleSelectEntity(entity)}
                  className={`p-3 rounded-lg cursor-pointer transition-colors ${
                    selectedEntity?.id === entity.id
                      ? 'bg-blue-50 border border-blue-200'
                      : 'bg-gray-50 hover:bg-gray-100'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{entity.name}</span>
                    <Badge variant="neutral">{entity.entity_type}</Badge>
                  </div>
                  <div className="text-sm text-gray-500 mt-1">
                    {entity.mention_count} mentions • {entity.document_count} docs
                  </div>
                </div>
              ))}
              {searchResults.length === 0 && searchQuery && !searching && (
                <p className="text-gray-500 text-center py-4">No entities found</p>
              )}
            </div>
          </Card>

          {/* Graph Visualization */}
          <Card className="p-4 lg:col-span-2">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold">Entity Graph</h3>
              {selectedEntity && (
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-500">Depth:</span>
                  <select
                    value={graphDepth}
                    onChange={(e) => setGraphDepth(Number(e.target.value))}
                    className="border rounded px-2 py-1 text-sm"
                  >
                    <option value={1}>1 hop</option>
                    <option value={2}>2 hops</option>
                    <option value={3}>3 hops</option>
                  </select>
                  <Button
                    size="sm"
                    onClick={() => handleSelectEntity(selectedEntity)}
                  >
                    Refresh
                  </Button>
                </div>
              )}
            </div>
            
            {graphData ? (
              <GraphVisualization data={graphData} />
            ) : (
              <div className="flex items-center justify-center h-64 text-gray-500">
                Select an entity to view its graph
              </div>
            )}

            {/* Selected Entity Details */}
            {selectedEntity && (
              <div className="mt-4 p-4 bg-gray-50 rounded-lg">
                <h4 className="font-medium">{selectedEntity.name}</h4>
                <p className="text-sm text-gray-600 mt-1">
                  Type: {selectedEntity.entity_type}
                </p>
                {selectedEntity.description && (
                  <p className="text-sm text-gray-500 mt-2">
                    {selectedEntity.description}
                  </p>
                )}
              </div>
            )}
          </Card>
        </div>
      )}

      {/* Q&A Tab */}
      {activeTab === 'qa' && (
        <div className="space-y-6">
          <Card className="p-6">
            <h3 className="font-semibold mb-4">Ask a Question</h3>
            <p className="text-gray-600 mb-4">
              Ask questions about entities and relationships in your documents.
            </p>
            
            <div className="flex gap-2 mb-6">
              <Input
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="e.g., What is the relationship between X and Y?"
                onKeyDown={(e) => e.key === 'Enter' && handleAskQuestion()}
                className="flex-1"
              />
              <Button onClick={handleAskQuestion} disabled={askingQuestion}>
                {askingQuestion ? <Spinner size="sm" /> : 'Ask'}
              </Button>
            </div>

            {/* Answer */}
            {answer && (
              <div className="space-y-4">
                <div className="p-4 bg-blue-50 rounded-lg">
                  <h4 className="font-medium text-blue-800 mb-2">Answer</h4>
                  <p className="text-gray-800">{answer.answer}</p>
                  <div className="mt-2 flex items-center gap-2">
                    <span className="text-sm text-gray-500">Confidence:</span>
                    <Badge
                      variant={answer.confidence > 0.7 ? 'success' : answer.confidence > 0.4 ? 'warning' : 'error'}
                    >
                      {(answer.confidence * 100).toFixed(0)}%
                    </Badge>
                  </div>
                </div>

                {/* Sources */}
                {answer.sources && Object.keys(answer.sources).length > 0 && (
                  <div className="p-4 bg-gray-50 rounded-lg">
                    <h4 className="font-medium mb-2">Sources</h4>
                    
                    {answer.sources.entities && answer.sources.entities.length > 0 && (
                      <div className="mb-3">
                        <span className="text-sm text-gray-500">Entities:</span>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {answer.sources.entities.map((e, i) => (
                            <Badge key={i} variant="neutral">
                              {(e as { name?: string }).name || 'Unknown'}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                    
                    {answer.sources.relations && answer.sources.relations.length > 0 && (
                      <div className="mb-3">
                        <span className="text-sm text-gray-500">Relations:</span>
                        <div className="text-sm mt-1 space-y-1">
                          {answer.sources.relations.slice(0, 5).map((r, i) => (
                            <div key={i} className="text-gray-700">
                              {(r as { source?: string }).source} → 
                              <span className="text-blue-600 mx-1">{(r as { relation?: string }).relation}</span> → 
                              {(r as { target?: string }).target}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Example Questions */}
            <div className="mt-6">
              <h4 className="text-sm font-medium text-gray-500 mb-2">Example Questions</h4>
              <div className="flex flex-wrap gap-2">
                {[
                  'Who works at company X?',
                  'What technologies are mentioned?',
                  'What is the relationship between A and B?',
                ].map((q, i) => (
                  <button
                    key={i}
                    onClick={() => setQuestion(q)}
                    className="text-sm px-3 py-1 bg-gray-100 hover:bg-gray-200 rounded-full text-gray-700"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Stats Tab */}
      {activeTab === 'stats' && stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className="p-4">
            <h4 className="text-sm text-gray-500">Total Entities</h4>
            <p className="text-3xl font-bold mt-1">{stats.total_entities}</p>
          </Card>
          <Card className="p-4">
            <h4 className="text-sm text-gray-500">Total Relations</h4>
            <p className="text-3xl font-bold mt-1">{stats.total_relations}</p>
          </Card>
          <Card className="p-4">
            <h4 className="text-sm text-gray-500">Knowledge Triples</h4>
            <p className="text-3xl font-bold mt-1">{stats.total_triples}</p>
          </Card>
          <Card className="p-4">
            <h4 className="text-sm text-gray-500">Entity Types</h4>
            <p className="text-3xl font-bold mt-1">
              {Object.keys(stats.entities_by_type).length}
            </p>
          </Card>
          
          {/* Entities by Type */}
          <Card className="p-4 md:col-span-2">
            <h4 className="font-medium mb-4">Entities by Type</h4>
            <div className="space-y-2">
              {Object.entries(stats.entities_by_type)
                .sort(([, a], [, b]) => b - a)
                .map(([type, count]) => (
                  <div key={type} className="flex items-center justify-between">
                    <span className="capitalize">{type}</span>
                    <div className="flex items-center gap-2">
                      <div className="w-32 bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-blue-500 h-2 rounded-full"
                          style={{
                            width: `${(count / stats.total_entities) * 100}%`,
                          }}
                        />
                      </div>
                      <span className="text-sm text-gray-600 w-12 text-right">
                        {count}
                      </span>
                    </div>
                  </div>
                ))}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};

export default KnowledgeGraph;