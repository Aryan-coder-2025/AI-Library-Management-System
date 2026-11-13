import React, { useEffect, useRef, useState } from 'react';
import { apiFetch } from '../services/apiClient';
import type { CopilotAgentAction, CopilotMessage, CopilotSource, CopilotToolExecution, UserProfile } from '../types/library';
import { VisionSearchModal } from './VisionSearchModal';
import { ConceptCanvas3D } from './ConceptCanvas3D';

interface AICopilotDrawerProps {
  currentUser: UserProfile;
  isOpen: boolean;
  onClose: () => void;
  onOpen: () => void;
  onSelectBook: (bookId: number) => void;
  onNavigateTab?: (tab: string) => void;
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
  const recognitionRef = useRef<any>(null);

  const speakText = (text: string) => {
    if (typeof window === 'undefined' || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const clean = text
      .replace(/[*_#`~\[\]()]/g, '')
      .replace(/https?:\/\/\S+/g, '')
      .replace(/[🪐✅📚ℹ️⚠️•]/g, '')
      .trim();
    if (!clean) return;
    const utterance = new SpeechSynthesisUtterance(clean);
    utterance.rate = 1.05;
    utterance.pitch = 1.0;
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
      };

      setMessages((prev) => [...prev, assistantMsg]);

      if (isVoiceEnabled && resp.answer) {
        speakText(resp.answer);
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
          className="copilot-drawer"
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
                      <button
                        type="button"
                        onClick={() => speakText(m.content)}
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
    </>
  );
};
