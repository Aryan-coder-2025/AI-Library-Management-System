import React, { useState } from 'react';
import { apiFetch } from '../services/apiClient';
import type { SemanticBookResult, SemanticSearchResponse } from '../types/library';
import { BookCover } from './BookCover';

interface SemanticSearchProps {
  onSelectBook: (id: number) => void;
  onGoToCatalogue: () => void;
}

const DISCOVERY_PROMPTS = [
  { label: 'Distributed Consensus & Raft', icon: '⚡' },
  { label: 'Neural Transformers & Attention', icon: '🧠' },
  { label: 'Zero-Knowledge Cryptography', icon: '🔐' },
  { label: 'Quantum Computing & Algorithms', icon: '⚛️' },
  { label: 'Autonomous Multi-Agent Systems', icon: '🤖' },
  { label: 'Database Storage Engines & LSM-Trees', icon: '💾' },
];

export const SemanticSearch: React.FC<SemanticSearchProps> = ({
  onSelectBook,
  onGoToCatalogue,
}) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SemanticBookResult[] | null>(null);
  const [disclaimer, setDisclaimer] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [modelUnavailable, setModelUnavailable] = useState(false);

  const executeSearch = async (searchQuery: string) => {
    const cleanQuery = searchQuery.trim();
    if (!cleanQuery) return;

    setLoading(true);
    setError(null);
    setModelUnavailable(false);

    try {
      const data = await apiFetch<SemanticSearchResponse>(
        `/api/search/semantic?q=${encodeURIComponent(cleanQuery)}&page=1&page_size=12`
      );
      setResults(data.items);
      setDisclaimer(data.disclaimer);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Semantic search failed';
      if (msg.includes('503')) {
        setModelUnavailable(true);
      } else {
        setError(msg.replace(/^\d+:\s*/, ''));
      }
      setResults(null);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    executeSearch(query);
  };

  const handleChipClick = (prompt: string) => {
    setQuery(prompt);
    executeSearch(prompt);
  };

  return (
    <div className="semantic-search-container">
      {/* Futuristic Header */}
      <div className="page-header">
        <div className="page-title-group">
          <div className="hero-tag-pill" style={{ marginBottom: '0.5rem' }}>
            <span className="pulsing-neon-dot" />
            <span>NEURAL VECTOR ENGINE • 384-DIMENSIONAL EMBEDDINGS</span>
          </div>
          <h1>Semantic Vector Search</h1>
          <p className="page-subtitle">
            Query Athenaeum's academic collection by conceptual meaning, mathematical intuition, or research inquiries.
          </p>
        </div>
      </div>

      {/* Cyber AI Vector Space Explainer & Prompt Discovery */}
      <div className="ai-callout-box">
        <div className="ai-callout-title">
          <span>🧠 Latent Vector Space Exploration</span>
        </div>
        <p className="ai-disclaimer" style={{ marginBottom: '0.85rem' }}>
          Unlike keyword matching, semantic search translates your natural language thoughts into 384-dimensional dense vectors using <code>all-MiniLM-L6-v2</code> and calculates cosine proximity against monograph embeddings.
        </p>

        {/* Discovery Chips */}
        <div className="discovery-chips-label">
          <span>⚡ QUICK EXPLORATION CONCEPTS:</span>
        </div>
        <div className="discovery-chips-container">
          {DISCOVERY_PROMPTS.map((item) => (
            <button
              key={item.label}
              type="button"
              className="discovery-chip-btn"
              onClick={() => handleChipClick(item.label)}
              title={`Explore: ${item.label}`}
            >
              <span className="chip-icon">{item.icon}</span>
              <span>{item.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Futuristic Search Form Bar */}
      <form onSubmit={handleSearch} className="semantic-search-form">
        <div className="semantic-input-wrap">
          <span className="semantic-input-icon">🔍</span>
          <input
            type="text"
            className="form-input semantic-search-input"
            placeholder="Describe a topic, research question, or conceptual subject (e.g. how consensus works in distributed networks)..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            maxLength={500}
            required
          />
          {query && (
            <button
              type="button"
              className="semantic-clear-btn"
              onClick={() => {
                setQuery('');
                setResults(null);
                setError(null);
              }}
              title="Clear search query"
            >
              ✕
            </button>
          )}
        </div>
        <button
          type="submit"
          className="btn btn-primary semantic-submit-btn"
          disabled={loading || !query.trim()}
        >
          {loading ? (
            <>
              <span className="pulsing-neon-dot" />
              <span>Projecting Vectors...</span>
            </>
          ) : (
            <>
              <span>⚡ Vector Search</span>
            </>
          )}
        </button>
      </form>

      {/* 503 Model Unavailable Fallback */}
      {modelUnavailable && (
        <div className="alert alert-warning">
          <div>
            <strong>Pretrained Model Offline (HTTP 503):</strong> The embedding runtime is currently not active in this server environment.
            <div style={{ marginTop: '0.5rem' }}>
              Standard keyword catalogue search remains fully operational.
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={onGoToCatalogue}
                style={{ marginLeft: '0.75rem' }}
              >
                Go to Standard Catalogue
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="alert alert-error">
          <span>{error}</span>
        </div>
      )}

      {/* Active Loading State */}
      {loading && (
        <div className="semantic-loading-card">
          <div className="semantic-radar-pulse" />
          <div className="semantic-loading-text">
            <span>Projecting query into 384-dimensional manifold...</span>
            <span className="semantic-loading-subtext">Calculating angular cosine similarity across indexed monographs</span>
          </div>
        </div>
      )}

      {/* Cosine Sim Disclaimer */}
      {disclaimer && !loading && (
        <div className="semantic-disclaimer-pill">
          <span>ℹ️ {disclaimer} (Scores represent directional cosine similarity in high-dimensional embedding space, not probabilities).</span>
        </div>
      )}

      {/* Zero Results State */}
      {results !== null && results.length === 0 && !loading && (
        <div className="empty-state">
          <div className="empty-state-title">No matching conceptual monographs</div>
          <p className="empty-state-text">
            No active library books met the similarity threshold for your query. Try exploring one of the suggested concept chips above or check the catalogue.
          </p>
          <button type="button" className="btn btn-secondary" onClick={onGoToCatalogue}>
            Browse Standard Catalogue
          </button>
        </div>
      )}

      {/* Initial Guide (Before search) */}
      {results === null && !loading && (
        <div className="semantic-guide-grid">
          <div className="semantic-guide-card">
            <div className="guide-card-icon">⚡</div>
            <div className="guide-card-title">Dense Neural Embeddings</div>
            <p className="guide-card-desc">
              Text sentences are encoded into 384 real-valued floating vectors capturing deep academic semantics beyond literal strings.
            </p>
          </div>
          <div className="semantic-guide-card">
            <div className="guide-card-icon">📐</div>
            <div className="guide-card-title">Cosine Similarity Ranking</div>
            <p className="guide-card-desc">
              Measures normalized dot products in latent space. A score near 1.0 indicates intense conceptual alignment.
            </p>
          </div>
          <div className="semantic-guide-card">
            <div className="guide-card-icon">🏛️</div>
            <div className="guide-card-title">Verified University Corpus</div>
            <p className="guide-card-desc">
              Instantly surfaces relevant monographs across Computing, Information Science, Cryptography, and Advanced Mathematics.
            </p>
          </div>
        </div>
      )}

      {/* Vector Results Grid */}
      {results && results.length > 0 && !loading && (
        <div className="book-grid">
          {results.map((book) => {
            const similarityPercent = Math.min(100, Math.max(0, Math.round(book.similarity_score * 100)));
            return (
              <div
                key={book.id}
                className="book-card semantic-result-card"
                onClick={() => onSelectBook(book.id)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onSelectBook(book.id);
                  }
                }}
                aria-label={`View details for ${book.title}`}
              >
                <BookCover title={book.title} author={book.author} category={book.category} />
                <div className="book-card-body">
                  {/* Top Vector Match Indicator */}
                  <div className="vector-match-header">
                    <span className="vector-similarity-badge">
                      ⚡ {similarityPercent}% Vector Match
                    </span>
                    <span className="vector-raw-score">
                      cos: {book.similarity_score.toFixed(3)}
                    </span>
                  </div>

                  {/* Similarity Progress Bar */}
                  <div className="vector-meter-track">
                    <div
                      className="vector-meter-bar"
                      style={{ width: `${similarityPercent}%` }}
                    />
                  </div>

                  <h3 className="book-card-title">{book.title}</h3>
                  <div className="book-card-author">{book.author}</div>
                  {book.description && (
                    <p className="book-card-desc">{book.description}</p>
                  )}
                  <div className="book-card-footer">
                    <span className="badge badge-neutral" style={{ fontSize: '0.7rem' }}>
                      {book.category}
                    </span>
                    <span
                      className={`availability-indicator ${
                        book.available_copies > 0 ? 'in-stock' : 'out-of-stock'
                      }`}
                    >
                      {book.available_copies > 0
                        ? `${book.available_copies} available`
                        : 'Checked out'}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
