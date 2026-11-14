import React, { useEffect, useRef, useState } from 'react';
import { apiFetch } from '../services/apiClient';
import type { CopilotAgentAction, CopilotMessage, CopilotSource, CopilotToolExecution, GraphTraceNode, UserProfile } from '../types/library';
import { VisionSearchModal } from './VisionSearchModal';
import { ConceptCanvas3D } from './ConceptCanvas3D';

interface AICopilotDrawerProps {
  currentUser: UserProfile;
  isOpen: boolean;
  onClose: () => void;
  onOpen: () => void;
  onSelectBook: (bookId: number) => void;
  onNavigateTab?: (tab: string) => void;
  onOpenAuditModal?: () => void;
}

const getContextualLoadingStages = (query: string): string[] => {
  const q = query.toLowerCase();

  // 1. Conversational, greetings, meta & casual chat
  if (
    /^(hi|hello|hey|yo|greetings|good\s*(morning|afternoon|evening|day)|sup)\b/.test(q) ||
    q.includes('talk normally') ||
    q.includes('speak normally') ||
    q.includes('tell me something') ||
    q.includes('talk to me') ||
    q.includes('who are you') ||
    q.includes('how are you') ||
    q.includes('can you talk') ||
    q.includes('can we chat') ||
    q.includes('chat with me') ||
    q.includes('are you human') ||
    q.includes('are you real') ||
    q.includes('are you an ai') ||
    q.includes('joke') ||
    q.includes('story') ||
    q.includes('what is your name')
  ) {
    return [
      'Thinking...',
      'Formulating response...',
      'Connecting with Gemini AI...',
    ];
  }

  // 1b. Cancellation
  if (q.includes('cancel')) {
    return [
      'Locating active reservation...',
      'Releasing seat allocation in database...',
      'Updating patron quota...',
    ];
  }

  // 2. Study Spaces & Wayfinding
  if (
    q.includes('seat') ||
    q.includes('room') ||
    q.includes('floor') ||
    q.includes('space') ||
    q.includes('desk') ||
    q.includes('wayfinding') ||
    q.includes('where is') ||
    q.includes('locate') ||
    q.includes('pod')
  ) {
    return [
      'Consulting floor plan directory...',
      'Checking live seat occupancy...',
      'Synthesizing directional guidance...',
    ];
  }

  // 3. Loans, Borrowing & Policies
  if (
    q.includes('loan') ||
    q.includes('due') ||
    q.includes('borrow') ||
    q.includes('return') ||
    q.includes('renew') ||
    q.includes('fine') ||
    q.includes('penalty') ||
    q.includes('policy') ||
    q.includes('rule') ||
    q.includes('hours') ||
    q.includes('limit')
  ) {
    return [
      'Checking circulation records...',
      'Reviewing borrowing policies...',
      'Synthesizing loan regulations...',
    ];
  }

  // 4. Books, Monographs, Authors & Reading Lists
  if (
    !q.includes('cancel') && (
      q.includes('book') ||
      q.includes('author') ||
      q.includes('monograph') ||
      q.includes('read') ||
      q.includes('syllabus') ||
      q.includes('title') ||
      q.includes('edition') ||
      q.includes('isbn') ||
      q.includes('recommend')
    )
  ) {
    return [
      'Searching library holdings...',
      'Checking copy shelf availability...',
      'Synthesizing recommendations...',
    ];
  }

  // 5. Default General Inquiry
  return [
    'Analyzing inquiry with Gemini AI...',
    'Consulting academic intelligence...',
    'Synthesizing verified response...',
  ];
};

