/**
 * Advanced Analytics Dashboard Page
 * 
 * Provides comprehensive analytics including:
 * - Usage summary
 * - Query patterns
 * - Cost tracking
 * - Performance metrics
 * - Trending topics
 */

import React, { useState, useEffect } from 'react';
import Card from '../components/ui/Card';
import Spinner from '../components/ui/Spinner';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import {
  getDashboardData,
  getQueryPatterns,
  getCostTracking,
  downloadAnalyticsCSV,
  DashboardData,
  QueryPatterns,
  CostTracking,
} from '../api/analytics';

// Chart components (simplified - in production use recharts or chart.js)
const SimpleBarChart: React.FC<{ data: { label: string; value: number }[]; color?: string }> = ({ 
  data, 
  color = '#3B82F6' 
}) => {
  const maxValue = Math.max(...data.map(d => d.value), 1);
  
  return (
    <div className="space-y-2">
      {data.map((item, index) => (
        <div key={index} className="flex items-center gap-2">
          <span className="text-sm text-gray-600 w-20 truncate">{item.label}</span>
          <div className="flex-1 bg-gray-200 rounded-full h-4">
            <div
              className="h-4 rounded-full transition-all duration-300"
              style={{ 
                width: `${(item.value / maxValue) * 100}%`,
                backgroundColor: color 
              }}
            />
          </div>
          <span className="text-sm font-medium w-12 text-right">{item.value}</span>
        </div>
      ))}
    </div>
  );
};

const SimpleLineChart: React.FC<{ data: { date: string; value: number }[] }> = ({ data }) => {
  if (data.length === 0) return <div className="text-gray-500 text-center py-8">No data</div>;
  
  const maxValue = Math.max(...data.map(d => d.value), 1);
  const minValue = Math.min(...data.map(d => d.value), 0);
  const range = maxValue - minValue || 1;
  
  const points = data.map((d, i) => ({
    x: (i / (data.length - 1 || 1)) * 100,
    y: 100 - ((d.value - minValue) / range) * 100,
  }));
  
  const pathData = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
  
  return (
    <div className="relative h-48">
      <svg viewBox="0 0 100 100" className="w-full h-full" preserveAspectRatio="none">
        <path
          d={pathData}
          fill="none"
          stroke="#3B82F6"
          strokeWidth="2"
          vectorEffect="non-scaling-stroke"
        />
        {points.map((p, i) => (
          <circle
            key={i}
            cx={p.x}
            cy={p.y}
            r="2"
            fill="#3B82F6"
            vectorEffect="non-scaling-stroke"
          />
        ))}
      </svg>
      <div className="absolute bottom-0 left-0 right-0 flex justify-between text-xs text-gray-500">
        <span>{data[0]?.date}</span>
        <span>{data[data.length - 1]?.date}</span>
      </div>
    </div>
  );
};

