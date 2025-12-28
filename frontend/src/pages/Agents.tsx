import { useState } from 'react';
import { Bot, FileText, Code2, Database } from 'lucide-react';
import PageContainer from '@/components/layout/PageContainer';
import Header from '@/components/layout/Header';
import AgentStatus from '@/components/agents/AgentStatus';
import AgentLogs from '@/components/agents/AgentLogs';
import { useAgents } from '@/hooks/useAgents';

const AGENT_DESCRIPTIONS: Record<string, string> = {
  QueryRouter: 'Routes incoming queries to the appropriate specialized agent',
  DocumentAnalyzer: 'Analyzes and extracts key information from documents',
  Summarizer: 'Creates concise summaries of document content',
  SQLGenerator: 'Generates SQL queries based on natural language requests',
};

const Agents = () => {
  const { agents, logs, agentsLoading, logsLoading, executeAgent, isExecuting } = useAgents();
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);

  const handleExecuteAgent = (agentName: string) => {
    executeAgent({ name: agentName, params: {} });
  };

  return (
    <PageContainer>
      <Header
        title="Agents"
        subtitle="Manage and monitor AI agents"
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-6">
          <h2 className="text-lg font-semibold text-text-primary mb-4">
            Available Agents
          </h2>
          
          {agentsLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent"></div>
            </div>
          ) : (
            <div className="space-y-4">
              {agents.map((agent) => {
                let Icon = Bot;
                if (agent.name === 'QueryRouter') Icon = Code2;
                if (agent.name === 'DocumentAnalyzer') Icon = FileText;
                if (agent.name === 'SQLGenerator') Icon = Database;

                return (
                  <div
                    key={agent.name}
                    className="card p-6 hover:shadow-card-hover transition-shadow cursor-pointer"
                    onClick={() => setSelectedAgent(agent.name)}
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-accent/10 rounded-md">
                          <Icon className="w-6 h-6 text-accent" />
                        </div>
                        <div>
                          <h3 className="font-semibold text-text-primary">
                            {agent.name}
                          </h3>
                          <AgentStatus status={agent.status as any} />
                        </div>
                      </div>
                    </div>
                    <p className="text-sm text-text-secondary">
                      {AGENT_DESCRIPTIONS[agent.name] || 'No description available'}
                    </p>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div>
          <h2 className="text-lg font-semibold text-text-primary mb-4">
            Execution Logs
          </h2>
          {logsLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent"></div>
            </div>
          ) : (
            <AgentLogs logs={logs} />
          )}
        </div>
      </div>
    </PageContainer>
  );
};

export default Agents;
