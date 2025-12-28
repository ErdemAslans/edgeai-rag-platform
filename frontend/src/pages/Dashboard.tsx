import { useEffect, useState } from 'react';
import { useAuthStore } from '@/stores/authStore';
import { FileText, MessageSquare, Bot, Clock } from 'lucide-react';
import PageContainer from '@/components/layout/PageContainer';
import Header from '@/components/layout/Header';
import Card from '@/components/ui/Card';
import Spinner from '@/components/ui/Spinner';

interface DashboardStats {
  total_documents: number;
  queries_today: number;
  active_agents: number;
  avg_response_time: number;
}

interface RecentActivity {
  id: string;
  type: 'upload' | 'query' | 'agent_execution';
  description: string;
  timestamp: string;
}

const Dashboard = () => {
  const { user } = useAuthStore();
  const [stats, setStats] = useState<DashboardStats>({
    total_documents: 0,
    queries_today: 0,
    active_agents: 0,
    avg_response_time: 0,
  });
  const [recentActivity, setRecentActivity] = useState<RecentActivity[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Simulate loading dashboard data
    setTimeout(() => {
      setStats({
        total_documents: 24,
        queries_today: 156,
        active_agents: 4,
        avg_response_time: 1.2,
      });
      setRecentActivity([
        {
          id: '1',
          type: 'upload',
          description: 'Uploaded "Annual Report 2024.pdf"',
          timestamp: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
        },
        {
          id: '2',
          type: 'query',
          description: 'Asked about Q4 revenue',
          timestamp: new Date(Date.now() - 1000 * 60 * 15).toISOString(),
        },
        {
          id: '3',
          type: 'agent_execution',
          description: 'Summarizer agent executed',
          timestamp: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
        },
        {
          id: '4',
          type: 'upload',
          description: 'Uploaded "Sales Data Q3.xlsx"',
          timestamp: new Date(Date.now() - 1000 * 60 * 45).toISOString(),
        },
        {
          id: '5',
          type: 'query',
          description: 'Generated SQL query for customer data',
          timestamp: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
        },
      ]);
      setIsLoading(false);
    }, 1000);
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
        </Card>

        <Card className="p-6">
          <h3 className="text-lg font-semibold text-text-primary mb-4">
            Quick Actions
          </h3>
          <div className="space-y-3">
            <button className="w-full text-left p-4 border border-border rounded-md hover:bg-gray-50 transition-colors">
              <div className="flex items-center gap-3">
                <FileText className="w-5 h-5 text-accent" />
                <div>
                  <p className="font-medium text-text-primary">Upload New Document</p>
                  <p className="text-sm text-text-secondary">Add PDF, TXT, or Excel files</p>
                </div>
              </div>
            </button>
            <button className="w-full text-left p-4 border border-border rounded-md hover:bg-gray-50 transition-colors">
              <div className="flex items-center gap-3">
                <MessageSquare className="w-5 h-5 text-success" />
                <div>
                  <p className="font-medium text-text-primary">Start New Chat</p>
                  <p className="text-sm text-text-secondary">Ask questions about your documents</p>
                </div>
              </div>
            </button>
            <button className="w-full text-left p-4 border border-border rounded-md hover:bg-gray-50 transition-colors">
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