const MetricCard: React.FC<{
  title: string;
  value: string | number;
  subtitle?: string;
  trend?: 'up' | 'down' | 'stable';
  icon?: React.ReactNode;
}> = ({ title, value, subtitle, trend, icon }) => (
  <Card className="p-4">
    <div className="flex items-start justify-between">
      <div>
        <p className="text-sm text-gray-600">{title}</p>
        <p className="text-2xl font-bold mt-1">{value}</p>
        {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-2">
        {trend && (
          <span className={`text-sm ${
            trend === 'up' ? 'text-green-500' : 
            trend === 'down' ? 'text-red-500' : 
            'text-gray-500'
          }`}>
            {trend === 'up' ? '↑' : trend === 'down' ? '↓' : '→'}
          </span>
        )}
        {icon}
      </div>
    </div>
  </Card>
);

const AdvancedAnalytics: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [queryPatterns, setQueryPatterns] = useState<QueryPatterns | null>(null);
  const [costData, setCostData] = useState<CostTracking | null>(null);
  const [selectedPeriod, setSelectedPeriod] = useState(30);
  const [activeTab, setActiveTab] = useState<'overview' | 'queries' | 'costs' | 'performance'>('overview');
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    loadData();
  }, [selectedPeriod]);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const [dashboard, patterns, costs] = await Promise.all([
        getDashboardData(),
        getQueryPatterns(selectedPeriod),
        getCostTracking(selectedPeriod),
      ]);
      
      setDashboardData(dashboard);
      setQueryPatterns(patterns);
      setCostData(costs);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load analytics');
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async () => {
    try {
      setExporting(true);
      await downloadAnalyticsCSV(selectedPeriod);
    } catch (err) {
      setError('Failed to export analytics');
    } finally {
      setExporting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-96">
        <p className="text-red-500 mb-4">{error}</p>
        <Button onClick={loadData}>Retry</Button>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Advanced Analytics</h1>
          <p className="text-gray-600">Comprehensive usage and performance metrics</p>
        </div>
        <div className="flex items-center gap-4">
          <select
            value={selectedPeriod}
            onChange={(e) => setSelectedPeriod(Number(e.target.value))}
            className="border rounded-lg px-3 py-2"
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
            <option value={365}>Last year</option>
          </select>
          <Button onClick={handleExport} disabled={exporting}>
            {exporting ? 'Exporting...' : 'Export CSV'}
          </Button>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-2 border-b">
        {(['overview', 'queries', 'costs', 'performance'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 font-medium capitalize transition-colors ${
              activeTab === tab
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Overview Tab */}
      {activeTab === 'overview' && dashboardData && (
        <div className="space-y-6">
          {/* Key Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard
              title="Total Queries"
              value={dashboardData.usage.total_queries.toLocaleString()}
              subtitle={`${dashboardData.usage.avg_tokens_per_query.toFixed(0)} avg tokens`}
            />
            <MetricCard
              title="Response Time"
              value={`${dashboardData.usage.avg_response_time_ms.toFixed(0)}ms`}
              subtitle="Average"
            />
            <MetricCard
              title="Satisfaction Rate"
              value={`${(dashboardData.performance.satisfaction_rate * 100).toFixed(1)}%`}
              trend={dashboardData.performance.satisfaction_rate > 0.8 ? 'up' : 'down'}
            />
            <MetricCard
              title="Estimated Cost"
              value={`$${dashboardData.usage.estimated_cost.toFixed(2)}`}
              subtitle="This period"
            />
          </div>

          {/* Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card className="p-4">
              <h3 className="font-semibold mb-4">Daily Query Volume</h3>
              <SimpleLineChart
                data={dashboardData.usage.daily_queries.map(d => ({
                  date: d.date,
                  value: d.count,
                }))}
              />
            </Card>
            
            <Card className="p-4">
              <h3 className="font-semibold mb-4">Queries by Agent</h3>
              <SimpleBarChart
                data={dashboardData.usage.queries_by_agent.map(a => ({
                  label: a.agent,
                  value: a.count,
                }))}
              />
            </Card>
          </div>

          {/* Trending Topics */}
          <Card className="p-4">
            <h3 className="font-semibold mb-4">Trending Topics</h3>
            <div className="flex flex-wrap gap-2">
              {dashboardData.trending.map((topic, index) => (
                <Badge
                  key={index}
                  variant={topic.trend === 'up' ? 'success' : topic.trend === 'down' ? 'error' : 'neutral'}
                >
                  {topic.topic}
                  <span className="ml-1 text-xs">
                    {topic.trend === 'up' ? '↑' : topic.trend === 'down' ? '↓' : '→'}
                    {(topic.growth_rate * 100).toFixed(0)}%
                  </span>
                </Badge>
              ))}
            </div>
          </Card>

          {/* Document Stats */}
          <Card className="p-4">
            <h3 className="font-semibold mb-4">Document Statistics</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <p className="text-sm text-gray-600">Total Documents</p>
                <p className="text-xl font-bold">{dashboardData.document_stats.total_documents}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Total Chunks</p>
                <p className="text-xl font-bold">{dashboardData.document_stats.total_chunks}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Avg Chunks/Doc</p>
                <p className="text-xl font-bold">{dashboardData.document_stats.avg_chunks_per_document.toFixed(1)}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">By Type</p>
                <div className="flex flex-wrap gap-1 mt-1">
                  {dashboardData.document_stats.documents_by_type.slice(0, 3).map((t, i) => (
                    <Badge key={i} variant="neutral" className="text-xs">
                      {t.type}: {t.count}
                    </Badge>
                  ))}
                </div>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Queries Tab */}
      {activeTab === 'queries' && queryPatterns && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card className="p-4">
              <h3 className="font-semibold mb-4">Top Keywords</h3>
              <SimpleBarChart
                data={queryPatterns.top_keywords.slice(0, 10).map(k => ({
                  label: k.keyword,
                  value: k.count,
                }))}
                color="#10B981"
              />
            </Card>
            
            <Card className="p-4">
              <h3 className="font-semibold mb-4">Query Types</h3>
              <SimpleBarChart
                data={Object.entries(queryPatterns.query_type_distribution).map(([type, count]) => ({
                  label: type,
                  value: count,
                }))}
                color="#8B5CF6"
              />
            </Card>
          </div>

          <Card className="p-4">
            <h3 className="font-semibold mb-4">Time Patterns</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <h4 className="text-sm font-medium text-gray-600 mb-2">By Hour of Day</h4>
                <SimpleBarChart
                  data={Object.entries(queryPatterns.time_patterns.by_hour)
                    .sort(([a], [b]) => parseInt(a) - parseInt(b))
                    .map(([hour, count]) => ({
                      label: `${hour}:00`,
                      value: count,
                    }))}
                  color="#F59E0B"
                />
              </div>
              <div>
                <h4 className="text-sm font-medium text-gray-600 mb-2">By Day of Week</h4>
                <SimpleBarChart
                  data={Object.entries(queryPatterns.time_patterns.by_day_of_week).map(([day, count]) => ({
                    label: day.substring(0, 3),
                    value: count,
                  }))}
                  color="#EC4899"
                />
              </div>
            </div>
            <div className="mt-4 flex gap-4 text-sm">
              <span className="text-gray-600">
                Peak Hour: <strong>{queryPatterns.time_patterns.peak_hour}:00</strong>
              </span>
              <span className="text-gray-600">
                Peak Day: <strong>{queryPatterns.time_patterns.peak_day}</strong>
              </span>
            </div>
          </Card>
        </div>
      )}

      {/* Costs Tab */}
      {activeTab === 'costs' && costData && (
        <div className="space-y-6">
          {/* Cost Summary */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <MetricCard
              title="Total Cost"
              value={`$${costData.total_cost.toFixed(2)}`}
              subtitle={`${costData.total_tokens.toLocaleString()} tokens`}
            />
            <MetricCard
              title="Projected Monthly"
              value={`$${costData.projected_monthly_cost.toFixed(2)}`}
              subtitle="Based on current usage"
            />
            <MetricCard
              title="Daily Average"
              value={`$${(costData.total_cost / costData.period_days).toFixed(2)}`}
              subtitle="Per day"
            />
          </div>

          {/* Daily Costs Chart */}
          <Card className="p-4">
            <h3 className="font-semibold mb-4">Daily Costs</h3>
            <SimpleLineChart
              data={costData.daily_costs.map(d => ({
                date: d.date,
                value: d.cost,
              }))}
            />
          </Card>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Cost by Agent */}
            <Card className="p-4">
              <h3 className="font-semibold mb-4">Cost by Agent</h3>
              <div className="space-y-3">
                {costData.cost_by_agent.map((agent, index) => (
                  <div key={index} className="flex items-center justify-between">
                    <span className="text-gray-700">{agent.agent}</span>
                    <div className="text-right">
                      <span className="font-medium">${agent.cost.toFixed(2)}</span>
                      <span className="text-gray-500 text-sm ml-2">
                        ({agent.tokens.toLocaleString()} tokens)
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </Card>

            {/* Cost Breakdown */}
            <Card className="p-4">
              <h3 className="font-semibold mb-4">Cost Breakdown</h3>
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between mb-1">
                    <span className="text-gray-600">LLM Inference</span>
                    <span className="font-medium">${costData.cost_breakdown.llm_inference.toFixed(2)}</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-blue-500 h-2 rounded-full"
                      style={{ width: `${(costData.cost_breakdown.llm_inference / costData.total_cost) * 100}%` }}
                    />
                  </div>
                </div>
                <div>
                  <div className="flex justify-between mb-1">
                    <span className="text-gray-600">Embeddings</span>
                    <span className="font-medium">${costData.cost_breakdown.embeddings.toFixed(2)}</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-green-500 h-2 rounded-full"
                      style={{ width: `${(costData.cost_breakdown.embeddings / costData.total_cost) * 100}%` }}
                    />
                  </div>
                </div>
                <div>
                  <div className="flex justify-between mb-1">
                    <span className="text-gray-600">Other</span>
                    <span className="font-medium">${costData.cost_breakdown.other.toFixed(2)}</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-purple-500 h-2 rounded-full"
                      style={{ width: `${(costData.cost_breakdown.other / costData.total_cost) * 100}%` }}
                    />
                  </div>
                </div>
              </div>
            </Card>
          </div>
        </div>
      )}

      {/* Performance Tab */}
      {activeTab === 'performance' && dashboardData && (
        <div className="space-y-6">
          {/* Performance Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard
              title="Availability"
              value={`${(dashboardData.performance.availability * 100).toFixed(2)}%`}
              trend={dashboardData.performance.availability > 0.99 ? 'up' : 'down'}
            />
            <MetricCard
              title="Error Rate"
              value={`${(dashboardData.performance.error_rate * 100).toFixed(2)}%`}
              trend={dashboardData.performance.error_rate < 0.01 ? 'up' : 'down'}
            />
            <MetricCard
              title="Cache Hit Rate"
              value={`${(dashboardData.performance.cache_hit_rate * 100).toFixed(1)}%`}
              trend={dashboardData.performance.cache_hit_rate > 0.5 ? 'up' : 'down'}
            />
            <MetricCard
              title="Satisfaction"
              value={`${(dashboardData.performance.satisfaction_rate * 100).toFixed(1)}%`}
              trend={dashboardData.performance.satisfaction_rate > 0.8 ? 'up' : 'down'}
            />
          </div>

          {/* Response Time Percentiles */}
          <Card className="p-4">
            <h3 className="font-semibold mb-4">Response Time Percentiles</h3>
            <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
              <div className="text-center">
                <p className="text-sm text-gray-600">Min</p>
                <p className="text-xl font-bold">{dashboardData.performance.response_time_percentiles.min.toFixed(0)}ms</p>
              </div>
              <div className="text-center">
                <p className="text-sm text-gray-600">P50</p>
                <p className="text-xl font-bold">{dashboardData.performance.response_time_percentiles.p50.toFixed(0)}ms</p>
              </div>
              <div className="text-center">
                <p className="text-sm text-gray-600">Average</p>
                <p className="text-xl font-bold">{dashboardData.performance.response_time_percentiles.avg.toFixed(0)}ms</p>
              </div>
              <div className="text-center">
                <p className="text-sm text-gray-600">P90</p>
                <p className="text-xl font-bold">{dashboardData.performance.response_time_percentiles.p90.toFixed(0)}ms</p>
              </div>
              <div className="text-center">
                <p className="text-sm text-gray-600">P99</p>
                <p className="text-xl font-bold">{dashboardData.performance.response_time_percentiles.p99.toFixed(0)}ms</p>
              </div>
              <div className="text-center">
                <p className="text-sm text-gray-600">Max</p>
                <p className="text-xl font-bold">{dashboardData.performance.response_time_percentiles.max.toFixed(0)}ms</p>
              </div>
            </div>
          </Card>

          {/* Performance Tips */}
          <Card className="p-4">
            <h3 className="font-semibold mb-4">Performance Insights</h3>
            <div className="space-y-3">
              {dashboardData.performance.cache_hit_rate < 0.5 && (
                <div className="flex items-start gap-3 p-3 bg-yellow-50 rounded-lg">
                  <span className="text-yellow-500">⚠️</span>
                  <div>
                    <p className="font-medium text-yellow-800">Low Cache Hit Rate</p>
                    <p className="text-sm text-yellow-700">
                      Your cache hit rate is below 50%. Consider adjusting cache TTL or query patterns.
                    </p>
                  </div>
                </div>
              )}
              {dashboardData.performance.error_rate > 0.05 && (
                <div className="flex items-start gap-3 p-3 bg-red-50 rounded-lg">
                  <span className="text-red-500">❌</span>
                  <div>
                    <p className="font-medium text-red-800">High Error Rate</p>
                    <p className="text-sm text-red-700">
                      Error rate is above 5%. Review error logs for common failure patterns.
                    </p>
                  </div>
                </div>
              )}
              {dashboardData.performance.response_time_percentiles.p90 > 5000 && (
                <div className="flex items-start gap-3 p-3 bg-orange-50 rounded-lg">
                  <span className="text-orange-500">🐢</span>
                  <div>
                    <p className="font-medium text-orange-800">Slow P90 Response Time</p>
                    <p className="text-sm text-orange-700">
                      10% of queries take more than 5 seconds. Consider query optimization.
                    </p>
                  </div>
                </div>
              )}
              {dashboardData.performance.error_rate < 0.01 &&
                dashboardData.performance.cache_hit_rate > 0.5 &&
                dashboardData.performance.response_time_percentiles.p90 < 5000 && (
                <div className="flex items-start gap-3 p-3 bg-green-50 rounded-lg">
                  <span className="text-green-500">✅</span>
                  <div>
                    <p className="font-medium text-green-800">System Health: Good</p>
                    <p className="text-sm text-green-700">
                      All performance metrics are within healthy ranges.
                    </p>
                  </div>
                </div>
              )}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};

export default AdvancedAnalytics;