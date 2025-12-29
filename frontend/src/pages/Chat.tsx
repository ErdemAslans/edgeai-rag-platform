import { useEffect, useRef, useState } from 'react';
import { MessageSquare, Send, FileText, X, ChevronDown, Bot, Zap, FileSearch, Database, List } from 'lucide-react';
import PageContainer from '@/components/layout/PageContainer';
import MessageBubble from '@/components/chat/MessageBubble';
import { Button, Card, Spinner } from '@/components/ui';
import { useChat } from '@/hooks/useChat';
import { useDocuments } from '@/hooks/useDocuments';
import { Document, QueryMode } from '@/types';

// Query mode options with icons and descriptions
const QUERY_MODES: { value: QueryMode; label: string; description: string; icon: React.ReactNode }[] = [
  { value: 'auto', label: 'Auto', description: 'Smart routing to best agent', icon: <Zap className="w-4 h-4" /> },
  { value: 'rag', label: 'RAG Search', description: 'Search documents for answers', icon: <FileSearch className="w-4 h-4" /> },
  { value: 'summarize', label: 'Summarize', description: 'Create summaries of content', icon: <List className="w-4 h-4" /> },
  { value: 'analyze', label: 'Analyze', description: 'Deep analysis of documents', icon: <Bot className="w-4 h-4" /> },
  { value: 'sql', label: 'SQL', description: 'Generate SQL queries', icon: <Database className="w-4 h-4" /> },
];

