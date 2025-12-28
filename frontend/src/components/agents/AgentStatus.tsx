import { CheckCircle2, XCircle, Clock } from 'lucide-react';

interface AgentStatusProps {
  status: 'active' | 'inactive' | 'loading';
}

const AgentStatus = ({ status }: AgentStatusProps) => {
  const statusConfig = {
    active: {
      icon: CheckCircle2,
      color: 'text-success',
      label: 'Active',
    },
    inactive: {
      icon: XCircle,
      color: 'text-text-secondary',
      label: 'Inactive',
    },
    loading: {
      icon: Clock,
      color: 'text-accent',
      label: 'Loading...',
    },
  };

  const config = statusConfig[status];
  const Icon = config.icon;

  return (
    <div className="flex items-center gap-2">
      <Icon className={`w-4 h-4 ${config.color}`} />
      <span className="text-sm text-text-secondary">{config.label}</span>
    </div>
  );
};

export default AgentStatus;
