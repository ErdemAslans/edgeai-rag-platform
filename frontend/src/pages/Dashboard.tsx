import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';
import { FileText, MessageSquare, Bot, Clock } from 'lucide-react';
import PageContainer from '@/components/layout/PageContainer';
import Header from '@/components/layout/Header';
import Card from '@/components/ui/Card';
import Spinner from '@/components/ui/Spinner';
import { getDashboard, DashboardStats, RecentActivity } from '@/api/dashboard';

const Dashboard = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const [stats, setStats] = useState<DashboardStats>({
    total_documents: 0,
    queries_today: 0,
    active_agents: 0,
    avg_response_time: 0,
  });
  const [recentActivity, setRecentActivity] = useState<RecentActivity[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        const data = await getDashboard();
        setStats(data.stats);
        setRecentActivity(data.recent_activity);
        setError(null);
      } catch (err) {
        console.error('Failed to fetch dashboard:', err);
        setError('Failed to load dashboard data');
        setStats({
          total_documents: 0,
          queries_today: 0,
          active_agents: 4,
          avg_response_time: 0,
        });
        setRecentActivity([]);
      } finally {
        setIsLoading(false);
      }
    };

    fetchDashboard();
  }, []);

  const statCards = [
    {
      title: 'Total Documents',
      value: stats.total_documents,
      icon: FileText,
      color: 'text-accent',
    },
    {
      title: 'Queries Today',
      value: stats.queries_today,
      icon: MessageSquare,
      color: 'text-success',
    },
    {
      title: 'Active Agents',
      value: stats.active_agents,
      icon: Bot,
      color: 'text-text-primary',
    },
    {
      title: 'Avg Response Time',
      value: `${stats.avg_response_time}s`,
      icon: Clock,
      color: 'text-text-secondary',
    },
  ];

  if (isLoading) {
    return (
      <PageContainer>
        <div className="flex items-center justify-center h-96">
          <Spinner size="lg" />
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <Header
        title={`Welcome back, ${user?.full_name || 'User'}`}
        subtitle="Here's what's happening with your RAG platform today"
      />

      {error && (
        <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded-md">
          <p className="text-sm text-yellow-800">{error}</p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {statCards.map((stat, index) => {
          const Icon = stat.icon;
          return (
            <Card key={index} className="p-6">
              <div className="flex items-center justify-between mb-4">
                <div className={`p-2 bg-gray-100 rounded-md ${stat.color}`}>
                  <Icon className="w-6 h-6" />
                </div>
              </div>
              <div>
                <p className="text-sm text-text-secondary">{stat.title}</p>
                <p className="text-2xl font-semibold text-text-primary mt-1">
                  {stat.value}
                </p>
              </div>
            </Card>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="p-6">
          <h3 className="text-lg font-semibold text-text-primary mb-4">
            Recent Activity
          </h3>
          {recentActivity.length === 0 ? (
            <p className="text-text-secondary text-sm">No recent activity</p>
          ) : (
            <div className="space-y-4">
              {recentActivity.map((activity) => (
                <div
                  key={activity.id}
                  className="flex items-start gap-3 pb-4 border-b border-border last:border-0 last:pb-0"
                >
                  <div className="flex-shrink-0">
                    {activity.type === 'upload' && <FileText className="w-5 h-5 text-accent" />}
                    {activity.type === 'query' && <MessageSquare className="w-5 h-5 text-success" />}
                    {activity.type === 'agent_execution' && <Bot className="w-5 h-5 text-text-primary" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-text-primary">
                      {activity.description}
                    </p>
                    <p className="text-xs text-text-secondary mt-1">
                      {new Date(activity.timestamp).toLocaleString()}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card className="p-6">
          <h3 className="text-lg font-semibold text-text-primary mb-4">
            Quick Actions
          </h3>
          <div className="space-y-3">
            <button
              onClick={() => navigate('/documents')}
              className="w-full text-left p-4 border border-border rounded-md hover:bg-gray-50 transition-colors"
            >
              <div className="flex items-center gap-3">
                <FileText className="w-5 h-5 text-accent" />
                <div>
                  <p className="font-medium text-text-primary">Upload New Document</p>
                  <p className="text-sm text-text-secondary">Add PDF, TXT, or Excel files</p>
                </div>
              </div>
            </button>
            <button
              onClick={() => navigate('/chat')}
              className="w-full text-left p-4 border border-border rounded-md hover:bg-gray-50 transition-colors"
            >
              <div className="flex items-center gap-3">
                <MessageSquare className="w-5 h-5 text-success" />
                <div>
                  <p className="font-medium text-text-primary">Start New Chat</p>
                  <p className="text-sm text-text-secondary">Ask questions about your documents</p>
                </div>
              </div>
            </button>
            <button
              onClick={() => navigate('/agents')}
              className="w-full text-left p-4 border border-border rounded-md hover:bg-gray-50 transition-colors"
            >
              <div className="flex items-center gap-3">
                <Bot className="w-5 h-5 text-text-primary" />
                <div>
                  <p className="font-medium text-text-primary">Execute Agent</p>
                  <p className="text-sm text-text-secondary">Run specialized AI agents</p>
                </div>
              </div>
            </button>
          </div>
        </Card>
      </div>
    </PageContainer>
  );
};

export default Dashboard;
