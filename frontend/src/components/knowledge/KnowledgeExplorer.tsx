import React, { useState, useEffect } from 'react';
import type { SubjectTree, KnowledgeSearchResult } from '../../types/knowledge';
import { getSubjectTree, searchKnowledge } from '../../services/knowledgeApi';
import { AcademicResearchDiscovery } from '../research/AcademicResearchDiscovery';

export const KnowledgeExplorer: React.FC = () => {
  const [activeSubTab, setActiveSubTab] = useState<'taxonomy' | 'research'>('taxonomy');
  const [subjects, setSubjects] = useState<SubjectTree[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [searchResults, setSearchResults] = useState<KnowledgeSearchResult[]>([]);
  const [searching, setSearching] = useState<boolean>(false);
  const [hasSearched, setHasSearched] = useState<boolean>(false);
  const [lastSearchedQuery, setLastSearchedQuery] = useState<string>('');
  const [searchError, setSearchError] = useState<string | null>(null);
  const [selectedSubject, setSelectedSubject] = useState<SubjectTree | null>(null);

  useEffect(() => {
    async function loadTree() {
      try {
        const data = await getSubjectTree();
        setSubjects(data);
        if (data.length > 0) setSelectedSubject(data[0]);
      } catch (err) {
        console.error('Failed to load knowledge hierarchy', err);
      } finally {
        setLoading(false);
      }
    }
    loadTree();
  }, []);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = searchQuery.trim();
    if (!q) {
      setSearchResults([]);
      setHasSearched(false);
      return;
    }
    setSearching(true);
    setSearchError(null);
    try {
      const res = await searchKnowledge(q);
      setSearchResults(res.results || []);
      setHasSearched(true);
      setLastSearchedQuery(q);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Knowledge search failed';
      setSearchError(msg.replace(/^\d+:\s*/, ''));
      setHasSearched(true);
      setLastSearchedQuery(q);
    } finally {
      setSearching(false);
    }
  };

  const handleSelectResult = (item: KnowledgeSearchResult) => {
    // Navigate and highlight the matching subject in the taxonomy tree
    const matchingSubject = subjects.find(
      (s) => item.context_path.toLowerCase().includes(s.name.toLowerCase()) || s.id === item.id
    );
    if (matchingSubject) {
      setSelectedSubject(matchingSubject);
    }
  };

  const handleClearSearch = () => {
    setSearchResults([]);
    setHasSearched(false);
    setSearchQuery('');
    setSearchError(null);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Sub-tab Switcher: Knowledge Graph vs External Research Discovery */}
      <div style={{ display: 'flex', gap: '0.5rem', borderBottom: '1px solid var(--card-border)', paddingBottom: '0.75rem' }}>
        <button
          type="button"
          className={`btn ${activeSubTab === 'taxonomy' ? 'btn-primary' : 'btn-secondary'} btn-sm`}
          onClick={() => setActiveSubTab('taxonomy')}
          style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}
        >
          <span>🧠</span>
          <span>Library Knowledge Taxonomy</span>
        </button>
        <button
          type="button"
          className={`btn ${activeSubTab === 'research' ? 'btn-primary' : 'btn-secondary'} btn-sm`}
          onClick={() => setActiveSubTab('research')}
          style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}
        >
          <span>🌐</span>
          <span>Global Academic Research (OpenAlex / arXiv / Crossref)</span>
        </button>
      </div>

      {activeSubTab === 'research' ? (
        <AcademicResearchDiscovery />
      ) : (
        <>
          {/* Header & Concept Search */}
      <div
        style={{
          background: 'var(--card-bg)',
          padding: '1.25rem',
          borderRadius: '12px',
          boxShadow: 'var(--card-shadow)',
          border: '1px solid var(--card-border)',
        }}
      >
        <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.15rem', color: 'var(--text-primary)' }}>
          🧠 Academic Knowledge Representation & Search-Based Navigation
        </h3>
        <p style={{ margin: '0 0 1rem 0', fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
          Explore structured subject taxonomies, topics, and underlying concepts linked to the library collection.
        </p>

        <form onSubmit={handleSearch} style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: '240px', position: 'relative' }}>
            <input
              type="text"
              placeholder="Search concepts, topics, or disciplines (e.g. 'dijkstra', 'neural networks', 'algebra')..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                width: '100%',
                padding: '0.65rem 2.2rem 0.65rem 0.85rem',
                borderRadius: '8px',
                border: '1px solid var(--border-medium, rgba(148, 163, 184, 0.25))',
                background: 'var(--bg-tertiary, #141F36)',
                color: 'var(--text-primary, #F8FAFC)',
                fontSize: '0.9rem',
                outline: 'none',
                boxSizing: 'border-box',
              }}
              onFocus={(e) => {
                e.currentTarget.style.borderColor = 'var(--accent-cyan, #38BDF8)';
                e.currentTarget.style.boxShadow = '0 0 0 2px rgba(56, 189, 248, 0.2)';
              }}
              onBlur={(e) => {
                e.currentTarget.style.borderColor = 'var(--border-medium, rgba(148, 163, 184, 0.25))';
                e.currentTarget.style.boxShadow = 'none';
              }}
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                style={{
                  position: 'absolute',
                  right: '0.6rem',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--text-muted, #94A3B8)',
                  cursor: 'pointer',
                  fontSize: '0.85rem',
                  padding: '2px 4px',
                }}
                title="Clear input"
              >
                ✕
              </button>
            )}
          </div>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={searching}
            style={{
              padding: '0.65rem 1.25rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              fontWeight: 600,
              cursor: searching ? 'not-allowed' : 'pointer',
            }}
          >
            {searching ? '⏳ Searching...' : '🔍 Search Knowledge'}
          </button>
        </form>

        {/* Quick query recommendation chips */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.75rem', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted, #64748B)' }}>Popular queries:</span>
          {[
            "dijkstras algorithm",
            "neural networks",
            "relational database",
            "linear algebra",
            "microservices",
          ].map((tag) => (
            <button
              key={tag}
              type="button"
              onClick={() => {
                setSearchQuery(tag);
                // Trigger search immediately
                setSearching(true);
                setSearchError(null);
                searchKnowledge(tag)
                  .then((res) => {
                    setSearchResults(res.results || []);
                    setHasSearched(true);
                    setLastSearchedQuery(tag);
                  })
                  .catch((err) => {
                    const msg = err instanceof Error ? err.message : 'Knowledge search failed';
                    setSearchError(msg.replace(/^\d+:\s*/, ''));
                    setHasSearched(true);
                    setLastSearchedQuery(tag);
                  })
                  .finally(() => setSearching(false));
              }}
              style={{
                fontSize: '0.75rem',
                padding: '2px 8px',
                borderRadius: '12px',
                background: 'rgba(56, 189, 248, 0.1)',
                border: '1px solid rgba(56, 189, 248, 0.25)',
                color: 'var(--brand-secondary, #38BDF8)',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(56, 189, 248, 0.2)';
                e.currentTarget.style.borderColor = 'var(--brand-secondary, #38BDF8)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(56, 189, 248, 0.1)';
                e.currentTarget.style.borderColor = 'rgba(56, 189, 248, 0.25)';
              }}
            >
              + {tag}
            </button>
          ))}
        </div>
      </div>

      {/* Search Error Display */}
      {searchError && (
        <div
          style={{
            background: 'rgba(239, 68, 68, 0.12)',
            padding: '1rem',
            borderRadius: '12px',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            color: '#ef4444',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span>⚠️ {searchError}</span>
          <button
            type="button"
            onClick={() => setSearchError(null)}
            style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer' }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Search Results Display */}
      {searchResults.length > 0 && (
        <div
          style={{
            background: 'var(--card-bg)',
            padding: '1.25rem',
            borderRadius: '12px',
            border: '1px solid var(--card-border)',
            boxShadow: 'var(--card-shadow)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <h4 style={{ margin: 0, fontSize: '0.95rem', color: 'var(--text-primary)' }}>
              Search Results for <span style={{ color: 'var(--accent-cyan)' }}>"{lastSearchedQuery}"</span> ({searchResults.length} concepts & topics found)
            </h4>
            <button
              type="button"
              onClick={handleClearSearch}
              className="btn btn-secondary btn-sm"
              style={{ fontSize: '0.8rem' }}
            >
              Clear Results
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
            {searchResults.map((item) => (
              <div
                key={`${item.item_type}-${item.id}`}
                onClick={() => handleSelectResult(item)}
                style={{
                  padding: '0.75rem 1rem',
                  borderRadius: '8px',
                  background: 'var(--bg-tertiary)',
                  border: '1px solid var(--card-border)',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = 'var(--accent-cyan)';
                  e.currentTarget.style.background = 'rgba(56, 189, 248, 0.08)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'var(--card-border)';
                  e.currentTarget.style.background = 'var(--bg-tertiary)';
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span
                      style={{
                        fontSize: '0.75rem',
                        fontWeight: 700,
                        textTransform: 'uppercase',
                        padding: '2px 8px',
                        borderRadius: '4px',
                        background:
                          item.item_type === 'concept'
                            ? 'rgba(59, 130, 246, 0.15)'
                            : item.item_type === 'topic'
                            ? 'rgba(245, 158, 11, 0.15)'
                            : 'rgba(128, 87, 245, 0.15)',
                        color:
                          item.item_type === 'concept'
                            ? 'var(--accent-cyan)'
                            : item.item_type === 'topic'
                            ? '#f59e0b'
                            : 'var(--brand-secondary)',
                      }}
                    >
                      {item.item_type}
                    </span>
                    <strong style={{ fontSize: '0.95rem', color: 'var(--text-primary)' }}>{item.title}</strong>
                  </div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)', fontWeight: 500 }}>
                    View in Taxonomy →
                  </span>
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                  <strong>Path:</strong> {item.context_path}
                </div>
                {item.description && (
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                    {item.description}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty Search State */}
      {hasSearched && searchResults.length === 0 && !searching && (
        <div
          style={{
            background: 'var(--card-bg)',
            padding: '1.25rem',
            borderRadius: '12px',
            border: '1px solid var(--card-border)',
            boxShadow: 'var(--card-shadow)',
            textAlign: 'center',
          }}
        >
          <div style={{ fontSize: '1rem', color: 'var(--text-primary)', marginBottom: '0.25rem' }}>
            No concepts found matching "{lastSearchedQuery}"
          </div>
          <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Try searching for terms like <strong>"algorithm"</strong>, <strong>"dijkstra"</strong>, <strong>"neural"</strong>, <strong>"architecture"</strong>, or explore the Academic Disciplines in the catalog below.
          </p>
        </div>
      )}

      {/* Interactive Subject Taxonomy Browser */}
      <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: '1rem', alignItems: 'start' }}>
        {/* Left: Subject List */}
        <div
          style={{
            background: 'var(--card-bg)',
            borderRadius: '12px',
            border: '1px solid var(--card-border)',
            padding: '0.75rem',
            boxShadow: 'var(--card-shadow)',
          }}
        >
          <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '0.9rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Academic Disciplines
          </h4>
          {loading ? (
            <div style={{ padding: '1rem', color: 'var(--text-muted)', fontSize: '0.85rem' }}>Loading subjects...</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {subjects.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => setSelectedSubject(s)}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'flex-start',
                    padding: '0.6rem 0.75rem',
                    borderRadius: '8px',
                    border: 'none',
                    textAlign: 'left',
                    cursor: 'pointer',
                    background: selectedSubject?.id === s.id ? 'var(--nav-item-active-bg, rgba(56, 189, 248, 0.12))' : 'transparent',
                    borderLeft: selectedSubject?.id === s.id ? '3px solid var(--brand-secondary, #38bdf8)' : '3px solid transparent',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <span style={{ fontWeight: 600, fontSize: '0.875rem', color: selectedSubject?.id === s.id ? 'var(--brand-secondary, #38bdf8)' : 'var(--text-primary)' }}>
                    {s.name}
                  </span>
                  <span style={{ fontSize: '0.75rem', color: selectedSubject?.id === s.id ? 'var(--text-secondary)' : 'var(--text-muted)' }}>
                    {s.code} • {s.topics.length} topics
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Right: Topics and Concepts Explorer */}
        <div
          style={{
            background: 'var(--card-bg)',
            borderRadius: '12px',
            border: '1px solid var(--card-border)',
            padding: '1.25rem',
            boxShadow: 'var(--card-shadow)',
          }}
        >
          {selectedSubject ? (
            <div>
              <div style={{ borderBottom: '1px solid var(--card-border)', paddingBottom: '0.75rem', marginBottom: '1rem' }}>
                <h3 style={{ margin: '0 0 0.25rem 0', color: 'var(--text-primary)' }}>{selectedSubject.name}</h3>
                <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{selectedSubject.description}</p>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {selectedSubject.topics.map((t) => (
                  <div
                    key={t.id}
                    style={{
                      border: '1px solid var(--card-border)',
                      borderRadius: '8px',
                      padding: '0.875rem',
                      background: 'var(--bg-tertiary)',
                    }}
                  >
                    <div style={{ fontWeight: 600, fontSize: '0.95rem', color: 'var(--text-primary)' }}>{t.name}</div>
                    {t.description && (
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '2px', marginBottom: '0.5rem' }}>
                        {t.description}
                      </div>
                    )}

                    {/* Concepts Pills */}
                    <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', marginTop: '0.5rem' }}>
                      {t.concepts.map((c) => (
                        <span
                          key={c.id}
                          title={c.description}
                          style={{
                            background: 'var(--card-bg)',
                            border: '1px solid var(--card-border)',
                            borderRadius: '16px',
                            padding: '2px 10px',
                            fontSize: '0.75rem',
                            color: 'var(--text-primary)',
                          }}
                        >
                          ✦ {c.name}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
              Select an academic discipline to view topics and concepts.
            </div>
          )}
        </div>
      </div>
    </>
  )}
</div>
  );
};

