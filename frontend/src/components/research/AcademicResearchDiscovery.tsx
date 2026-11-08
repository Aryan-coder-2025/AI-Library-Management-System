import React, { useState } from 'react';
import { apiFetch } from '../../services/apiClient';
import type { AcademicPaperResult, AcademicSearchResponse } from '../../types/library';

export const AcademicResearchDiscovery: React.FC = () => {
  const [query, setQuery] = useState('');
  const [papers, setPapers] = useState<AcademicPaperResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);
  const [extractedTopic, setExtractedTopic] = useState<string | null>(null);

  // Filters
  const [selectedProvider, setSelectedProvider] = useState<string>('all');
  const [openAccessOnly, setOpenAccessOnly] = useState<boolean>(false);
  const [yearFilter, setYearFilter] = useState<string>('');
  const [expandedAbstracts, setExpandedAbstracts] = useState<Record<string, boolean>>({});

  const cleanConversationalPreamble = (raw: string): string => {
    let cleaned = raw.trim().replace(/[\?\.!]+$/, '');
    const patterns = [
      /^(?:ok|okay|hey|hi|hello|please)[\s,]+/i,
      /^(?:can|could|would)\s+you\s+(?:please\s+)?(?:tell|show|give|find|search|recommend|suggest)\s+(?:me\s+)?(?:about\s+)?/i,
      /^(?:tell|show|give|find|search)\s+(?:me\s+)?(?:about\s+)?/i,
      /^(?:what\s+are\s+(?:some\s+)?(?:famous|the\s+best|top|the\s+latest|popular|major)\s+)?(?:research\s+)?(?:papers|articles|studies|publications|books)\s+(?:on|about|regarding|in)\s+/i,
      /^(?:some\s+)?(?:famous|best|top|latest|popular|major)\s+(?:research\s+)?(?:papers|articles|studies|publications)\s+(?:on|about|regarding|in)\s+/i,
      /^(?:papers|articles|studies|publications)\s+(?:on|about|regarding|in)\s+/i,
      /^(?:looking\s+for|search\s+for|find)\s+(?:papers|articles|studies)?\s*(?:on|about|regarding)?\s+/i,
    ];
    let changed = true;
    while (changed) {
      changed = false;
      for (const p of patterns) {
        const next = cleaned.replace(p, '').trim();
        if (next && next !== cleaned) {
          cleaned = next;
          changed = true;
        }
      }
    }
    return cleaned || raw.trim();
  };

  const handleSearch = async (e?: React.FormEvent, customQuery?: string) => {
    if (e) e.preventDefault();
    const rawSearchQuery = (customQuery !== undefined ? customQuery : query).trim();
    if (!rawSearchQuery) return;

    const cleaned = cleanConversationalPreamble(rawSearchQuery);
    if (cleaned !== rawSearchQuery) {
      setExtractedTopic(cleaned);
    } else {
      setExtractedTopic(null);
    }

    setLoading(true);
    setError(null);
    setSearched(true);

    try {
      const params = new URLSearchParams();
      params.set('q', rawSearchQuery);
      params.set('limit', '20');

      if (selectedProvider !== 'all') {
        params.set('providers', selectedProvider);
      }
      if (openAccessOnly) {
        params.set('is_oa', 'true');
      }
      if (yearFilter.trim()) {
        params.set('year', yearFilter.trim());
      }

      const res = await apiFetch<AcademicSearchResponse>(`/api/research/search?${params.toString()}`);
      setPapers(res.results);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Scholarly research search failed.';
      setError(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setLoading(false);
    }
  };

  const toggleAbstract = (id: string) => {
    setExpandedAbstracts((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const getProviderColor = (provider: string) => {
    switch (provider.toLowerCase()) {
      case 'openalex':
        return '#0284c7';
      case 'arxiv':
        return '#ea580c';
      case 'crossref':
        return '#059669';
      default:
        return 'var(--text-muted)';
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Search Header Banner */}
      <div
        style={{
          background: 'var(--glass-card)',
          padding: '1.5rem',
          borderRadius: '12px',
          boxShadow: 'var(--shadow-md)',
          border: '1px solid var(--border-medium)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
          <span style={{ fontSize: '1.5rem' }}>🌐</span>
          <div>
            <h3 style={{ margin: 0, fontSize: '1.15rem', color: 'var(--text-primary)' }}>
              Global Academic Research Discovery
            </h3>
            <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Direct federated search across <strong>OpenAlex</strong> (250M+ items), <strong>arXiv</strong> (Open Access Preprints), and <strong>Crossref</strong> (DOI registry).
            </p>
          </div>
        </div>

        {/* Search Input Bar */}
        <form onSubmit={(e) => handleSearch(e)} style={{ marginTop: '1rem', display: 'flex', gap: '0.75rem' }}>
          <input
            type="text"
            className="form-input"
            style={{ flex: 1, padding: '0.65rem 1rem', fontSize: '0.95rem' }}
            placeholder="Search papers by topic or keywords (e.g. 'Nanorobotics', 'CRISPR Cas9', 'Quantum Computing')..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button
            type="submit"
            className="btn btn-primary"
            style={{ padding: '0.65rem 1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}
            disabled={loading || !query.trim()}
          >
            {loading ? 'Searching APIs...' : 'Search Papers'}
          </button>
        </form>

        {/* Intent extraction notice */}
        {extractedTopic && (
          <div
            style={{
              marginTop: '0.65rem',
              padding: '0.4rem 0.75rem',
              borderRadius: '6px',
              background: 'rgba(6, 182, 212, 0.12)',
              border: '1px solid rgba(6, 182, 212, 0.3)',
              color: 'var(--color-accent)',
              fontSize: '0.8rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
            }}
          >
            <span>⚡</span>
            <span>
              Scholarly Intent Focused: Extracted <strong>"{extractedTopic}"</strong> (conversational preambles filtered for title matching on Crossref & arXiv).
            </span>
          </div>
        )}

        {/* Suggested Queries */}
        <div style={{ marginTop: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Quick Exploration:</span>
          {['Nanorobotics', 'Deep Learning', 'Quantum Computing', 'CRISPR Gene Editing', 'Renewable Energy Systems', 'Graph Neural Networks'].map((topic) => (
            <button
              key={topic}
              type="button"
              onClick={() => {
                setQuery(topic);
                handleSearch(undefined, topic);
              }}
              style={{
                background: 'var(--bg-subtle)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '16px',
                padding: '0.2rem 0.65rem',
                fontSize: '0.75rem',
                color: 'var(--color-secondary-violet)',
                cursor: 'pointer',
              }}
            >
              {topic}
            </button>
          ))}
        </div>

        {/* Filter Bar */}
        <div style={{ marginTop: '1rem', paddingTop: '0.75rem', borderTop: '1px solid var(--card-border)', display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem' }}>
            <label htmlFor="provider-filter" style={{ color: 'var(--text-secondary)' }}>Provider:</label>
            <select
              id="provider-filter"
              value={selectedProvider}
              onChange={(e) => setSelectedProvider(e.target.value)}
              className="form-input"
              style={{ padding: '0.3rem 0.6rem', fontSize: '0.82rem' }}
            >
              <option value="all">All Providers (Federated)</option>
              <option value="openalex">OpenAlex Only</option>
              <option value="arxiv">arXiv Only</option>
              <option value="crossref">Crossref Only</option>
            </select>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem' }}>
            <label htmlFor="year-filter" style={{ color: 'var(--text-secondary)' }}>Year:</label>
            <input
              id="year-filter"
              type="number"
              min="1990"
              max="2030"
              placeholder="e.g. 2024"
              value={yearFilter}
              onChange={(e) => setYearFilter(e.target.value)}
              className="form-input"
              style={{ width: '90px', padding: '0.3rem 0.5rem', fontSize: '0.82rem' }}
            />
          </div>

          <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem', color: 'var(--text-secondary)', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={openAccessOnly}
              onChange={(e) => setOpenAccessOnly(e.target.checked)}
            />
            <span>Open Access Only 🔓</span>
          </label>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="alert alert-error" role="alert">
          <span>{error}</span>
        </div>
      )}

      {/* Results Section */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '3rem 0', color: 'var(--text-secondary)' }}>
          <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>⏳</div>
          <p>Querying OpenAlex, arXiv, and Crossref APIs...</p>
        </div>
      ) : searched && papers.length === 0 ? (
        <div
          style={{
            background: 'var(--card-bg)',
            padding: '2.5rem',
            borderRadius: '12px',
            textAlign: 'center',
            border: '1px solid var(--card-border)',
            color: 'var(--text-muted)',
          }}
        >
          <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>🔍</div>
          <h4>No academic research papers found</h4>
          <p style={{ fontSize: '0.875rem' }}>Try adjusting your search terms, removing filters, or searching for broader topics.</p>
        </div>
      ) : (
        papers.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>Displaying {papers.length} scholarly results</span>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <span style={{ fontSize: '0.75rem', background: '#0284c720', color: '#38bdf8', padding: '0.15rem 0.5rem', borderRadius: '4px' }}>OpenAlex</span>
                <span style={{ fontSize: '0.75rem', background: '#ea580c20', color: '#fb923c', padding: '0.15rem 0.5rem', borderRadius: '4px' }}>arXiv</span>
                <span style={{ fontSize: '0.75rem', background: '#05966920', color: '#34d399', padding: '0.15rem 0.5rem', borderRadius: '4px' }}>Crossref</span>
              </div>
            </div>

            {papers.map((paper) => {
              const isExpanded = !!expandedAbstracts[paper.id];
              return (
                <div
                  key={paper.id}
                  style={{
                    background: 'var(--card-bg)',
                    padding: '1.25rem',
                    borderRadius: '10px',
                    border: '1px solid var(--card-border)',
                    boxShadow: 'var(--card-shadow)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.65rem',
                  }}
                >
                  {/* Top Badges & Venue */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span
                        style={{
                          backgroundColor: `${getProviderColor(paper.source_provider)}22`,
                          color: getProviderColor(paper.source_provider),
                          border: `1px solid ${getProviderColor(paper.source_provider)}44`,
                          padding: '0.15rem 0.5rem',
                          borderRadius: '4px',
                          fontSize: '0.72rem',
                          fontWeight: 700,
                          textTransform: 'uppercase',
                        }}
                      >
                        {paper.source_provider}
                      </span>

                      {paper.open_access && (
                        <span
                          style={{
                            backgroundColor: '#10b98122',
                            color: '#10b981',
                            padding: '0.15rem 0.45rem',
                            borderRadius: '4px',
                            fontSize: '0.72rem',
                            fontWeight: 600,
                          }}
                        >
                          🔓 Open Access
                        </span>
                      )}

                      {paper.publication_year && (
                        <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                          📅 {paper.publication_year}
                        </span>
                      )}
                    </div>

                    {paper.citation_count !== null && paper.citation_count !== undefined && (
                      <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                        📊 {paper.citation_count} Citations
                      </span>
                    )}
                  </div>

                  {/* Title */}
                  <h4 style={{ margin: 0, fontSize: '1.05rem', color: 'var(--text-primary)', lineHeight: 1.4 }}>
                    {paper.url ? (
                      <a
                        href={paper.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ color: 'var(--brand-secondary)', textDecoration: 'none' }}
                      >
                        {paper.title} ↗
                      </a>
                    ) : (
                      paper.title
                    )}
                  </h4>

                  {/* Authors & Venue */}
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                    {paper.authors.length > 0 && (
                      <span>✍️ {paper.authors.slice(0, 5).join(', ')}{paper.authors.length > 5 ? ` +${paper.authors.length - 5} more` : ''}</span>
                    )}
                    {paper.venue && (
                      <span style={{ fontStyle: 'italic', color: 'var(--text-muted)' }}>
                        • {paper.venue}
                      </span>
                    )}
                  </div>

                  {/* Abstract */}
                  {paper.abstract && (
                    <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.5, background: 'var(--bg-glass)', padding: '0.65rem 0.85rem', borderRadius: '6px' }}>
                      <p style={{ margin: 0 }}>
                        {isExpanded ? paper.abstract : `${paper.abstract.slice(0, 240)}...`}
                      </p>
                      {paper.abstract.length > 240 && (
                        <button
                          type="button"
                          onClick={() => toggleAbstract(paper.id)}
                          style={{
                            background: 'none',
                            border: 'none',
                            color: 'var(--brand-secondary)',
                            fontSize: '0.75rem',
                            cursor: 'pointer',
                            padding: 0,
                            marginTop: '0.35rem',
                            fontWeight: 600,
                          }}
                        >
                          {isExpanded ? 'Show less ▲' : 'Read full abstract ▼'}
                        </button>
                      )}
                    </div>
                  )}

                  {/* Identifiers & Links */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.25rem', paddingTop: '0.5rem', borderTop: '1px solid var(--card-border)' }}>
                    <div style={{ display: 'flex', gap: '0.75rem', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                      {paper.doi && (
                        <span>DOI: <code style={{ color: 'var(--text-secondary)' }}>{paper.doi}</code></span>
                      )}
                      {paper.arxiv_id && (
                        <span>arXiv: <code style={{ color: 'var(--text-secondary)' }}>{paper.arxiv_id}</code></span>
                      )}
                    </div>

                    {paper.url && (
                      <a
                        href={paper.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn btn-secondary btn-sm"
                        style={{ fontSize: '0.78rem', padding: '0.3rem 0.65rem' }}
                      >
                        View Official Paper ↗
                      </a>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )
      )}
    </div>
  );
};

