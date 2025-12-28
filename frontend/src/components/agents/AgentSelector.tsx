import { ChevronDown } from 'lucide-react';
import Dropdown from '@/components/ui/Dropdown';

interface AgentSelectorProps {
  agents: string[];
  selectedAgent: string | null;
  onSelect: (agent: string) => void;
}

const AgentSelector = ({ agents, selectedAgent, onSelect }: AgentSelectorProps) => {
  return (
    <Dropdown>
      <Dropdown.Trigger className="w-full">
        <span className="flex-1 text-left">
          {selectedAgent || 'Select Agent'}
        </span>
      </Dropdown.Trigger>
      <Dropdown.Content align="start" className="w-full">
        {agents.map((agent) => (
          <Dropdown.Item key={agent} onClick={() => onSelect(agent)}>
            {agent}
          </Dropdown.Item>
        ))}
      </Dropdown.Content>
    </Dropdown>
  );
};

export default AgentSelector;
