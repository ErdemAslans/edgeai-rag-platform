/**
 * Learning Analytics Dashboard Page
 * Displays adaptive learning insights and agent performance metrics
 */

import React, { useState, useEffect } from 'react';
import { getLearningAnalytics, getFeedbackSummary, getRoutingWeights, type LearningAnalytics, type FeedbackSummary, type RoutingWeights } from '../api/feedback';
import Card from '../components/ui/Card';
import Spinner from '../components/ui/Spinner';

const LearningAnalyticsPage: React.FC = () => {
  const [analytics, setAnalytics] = useState<LearningAnalytics | null>(null);
  const [summary, setSummary] = useState<FeedbackSummary | null>(null);
  const [weights, setWeights] = useState<RoutingWeights | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(30);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const [analyticsData, summaryData, weightsData] = await Promise.all([
          getLearningAnalytics(days),
          getFeedbackSummary(7),
          getRoutingWeights(),
        ]);
        setAnalytics(analyticsData);
        setSummary(summaryData);
        setWeights(weightsData);
      } catch (err) {
        console.error('Failed to fetch analytics:', err);
        setError('Analitik veriler yüklenemedi');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [days]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <p className="text-red-500 text-lg">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Tekrar Dene
          </button>
        </div>
      </div>
    );
  }

  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'improving':
        return <span className="text-green-500">↑</span>;
      case 'declining':
        return <span className="text-red-500">↓</span>;
      default:
        return <span className="text-gray-500">→</span>;
    }
  };

  const getImpactBadge = (impact: string) => {
    const colors = {
      high: 'bg-red-100 text-red-800',
      medium: 'bg-yellow-100 text-yellow-800',
      low: 'bg-green-100 text-green-800',
    };
    return colors[impact as keyof typeof colors] || colors.low;
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Öğrenme Analitiği</h1>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
        >
          <option value={7}>Son 7 gün</option>
          <option value={30}>Son 30 gün</option>
          <option value={90}>Son 90 gün</option>
        </select>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <Card className="p-6">
          <h3 className="text-sm font-medium text-gray-500">Toplam Geri Bildirim</h3>
          <p className="text-3xl font-bold text-gray-900 mt-2">
            {analytics?.total_feedback_count || 0}
          </p>
        </Card>
        <Card className="p-6">
          <h3 className="text-sm font-medium text-gray-500">Memnuniyet Oranı</h3>
          <p className="text-3xl font-bold text-gray-900 mt-2">
            {((analytics?.positive_rate || 0) * 100).toFixed(1)}%
          </p>
        </Card>
        <Card className="p-6">
          <h3 className="text-sm font-medium text-gray-500">Aktif Kalıplar</h3>
          <p className="text-3xl font-bold text-gray-900 mt-2">
            {analytics?.active_patterns_count || 0}
          </p>
        </Card>
        <Card className="p-6">
          <h3 className="text-sm font-medium text-gray-500">Trend</h3>
          <p className="text-3xl font-bold text-gray-900 mt-2 flex items-center gap-2">
            {getTrendIcon(summary?.trend || 'stable')}
            <span className="capitalize">{summary?.trend || 'stable'}</span>
          </p>
        </Card>
      </div>

      {/* Agent Performance */}
      <Card className="p-6 mb-8">
        <h2 className="text-xl font-semibold mb-4">Agent Performansı</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Agent
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Toplam
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Pozitif
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Negatif
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Memnuniyet
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Yönlendirme Ağırlığı
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {analytics?.agents_performance.map((agent) => (
                <tr key={agent.agent_name} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    {agent.agent_name}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {agent.total_feedback}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-green-600">
                    {agent.positive_feedback}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-red-600">
                    {agent.negative_feedback}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    <div className="flex items-center">
                      <div className="w-16 bg-gray-200 rounded-full h-2 mr-2">
                        <div
                          className="bg-blue-600 h-2 rounded-full"
                          style={{ width: `${agent.satisfaction_rate * 100}%` }}
                        />
                      </div>
                      {(agent.satisfaction_rate * 100).toFixed(0)}%
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {(weights?.weights[agent.agent_name] || 1).toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Insights */}
      <Card className="p-6 mb-8">
        <h2 className="text-xl font-semibold mb-4">Öğrenme İçgörüleri</h2>
        {analytics?.insights && analytics.insights.length > 0 ? (
          <div className="space-y-4">
            {analytics.insights.map((insight, index) => (
              <div
                key={index}
                className="border rounded-lg p-4 hover:shadow-md transition-shadow"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-medium text-gray-900">{insight.title}</h3>
                    <p className="text-sm text-gray-600 mt-1">{insight.description}</p>
                    <p className="text-sm text-blue-600 mt-2">
                      💡 {insight.recommendation}
                    </p>
                  </div>
                  <span
                    className={`px-2 py-1 text-xs font-medium rounded ${getImpactBadge(
                      insight.impact
                    )}`}
                  >
                    {insight.impact === 'high'
                      ? 'Yüksek Etki'
                      : insight.impact === 'medium'
                      ? 'Orta Etki'
                      : 'Düşük Etki'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-500 text-center py-8">
            Henüz yeterli veri yok. Daha fazla geri bildirim toplandıkça içgörüler
            görünecek.
          </p>
        )}
      </Card>

      {/* Category Breakdown */}
      {summary && Object.keys(summary.by_category).length > 0 && (
        <Card className="p-6">
          <h2 className="text-xl font-semibold mb-4">Negatif Geri Bildirim Kategorileri</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {Object.entries(summary.by_category).map(([category, count]) => (
              <div key={category} className="bg-gray-50 rounded-lg p-4 text-center">
                <p className="text-2xl font-bold text-gray-900">{count}</p>
                <p className="text-sm text-gray-600 capitalize">
                  {category.replace('_', ' ')}
                </p>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
};

export default LearningAnalyticsPage;