import React, { useState } from 'react';
import { apiFetch } from '../services/apiClient';
import type { SemanticBookResult, SemanticSearchResponse } from '../types/library';
import { BookCover } from './BookCover';

interface SemanticSearchProps {
  onSelectBook: (id: number) => void;
  onGoToCatalogue: () => void;
}

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

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanQuery = query.trim();
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

  return (
    <div>
      <div className="page-header">
        <div className="page-title-group">
          <h1>Semantic Book Search</h1>
          <p className="page-subtitle">
            Find books by conceptual meaning, themes, or conversational descriptions
          </p>
        </div>
      </div>

      <div className="ai-callout-box">
        <div className="ai-callout-title">
          <span>AI Vector Space Exploration</span>
        </div>
        <p className="ai-disclaimer">
          Unlike traditional keyword searches, semantic search compares the mathematical meaning of your inquiry against catalogued book embeddings using sentence transformers. You can enter natural language concepts like <em>"how to build autonomous systems"</em> or <em>"modern algebraic geometry with proofs"</em>.
        </p>
      </div>

      <form onSubmit={handleSearch} style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.5rem' }}>
        <input
          type="text"
          className="form-input"
          placeholder="Describe a topic, question, or conceptual subject..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          maxLength={500}
          required
        />
        <button
          type="submit"
          className="btn btn-primary"
          disabled={loading || !query.trim()}
        >
          {loading ? 'Searching Vector Space...' : 'Semantic Search'}
        </button>
        {results !== null && (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => {
              setResults(null);
              setQuery('');
              setError(null);
            }}
          >
            Clear
          </button>
        )}
      </form>

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

      {error && (
        <div className="alert alert-error">
          <span>{error}</span>
        </div>
      )}

      {loading && (
        <div style={{ textAlign: 'center', padding: '3rem 0', color: 'var(--text-muted)' }}>
          Computing query embeddings and ranking nearest neighbours...
        </div>
      )}

      {disclaimer && (
        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '1rem', fontStyle: 'italic' }}>
          Note: {disclaimer} (Scores represent directional cosine similarity in high-dimensional embedding space, not probabilities).
        </div>
      )}

      {results !== null && results.length === 0 && !loading && (
        <div className="empty-state">
          <div className="empty-state-title">No matching conceptual results</div>
          <p className="empty-state-text">
            No active library books met the similarity threshold for your query. Try rephrasing your conceptual description or use the standard catalogue.
          </p>
          <button type="button" className="btn btn-secondary" onClick={onGoToCatalogue}>
            Browse Standard Catalogue
          </button>
        </div>
      )}

      {results && results.length > 0 && (
        <div className="book-grid">
          {results.map((book) => (
            <div
              key={book.id}
              className="book-card"
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
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.35rem' }}>
                  <h3 className="book-card-title">{book.title}</h3>
                  <span className="badge badge-info" style={{ fontSize: '0.7rem' }}>
                    Cosine Sim: {book.similarity_score.toFixed(3)}
                  </span>
                </div>
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
          ))}
        </div>
      )}
    </div>
  );
};
