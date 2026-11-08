import React, { useState } from 'react';
import type { ModelComparisonResponse } from '../../types/knowledge';
import { evaluateModelComparison } from '../../services/knowledgeApi';

export const ModelComparisonStudio: React.FC = () => {
  const [prompt, setPrompt] = useState<string>(
    'What are the borrowing policies and loan duration limits for students and faculty?'
  );
  const [includeRag, setIncludeRag] = useState<boolean>(true);
  const [loading, setLoading] = useState<boolean>(false);
  const [comparisonResult, setComparisonResult] = useState<ModelComparisonResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleRunComparison = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const data = await evaluateModelComparison({
        prompt,
        models: ['local-deterministic', 'gemini-1.5-pro', 'gpt-4o'],
        include_rag_context: includeRag,
      });
      setComparisonResult(data);
    } catch (err: any) {
      setError(err.message || 'Comparison execution failed');
    } finally {
      setLoading(false);
    }
  };

  const hasSimulated = comparisonResult?.results.some(
    (r) => r.provider.includes('Simulated') || r.provider.includes('Unconfigured')
  );

  const getProviderBadge = (res: { provider: string; error?: string | null }) => {
    if (res.error) {
      return {
        label: '🔴 Offline / Error',
        bg: '#fee2e2',
        color: '#991b1b',
        border: '#fca5a5',
      };
    }
    if (res.provider.includes('Live API') || res.provider.includes('Live Remote')) {
      return {
        label: '🟢 Live Remote API',
        bg: '#dcfce7',
        color: '#166534',
        border: '#86efac',
      };
    }
    if (res.provider.includes('Simulated') || res.provider.includes('Unconfigured')) {
      return {
        label: '🟡 Simulated Fallback',
        bg: '#fef3c7',
        color: '#92400e',
        border: '#fcd34d',
      };
    }
    if (res.provider.includes('Local') || res.provider.includes('Rule-Based')) {
      return {
        label: '⚙️ Deterministic Planner',
        bg: '#e0f2fe',
        color: '#075985',
        border: '#7dd3fc',
      };
    }
    return {
      label: 'ℹ️ Standard',
      bg: '#f1f5f9',
      color: '#334155',
      border: '#cbd5e1',
    };
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Studio Header & Configuration Form */}
      <div
        style={{
          background: 'var(--card-bg)',
          padding: '1.25rem',
          borderRadius: '12px',
          border: '1px solid var(--card-border)',
          boxShadow: 'var(--card-shadow)',
        }}
      >
        <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.15rem', color: 'var(--text-primary)' }}>
          ⚖️ Modern AI Model Comparison Studio
        </h3>
        <p style={{ margin: '0 0 1rem 0', fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
          Evaluate identical prompts across Google Gemini, OpenAI, and Local Deterministic planners.
          Compare latency, token usage, and factual grounding against library knowledge.
        </p>

        <form onSubmit={handleRunComparison} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>
              Evaluation Prompt:
            </label>
            <textarea
              rows={3}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Enter library prompt to compare..."
              style={{
                width: '100%',
                padding: '0.6rem 0.85rem',
                borderRadius: '8px',
                border: '1px solid var(--card-border)',
                background: 'var(--bg-tertiary)',
                color: 'var(--text-primary)',
                fontSize: '0.9rem',
                fontFamily: 'inherit',
                boxSizing: 'border-box',
              }}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', color: 'var(--text-secondary)', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={includeRag}
                onChange={(e) => setIncludeRag(e.target.checked)}
              />
              Inject Retrieved Library RAG Context
            </label>

            <button type="submit" className="btn btn-primary" disabled={loading} style={{ fontWeight: 700 }}>
              {loading ? 'Evaluating Models...' : '🚀 Run Multi-Model Comparison'}
            </button>
          </div>
        </form>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      {/* Side-by-Side Model Comparison Grid */}
      {comparisonResult && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h4 style={{ margin: 0, fontSize: '1rem', color: 'var(--text-primary)' }}>
              Evaluation Results ({comparisonResult.results.length} models)
            </h4>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Evaluated at: {new Date(comparisonResult.timestamp).toLocaleTimeString()}
            </span>
          </div>

          {/* Provider Telemetry Transparency Banner (IMP-AI-02) */}
          {hasSimulated && (
            <div
              style={{
                background: 'rgba(245, 158, 11, 0.12)',
                border: '1px solid rgba(245, 158, 11, 0.3)',
                borderRadius: '8px',
                padding: '0.75rem 1rem',
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.65rem',
                color: '#f59e0b',
                fontSize: '0.825rem',
                lineHeight: '1.45',
              }}
            >
              <span style={{ fontSize: '1.15rem', lineHeight: 1 }}>⚠️</span>
              <div>
                <strong>Notice on AI Provider Telemetry:</strong> One or more models are operating under simulated development benchmarks because external provider API credentials are not configured in the host environment. Reported latencies and token counts reflect standardized local simulation fixtures rather than live remote provider telemetry. Local Deterministic results reflect live rule-based planning.
              </div>
            </div>
          )}

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
              gap: '1rem',
              alignItems: 'stretch',
            }}
          >
            {comparisonResult.results.map((res) => {
              const badge = getProviderBadge(res);
              return (
                <div
                  key={res.model_name}
                  style={{
                    background: 'var(--card-bg)',
                    borderRadius: '12px',
                    border: '1px solid var(--card-border)',
                    padding: '1rem',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    boxShadow: 'var(--card-shadow)',
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                      <div>
                        <strong style={{ fontSize: '1rem', color: 'var(--text-primary)' }}>{res.model_name}</strong>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{res.provider}</div>
                        <span
                          style={{
                            display: 'inline-block',
                            marginTop: '4px',
                            background: badge.bg,
                            color: badge.color,
                            border: `1px solid ${badge.border}`,
                            borderRadius: '4px',
                            padding: '1px 6px',
                            fontSize: '0.7rem',
                            fontWeight: 600,
                          }}
                        >
                          {badge.label}
                        </span>
                      </div>
                      <span
                        style={{
                          background: 'var(--bg-tertiary)',
                          padding: '2px 8px',
                          borderRadius: '12px',
                          fontSize: '0.75rem',
                          fontWeight: 600,
                          color: 'var(--text-secondary)',
                          border: '1px solid var(--card-border)',
                        }}
                      >
                        ⚡ {res.latency_ms} ms
                      </span>
                    </div>

                    {/* Grounding & Token Metrics */}
                    <div
                      style={{
                        display: 'flex',
                        gap: '0.75rem',
                        fontSize: '0.75rem',
                        background: 'var(--bg-tertiary)',
                        padding: '0.4rem 0.6rem',
                        borderRadius: '6px',
                        marginBottom: '0.75rem',
                        color: 'var(--text-secondary)',
                      }}
                    >
                      <span>
                        <strong>Grounding:</strong> {(res.factual_grounding_score * 100).toFixed(0)}%
                      </span>
                      <span>
                        <strong>Tokens:</strong> {res.token_usage?.total_tokens ?? 'N/A'}
                      </span>
                      <span>
                        <strong>Citations:</strong> {res.citations_count}
                      </span>
                    </div>

                    {/* Response Text */}
                    <div
                      style={{
                        fontSize: '0.85rem',
                        color: 'var(--text-primary)',
                        lineHeight: '1.45',
                        background: 'var(--bg-tertiary)',
                        padding: '0.75rem',
                        borderRadius: '6px',
                        border: '1px solid var(--card-border)',
                        minHeight: '100px',
                        whiteSpace: 'pre-wrap',
                      }}
                    >
                      {res.error ? (
                        <span style={{ color: '#dc2626' }}>Error: {res.error}</span>
                      ) : (
                        res.response_text
                      )}
                    </div>
                  </div>

                  <div style={{ marginTop: '0.75rem', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                    Audited factual grounding verified against library policy metadata.
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
