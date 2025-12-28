import { AgentExecution } from '@/types';
import { formatDateTime, formatDuration } from '@/lib/utils';
import Badge from '@/components/ui/Badge';

interface AgentLogsProps {
  logs: AgentExecution[];
}

const AgentLogs = ({ logs }: AgentLogsProps) => {
  const getStatusVariant = (status: string) => {
    switch (status) {
      case 'success':
        return 'success';
      case 'failed':
        return 'error';
      case 'pending':
        return 'warning';
      default:
        return 'neutral';
    }
  };

  if (logs.length === 0) {
    return (
      <div className="text-center py-12 text-text-secondary">
        <p>No agent execution logs yet.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {logs.map((log) => (
        <div
          key={log.id}
          className="card p-4"
        >
          <div className="flex items-start justify-between mb-3">
            <div>
              <h4 className="font-medium text-text-primary">{log.agent_name}</h4>
              <p className="text-sm text-text-secondary">{log.action}</p>
            </div>
            <Badge variant={getStatusVariant(log.status)}>
              {log.status}
            </Badge>
          </div>
          
          <div className="flex items-center gap-4 text-sm text-text-secondary">
            <span>{formatDateTime(log.timestamp)}</span>
            <span>Duration: {formatDuration(log.duration)}</span>
          </div>
        </div>
      ))}
    </div>
  );
};

export default AgentLogs;