export const AICopilotDrawer: React.FC<AICopilotDrawerProps> = ({
  currentUser,
  isOpen,
  onClose,
  onOpen,
  onSelectBook,
  onNavigateTab,
  onOpenAuditModal,
}) => {
  const [messages, setMessages] = useState<CopilotMessage[]>(() => [
    {
      id: 'welcome-1',
      role: 'assistant',
      content:
        `Hello ${currentUser.full_name}! I am your **AI Library Copilot**.\n\n` +
        `I am grounded directly in our verified database to help you check active loans, find monographs, verify physical copy availability, and explain borrowing rules.`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      is_fallback: true,
      suggested_followups:
        currentUser.role === 'student'
          ? [
              'What books do I currently have checked out?',
              'What is the borrowing duration and limit?',
              'Find books on Distributed Systems',
            ]
          : [
              'How many active loans are in circulation?',
              'What are the circulation desk return procedures?',
              'Search catalogue for monographs',
            ],
    },
  ]);

  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState<string>('Thinking...');
  const [lastProvider, setLastProvider] = useState<string>('auto');
  const [lastIsFallback, setLastIsFallback] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [showVisionModal, setShowVisionModal] = useState<boolean>(false);

  // Two-Way Spoken Voice Concierge State
  const [isVoiceEnabled, setIsVoiceEnabled] = useState<boolean>(false);
  const [isListening, setIsListening] = useState<boolean>(false);
  const [isExpanded, setIsExpanded] = useState<boolean>(false);
  const [speakingMsgId, setSpeakingMsgId] = useState<string | null>(null);
  const recognitionRef = useRef<any>(null);

  // BYOK (Bring Your Own Key) Multi-Provider State
  type AIProviderId = 'groq' | 'gemini' | 'openai' | 'anthropic';

  const [showKeyModal, setShowKeyModal] = useState<boolean>(false);
  const [activeProviderTab, setActiveProviderTab] = useState<AIProviderId>('groq');
  const [providerKeys, setProviderKeys] = useState<Record<AIProviderId, string>>(() => {
    if (typeof window === 'undefined') return { groq: '', gemini: '', openai: '', anthropic: '' };
    return {
      groq: localStorage.getItem('patron_custom_groq_key') || '',
      gemini: localStorage.getItem('patron_custom_gemini_key') || '',
      openai: localStorage.getItem('patron_custom_openai_key') || '',
      anthropic: localStorage.getItem('patron_custom_anthropic_key') || '',
    };
  });
  const [keyTesting, setKeyTesting] = useState<boolean>(false);
  const [keyMessage, setKeyMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const hasAnyKey = Boolean(
    providerKeys.groq.trim() ||
    providerKeys.gemini.trim() ||
    providerKeys.openai.trim() ||
    providerKeys.anthropic.trim()
  );

  const handleTestKey = async (provider: AIProviderId) => {
    const key = providerKeys[provider].trim();
    if (!key) {
      setKeyMessage({ type: 'error', text: `Please enter a ${provider.toUpperCase()} API Key to test.` });
      return;
    }
    setKeyTesting(true);
    setKeyMessage(null);
    try {
      const res = await apiFetch<{ valid: boolean; provider: string; message: string }>('/api/copilot/verify-key', {
        method: 'POST',
        body: JSON.stringify({ api_key: key, provider }),
      });
      if (res.valid) {
        setKeyMessage({ type: 'success', text: `Key verified successfully! (${res.message})` });
      } else {
        setKeyMessage({ type: 'error', text: res.message });
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to test key';
      setKeyMessage({ type: 'error', text: msg.replace(/^\d+:\s*/, '') });
    } finally {
      setKeyTesting(false);
    }
  };

  const handleSaveKey = (provider: AIProviderId) => {
    const key = providerKeys[provider].trim();
    if (!key) {
      setKeyMessage({ type: 'error', text: 'API key cannot be empty.' });
      return;
    }
    localStorage.setItem(`patron_custom_${provider}_key`, key);
    setKeyMessage({ type: 'success', text: `${provider.toUpperCase()} key saved! Intelligent gateway will route to it.` });
  };

  const handleClearKey = (provider: AIProviderId) => {
    localStorage.removeItem(`patron_custom_${provider}_key`);
    setProviderKeys((prev) => ({ ...prev, [provider]: '' }));
    setKeyMessage({ type: 'success', text: `${provider.toUpperCase()} key cleared.` });
  };

  const stopSpeaking = () => {
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    setSpeakingMsgId(null);
  };

  const speakText = (text: string, msgId?: string) => {
    if (typeof window === 'undefined' || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    setSpeakingMsgId(null);

    const clean = text
      .replace(/[*_#`~\[\]()]/g, '')
      .replace(/https?:\/\/\S+/g, '')
      .replace(/[🪐✅📚ℹ️⚠️•]/g, '')
      .trim();
    if (!clean) return;

    const utterance = new SpeechSynthesisUtterance(clean);
    utterance.rate = 1.05;
    utterance.pitch = 1.0;

    const idToTrack = msgId || 'auto-speech';
    setSpeakingMsgId(idToTrack);

    utterance.onend = () => {
      setSpeakingMsgId((curr) => (curr === idToTrack ? null : curr));
    };
    utterance.onerror = () => {
      setSpeakingMsgId((curr) => (curr === idToTrack ? null : curr));
    };

    window.speechSynthesis.speak(utterance);
  };

  const toggleListening = () => {
    if (isListening) {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      setIsListening(false);
      return;
    }

    const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRec) {
      alert('Live speech recognition is not supported in this browser. Please use Google Chrome or Microsoft Edge.');
      return;
    }

    try {
      const recognition = new SpeechRec();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = 'en-US';

      recognition.onstart = () => {
        setIsListening(true);
      };

      recognition.onresult = (event: any) => {
        const transcript = Array.from(event.results)
          .map((result: any) => result[0].transcript)
          .join('');
        setInputMessage(transcript);
      };

      recognition.onerror = () => {
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch {
      setIsListening(false);
    }
  };

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const stageTimersRef = useRef<NodeJS.Timeout[]>([]);

  useEffect(() => {
    return () => {
      stageTimersRef.current.forEach(clearTimeout);
      if (typeof window !== 'undefined' && window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
    };
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
      setTimeout(() => inputRef.current?.focus(), 150);
    }
  }, [isOpen, messages]);

  // Handle ESC key to close drawer
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  const handleSend = async (textToSend?: string) => {
    const text = (textToSend || inputMessage).trim();
    if (!text || isLoading) return;

    const userMsg: CopilotMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputMessage('');
    setIsLoading(true);
    setErrorMessage(null);

    // Dynamic contextual loading stages
    stageTimersRef.current.forEach(clearTimeout);
    stageTimersRef.current = [];
    const stages = getContextualLoadingStages(text);
    setLoadingStatus(stages[0]);

    if (stages[1]) {
      const t1 = setTimeout(() => setLoadingStatus(stages[1]), 750);
      stageTimersRef.current.push(t1);
    }
    if (stages[2]) {
      const t2 = setTimeout(() => setLoadingStatus(stages[2]), 1700);
      stageTimersRef.current.push(t2);
    }

    try {
      const history = messages
        .filter((m) => m.role === 'user' || m.role === 'assistant')
        .slice(-6)
        .map((m) => ({
          role: m.role,
          content: m.content.trim().slice(0, 3000),
        }))
        .filter((m) => m.content.length > 0);

      const resp = await apiFetch<any>('/api/knowledge/agent/chat', {
        method: 'POST',
        body: JSON.stringify({
          message: text,
          conversation_history: history,
        }),
      });

      setLastProvider(resp.provider || 'Librarian Agent Tool Runner');
      setLastIsFallback(false);

      const assistantMsg: CopilotMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: resp.answer,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        provider: resp.provider,
        is_fallback: false,
        sources: resp.citations?.map((c: any) => ({
          title: c.title,
          source_type: c.source_type,
          snippet: c.snippet,
          url_or_action: c.url_or_action,
        })),
        agent_actions: resp.agent_actions,
        tool_calls: resp.tool_calls,
        suggested_followups: resp.suggested_followups,
        concept_3d: resp.concept_3d,
        graph_trace: resp.graph_trace,
        architecture_mode: resp.architecture_mode,
      };

      setMessages((prev) => [...prev, assistantMsg]);

      if (isVoiceEnabled && resp.answer) {
        speakText(resp.answer, assistantMsg.id);
      }
    } catch (err: unknown) {
      let msg = 'Failed to reach AI Copilot.';
      if (err instanceof Error) {
        msg = err.message;
      } else if (typeof err === 'string') {
        msg = err;
      } else if (err && typeof err === 'object') {
        msg = JSON.stringify(err);
      }
      setErrorMessage(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setIsLoading(false);
      stageTimersRef.current.forEach(clearTimeout);
      stageTimersRef.current = [];
    }
  };

  const handleClearHistory = () => {
    setMessages([
      {
        id: `welcome-${Date.now()}`,
        role: 'assistant',
        content: 'Conversation cleared. How can I assist you with library holdings or procedures?',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        suggested_followups:
          currentUser.role === 'student'
            ? [
                'What books do I currently have checked out?',
                'What is the borrowing limit?',
                'Find books on Artificial Intelligence',
              ]
            : [
                'How many active loans are in circulation?',
                'Circulation Desk return procedure',
              ],
      },
    ]);
  };

  const renderBookCards = (sources: CopilotSource[]) => {
    const bookSources = sources.filter((s) => s.type === 'book' && s.id);
    if (bookSources.length === 0) return null;

    return (
      <div className="copilot-book-cards-grid">
        {bookSources.map((b) => {
          const isAvail = (b.available_copies ?? 0) > 0;
          return (
            <div key={b.id} className="copilot-book-card">
              <div className="copilot-book-card-main">
                <div className="copilot-book-card-title">{b.title}</div>
                <div className="copilot-book-card-author">
                  {b.author ? `by ${b.author}` : ''} {b.category ? `• ${b.category}` : ''}
                </div>
              </div>
              <div className="copilot-book-card-footer">
                <span className={`copilot-avail-badge ${isAvail ? 'badge-avail' : 'badge-borrowed'}`}>
                  {b.available_copies ?? 0} / {b.total_copies ?? 0} available
                </span>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm copilot-view-book-btn"
                  onClick={() => onSelectBook(b.id!)}
                  title="View full monograph metadata and shelf locations"
                >
                  View Details
                </button>
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  const renderPolicyAndLoanSources = (sources: CopilotSource[]) => {
    const nonBookSources = sources.filter((s) => s.type !== 'book');
    if (nonBookSources.length === 0) return null;

    return (
      <div className="copilot-sources-block">
        <div className="copilot-sources-label">Verified Policy & Loan Records:</div>
        <div className="copilot-sources-chips">
          {nonBookSources.map((s, idx) => (
            <span
              key={idx}
              className={`copilot-source-chip copilot-source-${s.type}`}
              title={s.snippet || ''}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: '3px' }}>
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
              {s.title}
            </span>
          ))}
        </div>
      </div>
    );
  };

  const [copiedToken, setCopiedToken] = useState<string | null>(null);

  const handleCopy = (token: string) => {
    navigator.clipboard.writeText(token);
    setCopiedToken(token);
    setTimeout(() => setCopiedToken(null), 2500);
  };

  const renderStateGraphTrace = (trace?: GraphTraceNode[], architectureMode?: string) => {
    if (!trace || trace.length === 0) return null;
    const totalLatency = trace.reduce((acc, n) => acc + (n.duration_ms || 0), 0);
    return (
      <details
        className="copilot-tool-trace"
        style={{
          marginBottom: '0.5rem',
          border: '1px solid rgba(56, 189, 248, 0.25)',
          borderRadius: '8px',
          background: 'rgba(15, 23, 42, 0.65)',
        }}
      >
        <summary
          className="copilot-tool-trace-summary"
          style={{
            color: '#38bdf8',
            fontWeight: 600,
            cursor: 'pointer',
            padding: '0.4rem 0.6rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
            <span>🕸️</span>
            <span>StateGraph Pipeline ({trace.length} Nodes · {totalLatency.toFixed(1)}ms)</span>
          </span>
          <span style={{ fontSize: '0.65rem', color: '#10b981', background: 'rgba(16, 185, 129, 0.15)', padding: '2px 6px', borderRadius: '4px' }}>
            VERIFIED
          </span>
        </summary>
        <div className="copilot-tool-trace-body" style={{ padding: '0.4rem 0.6rem', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
          {architectureMode && (
            <div style={{ fontSize: '0.7rem', color: '#94a3b8', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '0.3rem', display: 'flex', justifyContent: 'space-between' }}>
              <span>Orchestration:</span>
              <span style={{ color: '#a78bfa', fontWeight: 600 }}>{architectureMode}</span>
            </div>
          )}
          {trace.map((item, idx) => (
            <div
              key={idx}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0.25rem 0.45rem',
                background: 'rgba(255,255,255,0.03)',
                borderRadius: '4px',
                fontSize: '0.72rem',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <span style={{ color: item.status.includes('FLAGGED') ? '#ef4444' : '#10b981', fontSize: '0.8rem' }}>
                  {item.status.includes('FLAGGED') ? '🛡️' : '✓'}
                </span>
                <span style={{ fontWeight: 600, color: '#f1f5f9' }}>{item.stage || item.label || item.node}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                <span style={{ color: '#94a3b8', fontFamily: 'monospace' }}>{item.duration_ms}ms</span>
                <span
                  style={{
                    fontSize: '0.66rem',
                    padding: '1px 5px',
                    borderRadius: '3px',
                    background: item.status.includes('FLAGGED') ? 'rgba(239, 68, 68, 0.2)' : 'rgba(56, 189, 248, 0.15)',
                    color: item.status.includes('FLAGGED') ? '#fca5a5' : '#38bdf8',
                    fontWeight: 600,
                  }}
                >
                  {item.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      </details>
    );
  };

  const renderToolCallsTrace = (toolCalls?: CopilotToolExecution[]) => {
    if (!toolCalls || toolCalls.length === 0) return null;
    return (
      <details className="copilot-tool-trace">
        <summary className="copilot-tool-trace-summary">
          <span>⚙️ Agent Action Trace ({toolCalls.length} tool{toolCalls.length > 1 ? 's' : ''} executed)</span>
        </summary>
        <div className="copilot-tool-trace-body">
          {toolCalls.map((tc, idx) => (
            <div key={idx} className="copilot-tool-trace-item">
              <span className="copilot-tool-name">{tc.tool_name}</span>
              <span className="copilot-tool-args">{JSON.stringify(tc.arguments)}</span>
            </div>
          ))}
        </div>
      </details>
    );
  };

  const renderAgentActions = (actions?: CopilotAgentAction[]) => {
    if (!actions || actions.length === 0) return null;

    return (
      <div className="copilot-agent-actions-stack">
        {actions.map((act, idx) => {
          const isSuccess = act.status === 'success';
          return (
            <div
              key={idx}
              className={`copilot-action-card copilot-action-${act.action_type} ${isSuccess ? 'card-success' : 'card-info'}`}
            >
              <div className="copilot-action-card-header">
                <span className="copilot-action-type-badge">
                  {act.action_type === 'space_reserved' && '🪑 STUDY DESK CONFIRMED'}
                  {act.action_type === 'hold_placed' && '📚 MONOGRAPH HOLD READY'}
                  {act.action_type === 'loan_renewed' && '✅ LOAN RENEWED'}
                  {act.action_type === 'return_pass_generated' && '📱 RETURN CLEARANCE PASS'}
                  {act.action_type === 'academic_research' && '🎓 SCHOLARLY PREPRINTS'}
                </span>
                <span className="copilot-action-status-pill">{act.status.toUpperCase()}</span>
              </div>

              <div className="copilot-action-card-title">{act.title}</div>
              <div className="copilot-action-card-desc">{act.description}</div>

              {/* Action-Specific Interactive Payloads */}
              {act.action_type === 'space_reserved' && act.data && (
                <div className="copilot-action-payload">
                  {act.data.check_in_token && (
                    <div className="copilot-token-row">
                      <span className="token-label">Check-in Token:</span>
                      <code className="token-val">
                        {act.data.check_in_token.length > 20
                          ? `${act.data.check_in_token.slice(0, 14)}...`
                          : act.data.check_in_token}
                      </code>
                      <button
                        type="button"
                        className="btn-copy-token"
                        onClick={() => handleCopy(act.data.check_in_token)}
                      >
                        {copiedToken === act.data.check_in_token ? '✓ Copied' : 'Copy'}
                      </button>
                    </div>
                  )}
                  <div className="copilot-action-buttons">
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={() => {
                        onNavigateTab?.('spaces');
                        onClose();
                      }}
                    >
                      View on Floor Map 📍
                    </button>
                  </div>
                </div>
              )}

              {act.action_type === 'hold_placed' && act.data && (
                <div className="copilot-action-buttons" style={{ marginTop: '0.5rem' }}>
                  {act.data.book_id && (
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={() => onSelectBook(act.data.book_id)}
                    >
                      View Monograph Details 📖
                    </button>
                  )}
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => {
                      onNavigateTab?.('catalogue');
                      onClose();
                    }}
                  >
                    Open Catalogue
                  </button>
                </div>
              )}

              {act.action_type === 'loan_renewed' && (
                <div className="copilot-action-buttons" style={{ marginTop: '0.5rem' }}>
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    onClick={() => {
                      onNavigateTab?.('loans');
                      onClose();
                    }}
                  >
                    View Active Loans Desk 📋
                  </button>
                </div>
              )}

              {act.action_type === 'return_pass_generated' && act.data && (
                <div className="copilot-action-payload">
                  {act.data.token_code && (
                    <div className="copilot-token-row">
                      <span className="token-label">Pass Code:</span>
                      <code className="token-val">{act.data.token_code}</code>
                      <button
                        type="button"
                        className="btn-copy-token"
                        onClick={() => handleCopy(act.data.token_code)}
                      >
                        {copiedToken === act.data.token_code ? '✓ Copied' : 'Copy'}
                      </button>
                    </div>
                  )}
                  <div className="copilot-action-buttons">
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={() => {
                        onNavigateTab?.('loans');
                        onClose();
                      }}
                    >
                      View in Loans Desk 📲
                    </button>
                  </div>
                </div>
              )}

              {act.action_type === 'academic_research' && act.data && act.data.papers && (
                <div className="copilot-research-papers-list">
                  {act.data.papers.map((p: any, pIdx: number) => (
                    <div key={pIdx} className="copilot-research-paper-item">
                      <div className="paper-item-title">{p.title}</div>
                      <div className="paper-item-meta">
                        {p.authors?.slice(0, 2).join(', ')} • {p.venue || p.year}
                      </div>
                      {p.open_access_pdf_url && (
                        <a
                          href={p.open_access_pdf_url}
                          target="_blank"
                          rel="noreferrer"
                          className="btn-oa-pdf"
                        >
                          Open PDF ↗
                        </a>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <>
      {/* Floating launcher badge when closed */}
      {!isOpen && (
        <button
          type="button"
          data-tour="copilot-launcher"
          className="copilot-floating-launcher"
          onClick={onOpen}
          aria-label="Open AI Library Copilot"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" />
          </svg>
          <span className="copilot-launcher-text">AI Copilot</span>
        </button>
      )}

      {/* Slide-out Copilot Drawer */}
      {isOpen && (
        <aside
          className={`copilot-drawer ${isExpanded ? 'copilot-drawer-expanded' : ''}`.trim()}
          aria-label="AI Library Copilot"
          role="region"
        >
          {/* Header */}
          <div className="copilot-header">
            <div className="copilot-header-info">
              <div className="copilot-title-row">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: '#93c5fd' }}>
                  <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" />
                </svg>
                <h3>AI Library Copilot</h3>
              </div>
              <div className="copilot-status-row">
                {lastIsFallback ? (
                  <span className="copilot-mode-pill copilot-mode-offline" title="Grounded locally using live SQLite database records and library policies">
                    Local Grounded Mode
                  </span>
                ) : (
                  <span className="copilot-mode-pill copilot-mode-online" title={`Powered by ${lastProvider.toUpperCase()}`}>
                    AI Active ({lastProvider})
                  </span>
                )}
              </div>
            </div>

            <div className="copilot-header-actions">
              {onOpenAuditModal && (
                <button
                  type="button"
                  className="copilot-btn-icon"
                  onClick={onOpenAuditModal}
                  title="Architecture Defense & StateGraph Audit Studio"
                  aria-label="Defense Studio"
                  style={{
                    color: '#38bdf8',
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '0.9rem',
                  }}
                >
                  🛡️
                </button>
              )}
              <button
                type="button"
                className="copilot-btn-icon"
                onClick={() => {
                  setKeyMessage(null);
                  setShowKeyModal(true);
                }}
                title={hasAnyKey ? 'Personal AI Key Gateway Active (Click to configure)' : 'Configure Multi-Provider AI Keys (BYOK)'}
                aria-label="Configure AI Key"
                style={{
                  fontSize: '0.92rem',
                  color: hasAnyKey ? '#10b981' : '#94a3b8',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  position: 'relative',
                }}
              >
                🔑
                {hasAnyKey && (
                  <span
                    style={{
                      position: 'absolute',
                      top: '2px',
                      right: '2px',
                      width: '6px',
                      height: '6px',
                      borderRadius: '50%',
                      backgroundColor: '#10b981',
                      boxShadow: '0 0 6px #10b981',
                    }}
                  />
                )}
              </button>
              <button
                type="button"
                className="copilot-btn-icon"
                onClick={() => {
                  if (isVoiceEnabled && typeof window !== 'undefined' && window.speechSynthesis) {
                    window.speechSynthesis.cancel();
                  }
                  setIsVoiceEnabled((prev) => !prev);
                }}
                title={isVoiceEnabled ? 'Voice Narration ON (Click to Mute)' : 'Voice Narration OFF (Click to Enable)'}
                aria-label="Toggle Voice Narration"
                style={{
                  fontSize: '0.95rem',
                  color: isVoiceEnabled ? '#38bdf8' : '#64748b',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                {isVoiceEnabled ? '🔊' : '🔇'}
              </button>
              <button
                type="button"
                className="copilot-btn-icon"
                onClick={() => setIsExpanded((prev) => !prev)}
                title={isExpanded ? 'Collapse drawer to standard width (440px)' : 'Expand drawer to wide canvas view (920px)'}
                aria-label={isExpanded ? 'Collapse drawer' : 'Expand drawer'}
                style={{
                  color: isExpanded ? '#38bdf8' : '#94a3b8',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                {isExpanded ? (
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M4 14h6v6m0-6L3 21m17-7h-6v6m0-6 7 7M4 10h6V4m0 6L3 3m17 7h-6V4m0 6 7-7"/>
                  </svg>
                ) : (
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M15 3h6v6m0-6L14 10M9 21H3v-6m0 6 7-7M3 9V3h6M3 3l7 7m11 11v-6h-6m6 6-7-7"/>
                  </svg>
                )}
              </button>
              <button
                type="button"
                className="copilot-btn-icon"
                onClick={handleClearHistory}
                title="Clear conversation history"
                aria-label="Clear chat"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="3 6 5 6 21 6" />
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                </svg>
              </button>
              <button
                type="button"
                className="copilot-btn-icon"
                onClick={onClose}
                title="Close Copilot (Esc)"
                aria-label="Close Copilot"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
          </div>

          {/* Messages Body */}
          <div className="copilot-messages-container">
            {speakingMsgId && (
              <div
                style={{
                  position: 'sticky',
                  top: 0,
                  zIndex: 20,
                  background: 'linear-gradient(90deg, rgba(220, 38, 38, 0.95), rgba(153, 27, 27, 0.95))',
                  backdropFilter: 'blur(8px)',
                  color: '#ffffff',
                  padding: '0.4rem 0.85rem',
                  borderRadius: '6px',
                  marginBottom: '0.65rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  boxShadow: '0 4px 14px rgba(220, 38, 38, 0.4)',
                  animation: 'fadeIn 0.15s ease',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', fontSize: '0.75rem', fontWeight: 600 }}>
                  <span style={{ fontSize: '0.9rem' }}>🔊</span>
                  <span>AI Narration is speaking...</span>
                </div>
                <button
                  type="button"
                  onClick={stopSpeaking}
                  style={{
                    background: 'rgba(255, 255, 255, 0.25)',
                    border: '1px solid rgba(255, 255, 255, 0.4)',
                    color: '#ffffff',
                    borderRadius: '4px',
                    padding: '2px 9px',
                    fontSize: '0.72rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                >
                  <span>⏹️</span> Stop Narration
                </button>
              </div>
            )}
            {messages.map((m) => (
              <div key={m.id} className={`copilot-bubble-row ${m.role === 'user' ? 'bubble-user' : 'bubble-assistant'}`}>
                {m.role === 'assistant' && (
                  <div className="copilot-avatar">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M12 2a8 8 0 0 0-8 8c0 5 8 12 8 12s8-7 8-12a8 8 0 0 0-8-8z" />
                    </svg>
                  </div>
                )}
                <div className="copilot-bubble-content">
                  {/* Render StateGraph Pipeline Trace */}
                  {m.graph_trace && renderStateGraphTrace(m.graph_trace, m.architecture_mode)}

                  {/* Render Agent Execution Activity Trace */}
                  {m.tool_calls && renderToolCallsTrace(m.tool_calls)}

                  <div className="copilot-bubble-text" style={{ whiteSpace: 'pre-line' }}>
                    {m.content}
                  </div>

                  {/* Render Autonomous Agent Executed Action Cards */}
                  {m.agent_actions && renderAgentActions(m.agent_actions)}

                  {/* Render Interactive 3D WebGL Concept Model */}
                  {m.concept_3d && (
                    <ConceptCanvas3D
                      conceptType={m.concept_3d.concept_type || 'neural_network'}
                      title={m.concept_3d.title}
                      description={m.concept_3d.description}
                    />
                  )}

                  {/* Render Structured Book Result Cards */}
                  {m.sources && renderBookCards(m.sources)}

                  {/* Render Policy and Loan Sources */}
                  {m.sources && renderPolicyAndLoanSources(m.sources)}

                  {/* Suggested Follow-up chips */}
                  {m.suggested_followups && m.suggested_followups.length > 0 && !isLoading && (
                    <div className="copilot-followups-block">
                      {m.suggested_followups.map((q, idx) => (
                        <button
                          key={idx}
                          type="button"
                          className="copilot-followup-pill"
                          onClick={() => handleSend(q)}
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                  )}

                  <div className="copilot-bubble-timestamp" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
                    <span>{m.timestamp}</span>
                    {m.role === 'assistant' && (
                      speakingMsgId === m.id ? (
                        <button
                          type="button"
                          onClick={stopSpeaking}
                          title="Stop AI speech narration"
                          style={{
                            background: 'rgba(239, 68, 68, 0.25)',
                            border: '1px solid rgba(239, 68, 68, 0.6)',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            fontSize: '0.72rem',
                            color: '#F87171',
                            padding: '1px 8px',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            fontWeight: 700,
                            boxShadow: '0 0 10px rgba(239, 68, 68, 0.35)',
                          }}
                        >
                          <span style={{ fontSize: '0.68rem' }}>⏹️</span> Stop Speaking
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => speakText(m.content, m.id)}
                          title="Listen to this explanation (Text-to-Speech)"
                          style={{
                            background: 'none',
                            border: 'none',
                            cursor: 'pointer',
                            fontSize: '0.75rem',
                            color: '#38bdf8',
                            padding: '0 4px',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '3px',
                            opacity: 0.85,
                          }}
                        >
                          🔊 Listen
                        </button>
                      )
                    )}
                  </div>
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="copilot-bubble-row bubble-assistant">
                <div className="copilot-avatar">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" />
                  </svg>
                </div>
                <div className="copilot-bubble-content">
                  <div className="copilot-thinking-indicator">
                    <div className="copilot-dot" />
                    <div className="copilot-dot" />
                    <div className="copilot-dot" />
                    <span className="copilot-thinking-label">
                      {loadingStatus}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {errorMessage && (
              <div className="alert alert-error" style={{ margin: '0.5rem 0', fontSize: '0.85rem' }}>
                {errorMessage}
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input Footer */}
          <form
            className="copilot-footer"
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
          >
            <div className="copilot-input-wrapper">
              <input
                ref={inputRef}
                type="text"
                className="copilot-input"
                placeholder="Ask about books, loans, availability, or policies..."
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                maxLength={500}
                disabled={isLoading}
              />
              <span className="copilot-char-counter">{inputMessage.length}/500</span>
            </div>

            <button
              type="button"
              className={`btn ${isListening ? 'btn-danger' : 'btn-secondary'} copilot-mic-btn`}
              onClick={toggleListening}
              title={isListening ? 'Listening... (Click to Stop)' : 'Voice Input (Click and Speak your query)'}
              style={{
                padding: '0 0.65rem',
                height: '38px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                backgroundColor: isListening ? '#ef4444' : undefined,
                color: isListening ? '#ffffff' : undefined,
                boxShadow: isListening ? '0 0 12px rgba(239, 68, 68, 0.8)' : undefined,
                fontSize: '1rem',
              }}
            >
              {isListening ? '⏹️' : '🎤'}
            </button>

            <button
              type="button"
              className="btn btn-secondary copilot-vision-btn"
              onClick={() => setShowVisionModal(true)}
              title="Multimodal Analysis: Images, Voice Recordings (mic), PDF Papers, Word, or Slides"
              style={{ padding: '0 0.65rem', height: '38px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
            >
              🎙️📷
            </button>

            <button
              type="submit"
              className="btn btn-primary copilot-send-btn"
              disabled={isLoading || !inputMessage.trim()}
              aria-label="Send query"
            >
              {isLoading ? (
                '...'
              ) : (
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="22" y1="2" x2="11" y2="13" />
                  <polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
              )}
            </button>
          </form>
        </aside>
      )}

      {showVisionModal && (
        <VisionSearchModal
          onClose={() => setShowVisionModal(false)}
          onSelectBook={onSelectBook}
        />
      )}

      {showKeyModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 999999,
            backgroundColor: 'rgba(3, 7, 18, 0.85)',
            backdropFilter: 'blur(10px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1rem',
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowKeyModal(false);
          }}
        >
          <div
            style={{
              backgroundColor: '#0c1322',
              border: '1px solid rgba(56, 189, 248, 0.35)',
              borderRadius: '14px',
              maxWidth: '520px',
              width: '100%',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7)',
              padding: '1.5rem',
              color: '#f8fafc',
            }}
          >
            {/* Modal Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <span style={{ fontSize: '1.25rem' }}>🔑</span>
                <div>
                  <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700, color: '#f8fafc' }}>
                    Multi-Provider AI Gateway (BYOK)
                  </h3>
                  <div style={{ fontSize: '0.72rem', color: '#64748b' }}>
                    Omnichannel Model Routing & Quota Optimization
                  </div>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowKeyModal(false)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#94a3b8',
                  fontSize: '1.2rem',
                  cursor: 'pointer',
                  padding: '4px',
                }}
              >
                ✕
              </button>
            </div>

            {/* Live Gateway Routing Status */}
            <div
              style={{
                background: 'rgba(255, 255, 255, 0.03)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                borderRadius: '8px',
                padding: '0.65rem 0.85rem',
                marginBottom: '1rem',
                fontSize: '0.78rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.35rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: '#94a3b8' }}>⚡ Real-Time Chat Engine:</span>
                <span style={{ fontWeight: 600, color: providerKeys.groq.trim() ? '#4ade80' : providerKeys.openai.trim() ? '#38bdf8' : providerKeys.anthropic.trim() ? '#fb923c' : providerKeys.gemini.trim() ? '#a78bfa' : '#94a3b8' }}>
                  {providerKeys.groq.trim() ? 'Groq LPU (Llama 3.3 70B)' : providerKeys.openai.trim() ? 'OpenAI (GPT-4o-mini)' : providerKeys.anthropic.trim() ? 'Anthropic (Claude 3.5)' : providerKeys.gemini.trim() ? 'Google Gemini' : 'Institutional Default'}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: '#94a3b8' }}>📸 Multimodal OCR & Vision:</span>
                <span style={{ fontWeight: 600, color: providerKeys.gemini.trim() ? '#a78bfa' : providerKeys.openai.trim() ? '#38bdf8' : providerKeys.anthropic.trim() ? '#fb923c' : '#94a3b8' }}>
                  {providerKeys.gemini.trim() ? 'Google Gemini Multimodal' : providerKeys.openai.trim() ? 'OpenAI GPT-4o Vision' : providerKeys.anthropic.trim() ? 'Claude 3.5 Vision' : 'Institutional Default'}
                </span>
              </div>
            </div>

            {/* Provider Tabs */}
            <div style={{ display: 'flex', gap: '0.35rem', marginBottom: '1rem', background: 'rgba(255, 255, 255, 0.05)', padding: '3px', borderRadius: '8px' }}>
              {(
                [
                  { id: 'groq', label: '⚡ Groq', badge: 'Fastest' },
                  { id: 'gemini', label: '🪐 Gemini', badge: 'Vision' },
                  { id: 'openai', label: '🧠 OpenAI', badge: 'GPT-4o' },
                  { id: 'anthropic', label: '🎭 Claude', badge: '3.5' },
                ] as const
              ).map((p) => {
                const isSaved = Boolean(providerKeys[p.id].trim());
                const isActive = activeProviderTab === p.id;
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => {
                      setActiveProviderTab(p.id);
                      setKeyMessage(null);
                    }}
                    style={{
                      flex: 1,
                      padding: '0.45rem 0.35rem',
                      borderRadius: '6px',
                      border: 'none',
                      background: isActive ? 'rgba(56, 189, 248, 0.25)' : 'transparent',
                      color: isActive ? '#38bdf8' : '#94a3b8',
                      fontSize: '0.76rem',
                      fontWeight: isActive ? 700 : 500,
                      cursor: 'pointer',
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      gap: '2px',
                      position: 'relative',
                    }}
                  >
                    <span>{p.label}</span>
                    {isSaved && (
                      <span style={{ width: '4px', height: '4px', borderRadius: '50%', backgroundColor: '#4ade80' }} />
                    )}
                  </button>
                );
              })}
            </div>

            {keyMessage && (
              <div
                style={{
                  padding: '0.55rem 0.85rem',
                  borderRadius: '8px',
                  marginBottom: '1rem',
                  fontSize: '0.8rem',
                  backgroundColor: keyMessage.type === 'success' ? 'rgba(34, 197, 94, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                  color: keyMessage.type === 'success' ? '#4ade80' : '#f87171',
                  border: `1px solid ${keyMessage.type === 'success' ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
                }}
              >
                {keyMessage.text}
              </div>
            )}

            {/* Active Provider Card */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
                  <label style={{ fontSize: '0.78rem', color: '#cbd5e1', fontWeight: 600 }}>
                    {activeProviderTab === 'groq' && '⚡ Groq API Key (Llama 3.3 70B - 500+ tokens/s)'}
                    {activeProviderTab === 'gemini' && '🪐 Google Gemini API Key (Multimodal Vision & Audio)'}
                    {activeProviderTab === 'openai' && '🧠 OpenAI API Key (GPT-4o / GPT-4o-mini)'}
                    {activeProviderTab === 'anthropic' && '🎭 Anthropic API Key (Claude 3.5 Sonnet / Haiku)'}
                  </label>
                  <span
                    style={{
                      fontSize: '0.7rem',
                      color: providerKeys[activeProviderTab].trim() ? '#4ade80' : '#64748b',
                      fontWeight: 600,
                    }}
                  >
                    {providerKeys[activeProviderTab].trim() ? '● Configured' : '○ Not Configured'}
                  </span>
                </div>
                <input
                  type="password"
                  value={providerKeys[activeProviderTab]}
                  onChange={(e) => {
                    const val = e.target.value;
                    setProviderKeys((prev) => ({ ...prev, [activeProviderTab]: val }));
                  }}
                  placeholder={
                    activeProviderTab === 'groq'
                      ? 'gsk_... (Paste Groq API Key)'
                      : activeProviderTab === 'gemini'
                      ? 'AIzaSy... (Paste Gemini Key)'
                      : activeProviderTab === 'openai'
                      ? 'sk-... (Paste OpenAI Key)'
                      : 'sk-ant-... (Paste Anthropic Key)'
                  }
                  style={{
                    width: '100%',
                    padding: '0.55rem 0.75rem',
                    borderRadius: '8px',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    backgroundColor: 'rgba(15, 23, 42, 0.8)',
                    color: '#f8fafc',
                    fontSize: '0.88rem',
                    fontFamily: 'monospace',
                    boxSizing: 'border-box',
                  }}
                />
              </div>

              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.25rem' }}>
                <button
                  type="button"
                  onClick={() => handleSaveKey(activeProviderTab)}
                  disabled={!providerKeys[activeProviderTab].trim()}
                  className="btn btn-primary btn-sm"
                  style={{ flex: 1, padding: '0.5rem 0.8rem' }}
                >
                  Save {activeProviderTab.toUpperCase()} Key
                </button>
                <button
                  type="button"
                  onClick={() => handleTestKey(activeProviderTab)}
                  disabled={keyTesting || !providerKeys[activeProviderTab].trim()}
                  className="btn btn-secondary btn-sm"
                  style={{ padding: '0.5rem 0.8rem' }}
                >
                  {keyTesting ? 'Testing...' : '⚡ Test Key'}
                </button>
                {Boolean(providerKeys[activeProviderTab].trim()) && (
                  <button
                    type="button"
                    onClick={() => handleClearKey(activeProviderTab)}
                    className="btn btn-outline btn-sm"
                    style={{ color: '#f87171', borderColor: 'rgba(239, 68, 68, 0.35)' }}
                  >
                    Clear
                  </button>
                )}
              </div>
            </div>

            <div
              style={{
                marginTop: '1.25rem',
                paddingTop: '0.85rem',
                borderTop: '1px solid rgba(255, 255, 255, 0.1)',
                fontSize: '0.76rem',
                color: '#64748b',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <span>Get API key from provider console:</span>
              <a
                href={
                  activeProviderTab === 'groq'
                    ? 'https://console.groq.com/keys'
                    : activeProviderTab === 'gemini'
                    ? 'https://aistudio.google.com/app/apikey'
                    : activeProviderTab === 'openai'
                    ? 'https://platform.openai.com/api-keys'
                    : 'https://console.anthropic.com/'
                }
                target="_blank"
                rel="noreferrer"
                style={{ color: '#38bdf8', textDecoration: 'none', fontWeight: 600 }}
              >
                Open {activeProviderTab.toUpperCase()} Console ↗
              </a>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