const Chat = () => {
  const {
    currentConversation,
    sendMessage,
    isLoading,
    clearCurrentConversation,
  } = useChat();
  const { documents } = useDocuments();
  const [message, setMessage] = useState('');
  const [selectedDocuments, setSelectedDocuments] = useState<string[]>([]);
  const [showDocumentPicker, setShowDocumentPicker] = useState(false);
  const [selectedMode, setSelectedMode] = useState<QueryMode>('auto');
  const [showModePicker, setShowModePicker] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Get processed documents only
  const processedDocuments = documents?.filter(d => d.status === 'completed') || [];
  
  // Get current mode info
  const currentModeInfo = QUERY_MODES.find(m => m.value === selectedMode) || QUERY_MODES[0];

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [currentConversation]);

  const handleSendMessage = () => {
    if (message.trim() && !isLoading) {
      // Pass document IDs array and mode to sendMessage
      const docIds = selectedDocuments.length > 0 ? selectedDocuments : undefined;
      sendMessage(message.trim(), docIds, selectedMode);
      setMessage('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const toggleDocument = (docId: string) => {
    setSelectedDocuments(prev => 
      prev.includes(docId) 
        ? prev.filter(id => id !== docId)
        : [...prev, docId]
    );
  };

  const selectAllDocuments = () => {
    setSelectedDocuments(processedDocuments.map(d => d.id));
  };

  const clearDocumentSelection = () => {
    setSelectedDocuments([]);
  };

  return (
    <PageContainer title="Chat" subtitle="Ask questions about your documents with smart agent routing">
      <div className="flex flex-col h-[calc(100vh-12rem)]">
        {/* Mode and Document Selection Bar */}
        <div className="mb-4 space-y-2">
          {/* Agent Mode Selection */}
          <Card className="p-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Bot className="w-5 h-5 text-accent" />
                <span className="text-sm font-medium text-text-primary">
                  Agent Mode:
                </span>
                <div className="flex items-center gap-1 px-2 py-1 bg-accent/10 rounded-md">
                  {currentModeInfo.icon}
                  <span className="text-sm font-medium text-accent">{currentModeInfo.label}</span>
                </div>
                <span className="text-xs text-text-secondary hidden sm:inline">
                  {currentModeInfo.description}
                </span>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowModePicker(!showModePicker)}
              >
                <ChevronDown className={`w-4 h-4 transition-transform ${showModePicker ? 'rotate-180' : ''}`} />
                Change
              </Button>
            </div>

            {/* Mode Picker Dropdown */}
            {showModePicker && (
              <div className="mt-3 pt-3 border-t border-border">
                <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                  {QUERY_MODES.map((mode) => (
                    <button
                      key={mode.value}
                      onClick={() => {
                        setSelectedMode(mode.value);
                        setShowModePicker(false);
                      }}
                      className={`flex flex-col items-center gap-1 p-3 rounded-lg transition-colors ${
                        selectedMode === mode.value
                          ? 'bg-accent text-white'
                          : 'bg-secondary hover:bg-secondary/80 text-text-primary'
                      }`}
                    >
                      <div className={selectedMode === mode.value ? 'text-white' : 'text-accent'}>
                        {mode.icon}
                      </div>
                      <span className="text-sm font-medium">{mode.label}</span>
                      <span className={`text-xs ${selectedMode === mode.value ? 'text-white/80' : 'text-text-secondary'}`}>
                        {mode.description}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </Card>

          {/* Document Selection */}
          <Card className="p-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-accent" />
                <span className="text-sm font-medium text-text-primary">
                  Search in:
                </span>
                {selectedDocuments.length === 0 ? (
                  <span className="text-sm text-text-secondary">All documents</span>
                ) : (
                  <span className="text-sm text-accent">
                    {selectedDocuments.length} document{selectedDocuments.length > 1 ? 's' : ''} selected
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowDocumentPicker(!showDocumentPicker)}
                >
                  <ChevronDown className={`w-4 h-4 transition-transform ${showDocumentPicker ? 'rotate-180' : ''}`} />
                  Select Documents
                </Button>
                {selectedDocuments.length > 0 && (
                  <Button variant="ghost" size="sm" onClick={clearDocumentSelection}>
                    <X className="w-4 h-4" />
                  </Button>
                )}
              </div>
            </div>

            {/* Document Picker Dropdown */}
            {showDocumentPicker && (
              <div className="mt-3 pt-3 border-t border-border">
                {processedDocuments.length === 0 ? (
                  <p className="text-sm text-text-secondary text-center py-2">
                    No processed documents available. Upload and process documents first.
                  </p>
                ) : (
                  <>
                    <div className="flex justify-between mb-2">
                      <span className="text-xs text-text-secondary">
                        {processedDocuments.length} documents available
                      </span>
                      <button
                        onClick={selectAllDocuments}
                        className="text-xs text-accent hover:underline"
                      >
                        Select all
                      </button>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 max-h-48 overflow-y-auto">
                      {processedDocuments.map((doc) => (
                        <label
                          key={doc.id}
                          className={`flex items-center gap-2 p-2 rounded-md cursor-pointer transition-colors ${
                            selectedDocuments.includes(doc.id)
                              ? 'bg-accent/10 border border-accent'
                              : 'bg-secondary hover:bg-secondary/80 border border-transparent'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={selectedDocuments.includes(doc.id)}
                            onChange={() => toggleDocument(doc.id)}
                            className="rounded border-border text-accent focus:ring-accent"
                          />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-text-primary truncate">
                              {doc.filename}
                            </p>
                            <p className="text-xs text-text-secondary">
                              {doc.chunk_count || 0} chunks
                            </p>
                          </div>
                        </label>
                      ))}
                    </div>
                  </>
                )}
              </div>
            )}
          </Card>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto bg-secondary rounded-lg p-4 mb-4">
          {currentConversation.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <MessageSquare className="w-16 h-16 mx-auto text-text-secondary mb-4" />
                <h2 className="text-xl font-semibold text-text-primary mb-2">
                  Start a conversation
                </h2>
                <p className="text-text-secondary max-w-md">
                  Ask questions about your documents. The system will automatically
                  route your query to the best agent, or select a specific mode above.
                </p>
                <div className="flex flex-wrap justify-center gap-2 mt-4">
                  <span className="px-2 py-1 bg-accent/10 text-accent text-xs rounded-full">
                    🤖 Smart Routing
                  </span>
                  <span className="px-2 py-1 bg-accent/10 text-accent text-xs rounded-full">
                    📄 RAG Search
                  </span>
                  <span className="px-2 py-1 bg-accent/10 text-accent text-xs rounded-full">
                    📝 Summarization
                  </span>
                  <span className="px-2 py-1 bg-accent/10 text-accent text-xs rounded-full">
                    🔍 Analysis
                  </span>
                </div>
                {processedDocuments.length > 0 && (
                  <p className="text-sm text-accent mt-4">
                    {processedDocuments.length} document{processedDocuments.length > 1 ? 's' : ''} ready for search
                  </p>
                )}
              </div>
            </div>
          ) : (
            <div className="max-w-4xl mx-auto space-y-4">
              {currentConversation.map((msg) => (
                <MessageBubble key={msg.id} message={msg} />
              ))}
              {isLoading && (
                <div className="flex justify-start mb-4">
                  <div className="bg-white border border-border rounded-lg p-4">
                    <div className="flex items-center gap-2">
                      <Spinner size="sm" />
                      <span className="text-sm text-text-secondary">Thinking...</span>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="bg-white rounded-lg border border-border p-4">
          <div className="flex gap-3 items-end">
            <textarea
              ref={inputRef}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                selectedDocuments.length > 0
                  ? `Ask about ${selectedDocuments.length} selected document${selectedDocuments.length > 1 ? 's' : ''}...`
                  : 'Ask a question about your documents...'
              }
              rows={1}
              className="flex-1 resize-none border border-border rounded-lg px-4 py-3 text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent transition-all"
              style={{ minHeight: '48px', maxHeight: '200px' }}
            />
            <Button
              onClick={handleSendMessage}
              disabled={!message.trim() || isLoading}
              className="h-12 px-6"
            >
              {isLoading ? (
                <Spinner size="sm" />
              ) : (
                <>
                  <Send className="w-4 h-4 mr-2" />
                  Send
                </>
              )}
            </Button>
          </div>
          <div className="flex justify-between mt-2">
            <div className="flex items-center gap-2">
              <p className="text-xs text-text-secondary">
                Press Enter to send, Shift + Enter for new line
              </p>
              <span className="text-xs text-accent">
                • Mode: {currentModeInfo.label}
              </span>
            </div>
            {currentConversation.length > 0 && (
              <button
                onClick={clearCurrentConversation}
                className="text-xs text-text-secondary hover:text-accent transition-colors"
              >
                Clear conversation
              </button>
            )}
          </div>
        </div>
      </div>
    </PageContainer>
  );
};

export default Chat;
