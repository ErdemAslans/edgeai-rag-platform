import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getAgents, executeAgent, getAgentLogs } from '@/api/agents';
import { Agent, AgentExecution } from '@/types';
import { useToast } from '@/components/ui/Toast';

export const useAgents = () => {
  const queryClient = useQueryClient();
  const { addToast } = useToast();

  const { data: agents = [], isLoading: agentsLoading } = useQuery({
    queryKey: ['agents'],
    queryFn: getAgents,
  });

  const { data: logs = [], isLoading: logsLoading } = useQuery({
    queryKey: ['agent-logs'],
    queryFn: getAgentLogs,
  });

  const executeMutation = useMutation({
    mutationFn: async ({ name, params }: { name: string; params: Record<string, unknown> }) => {
      return await executeAgent(name, params);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agent-logs'] });
      addToast('Agent executed successfully!', 'success');
    },
    onError: (error: any) => {
      addToast(error.response?.data?.detail || 'Failed to execute agent.', 'error');
    },
  });

  return {
    agents,
    logs,
    agentsLoading,
    logsLoading,
    executeAgent: executeMutation.mutate,
    isExecuting: executeMutation.isPending,
  };
};
