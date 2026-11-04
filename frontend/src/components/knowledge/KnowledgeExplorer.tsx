import React, { useState, useEffect } from 'react';
import type { SubjectTree, KnowledgeSearchResult } from '../../types/knowledge';
import { getSubjectTree, searchKnowledge } from '../../services/knowledgeApi';

export const KnowledgeExplorer: React.FC = () => {
  const [subjects, setSubjects] = useState<SubjectTree[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [searchResults, setSearchResults] = useState<KnowledgeSearchResult[]>([]);
  const [searching, setSearching] = useState<boolean>(false);
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
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }
    setSearching(true);
    try {
      const res = await searchKnowledge(searchQuery);
      setSearchResults(res.results);
    } catch (err) {
      console.error('Knowledge search failed', err);
    } finally {
      setSearching(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Header & Concept Search */}
      <div
        style={{
          background: '#ffffff',
          padding: '1.25rem',
          borderRadius: '8px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
          border: '1px solid #e2e8f0',
        }}
      >
        <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.15rem', color: '#1e293b' }}>
          🧠 Academic Knowledge Representation & Search-Based Navigation
        </h3>
        <p style={{ margin: '0 0 1rem 0', fontSize: '0.875rem', color: '#64748b' }}>
          Explore structured subject taxonomies, topics, and underlying concepts linked to the library collection.
        </p>

        <form onSubmit={handleSearch} style={{ display: 'flex', gap: '0.5rem' }}>
          <input
            type="text"
            placeholder="Search concepts, topics, or disciplines (e.g. 'neural', 'dijkstra', 'algebra')..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              flex: 1,
              padding: '0.5rem 0.75rem',
              borderRadius: '6px',
              border: '1px solid #cbd5e1',
              fontSize: '0.9rem',
            }}
          />
          <button type="submit" className="btn btn-primary" disabled={searching}>
            {searching ? 'Searching...' : '🔍 Search Knowledge'}
          </button>
        </form>
      </div>

      {/* Search Results Display */}
      {searchResults.length > 0 && (
        <div
          style={{
            background: '#ffffff',
            padding: '1rem',
            borderRadius: '8px',
            border: '1px solid #e2e8f0',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
            <h4 style={{ margin: 0, fontSize: '0.95rem', color: '#334155' }}>
              Search Results for "{searchQuery}" ({searchResults.length} concepts found)
            </h4>
            <button
              type="button"
              onClick={() => setSearchResults([])}
              style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: '0.8rem' }}
            >
              Clear Results
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {searchResults.map((item) => (
              <div
                key={`${item.item_type}-${item.id}`}
                style={{
                  padding: '0.75rem',
                  borderRadius: '6px',
                  background: '#f8fafc',
                  border: '1px solid #e2e8f0',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span
                    style={{
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      padding: '2px 6px',
                      borderRadius: '4px',
                      background: item.item_type === 'concept' ? '#dbeafe' : item.item_type === 'topic' ? '#fef3c7' : '#e0e7ff',
                      color: item.item_type === 'concept' ? '#1e40af' : item.item_type === 'topic' ? '#92400e' : '#3730a3',
                    }}
                  >
                    {item.item_type}
                  </span>
                  <strong style={{ fontSize: '0.95rem', color: '#1e293b' }}>{item.title}</strong>
                </div>
                <div style={{ fontSize: '0.8rem', color: '#475569', marginTop: '4px' }}>
                  <strong>Path:</strong> {item.context_path}
                </div>
                {item.description && (
                  <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '2px' }}>
                    {item.description}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Interactive Subject Taxonomy Browser */}
      <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: '1rem', alignItems: 'start' }}>
        {/* Left: Subject List */}
        <div
          style={{
            background: '#ffffff',
            borderRadius: '8px',
            border: '1px solid #e2e8f0',
            padding: '0.75rem',
          }}
        >
          <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '0.9rem', color: '#475569', textTransform: 'uppercase' }}>
            Academic Disciplines
          </h4>
          {loading ? (
            <div style={{ padding: '1rem', color: '#94a3b8', fontSize: '0.85rem' }}>Loading subjects...</div>
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
                    borderRadius: '6px',
                    border: 'none',
                    textAlign: 'left',
                    cursor: 'pointer',
                    background: selectedSubject?.id === s.id ? '#eff6ff' : 'transparent',
                    borderLeft: selectedSubject?.id === s.id ? '3px solid #3b82f6' : '3px solid transparent',
                  }}
                >
                  <span style={{ fontWeight: 600, fontSize: '0.875rem', color: selectedSubject?.id === s.id ? '#1d4ed8' : '#334155' }}>
                    {s.name}
                  </span>
                  <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
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
            background: '#ffffff',
            borderRadius: '8px',
            border: '1px solid #e2e8f0',
            padding: '1.25rem',
          }}
        >
          {selectedSubject ? (
            <div>
              <div style={{ borderBottom: '1px solid #e2e8f0', paddingBottom: '0.75rem', marginBottom: '1rem' }}>
                <h3 style={{ margin: '0 0 0.25rem 0', color: '#1e293b' }}>{selectedSubject.name}</h3>
                <p style={{ margin: 0, fontSize: '0.85rem', color: '#64748b' }}>{selectedSubject.description}</p>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {selectedSubject.topics.map((t) => (
                  <div
                    key={t.id}
                    style={{
                      border: '1px solid #f1f5f9',
                      borderRadius: '6px',
                      padding: '0.875rem',
                      background: '#f8fafc',
                    }}
                  >
                    <div style={{ fontWeight: 600, fontSize: '0.95rem', color: '#0f172a' }}>{t.name}</div>
                    {t.description && (
                      <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '2px', marginBottom: '0.5rem' }}>
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
                            background: '#ffffff',
                            border: '1px solid #cbd5e1',
                            borderRadius: '16px',
                            padding: '2px 10px',
                            fontSize: '0.75rem',
                            color: '#334155',
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
            <div style={{ padding: '2rem', textAlign: 'center', color: '#94a3b8' }}>
              Select an academic discipline to view topics and concepts.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

