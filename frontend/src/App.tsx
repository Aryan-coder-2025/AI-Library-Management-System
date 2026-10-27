import { useEffect, useState } from 'react';
import { apiFetch } from './services/apiClient';

interface HealthData {
  status: string;
  project_name: string;
  environment: string;
  database: string;
}

interface UserProfile {
  id: number;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

interface SemanticBookResult {
  id: number;
  title: string;
  author: string;
  isbn: string;
  category: string;
  description: string | null;
  total_copies: number;
  available_copies: number;
  similarity_score: number;
}

interface SemanticSearchResponse {
  items: SemanticBookResult[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  query: string;
  disclaimer: string;
}

interface BookRecommendationResult {
  id: number;
  title: string;
  author: string;
  isbn: string;
  category: string;
  description: string | null;
  similarity_score: number;
}

interface BookRecommendationResponse {
  source_book_id: number;
  source_book_title: string;
  recommendations: BookRecommendationResult[];
  total: number;
  disclaimer: string;
}

interface EmbeddingStatusResponse {
  total_books: number;
  with_embedding: number;
  missing_embedding: number;
  stale_embedding: number;
  model_name: string;
  model_available: boolean;
  is_processing: boolean;
}

interface EmbeddingRefreshResponse {
  status: string;
  total_candidates: number;
  processed: number;
  failed: number;
  stale: number;
  missing: number;
  message: string;
  errors?: string[];
}

export function App() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [healthLoading, setHealthLoading] = useState<boolean>(true);

  // Authentication State
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [authLoading, setAuthLoading] = useState<boolean>(true);
  const [emailInput, setEmailInput] = useState<string>('');
  const [passwordInput, setPasswordInput] = useState<string>('');
  const [loginError, setLoginError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  // Semantic Search State
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [searchResults, setSearchResults] = useState<SemanticBookResult[] | null>(null);
  const [searchTotal, setSearchTotal] = useState<number>(0);
  const [searchDisclaimer, setSearchDisclaimer] = useState<string>('');
  const [searchLoading, setSearchLoading] = useState<boolean>(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [isModelUnavailable, setIsModelUnavailable] = useState<boolean>(false);

  // Recommendations State
  const [recsLoading, setRecsLoading] = useState<boolean>(false);
  const [selectedBook, setSelectedBook] = useState<SemanticBookResult | null>(null);
  const [recsResponse, setRecsResponse] = useState<BookRecommendationResponse | null>(null);
  const [recsError, setRecsError] = useState<string | null>(null);

  // Librarian Embedding Management State
  const [embStatus, setEmbStatus] = useState<EmbeddingStatusResponse | null>(null);
  const [embLoading, setEmbLoading] = useState<boolean>(false);
  const [embRefreshLoading, setEmbRefreshLoading] = useState<boolean>(false);
  const [forceRefresh, setForceRefresh] = useState<boolean>(false);
  const [refreshMessage, setRefreshMessage] = useState<string | null>(null);
  const [refreshErrors, setRefreshErrors] = useState<string[]>([]);

  useEffect(() => {
    // 1. Fetch system health
    apiFetch<HealthData>('/api/health')
      .then((data) => {
        setHealth(data);
        setHealthLoading(false);
      })
      .catch((err) => {
        setHealthError(err.message || 'Failed to connect to backend service');
        setHealthLoading(false);
      });

    // 2. Check existing session
    apiFetch<UserProfile>('/api/auth/me')
      .then((user) => {
        setCurrentUser(user);
        setAuthLoading(false);
      })
      .catch(() => {
        setCurrentUser(null);
        setAuthLoading(false);
      });
  }, []);

  // Fetch librarian embedding status when authenticated as librarian
  useEffect(() => {
    if (currentUser?.role === 'librarian') {
      fetchEmbeddingStatus();
    }
  }, [currentUser]);

  const fetchEmbeddingStatus = async () => {
    setEmbLoading(true);
    try {
      const data = await apiFetch<EmbeddingStatusResponse>('/api/embeddings/status');
      setEmbStatus(data);
    } catch {
      // Non-critical background status fetch
    } finally {
      setEmbLoading(false);
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError(null);
    setIsSubmitting(true);

    try {
      const user = await apiFetch<UserProfile>('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({
          email: emailInput,
          password: passwordInput,
        }),
      });
      setCurrentUser(user);
      setPasswordInput('');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Login failed';
      setLoginError(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleLogout = async () => {
    try {
      await apiFetch('/api/auth/logout', { method: 'POST' });
    } catch {
      // Ignore logout errors
    } finally {
      setCurrentUser(null);
      setEmailInput('');
      setPasswordInput('');
      setLoginError(null);
      setSearchResults(null);
      setSelectedBook(null);
      setRecsResponse(null);
      setEmbStatus(null);
    }
  };

  const handleSemanticSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    const query = searchQuery.trim();
    if (!query) return;

    setSearchLoading(true);
    setSearchError(null);
    setIsModelUnavailable(false);

    try {
      const res = await apiFetch<SemanticSearchResponse>(
        `/api/search/semantic?q=${encodeURIComponent(query)}&page=1&page_size=10`
      );
      setSearchResults(res.items);
      setSearchTotal(res.total);
      setSearchDisclaimer(res.disclaimer);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Semantic search failed';
      if (msg.includes('503')) {
        setIsModelUnavailable(true);
      } else {
        setSearchError(msg.replace(/^\d+:\s*/, ''));
      }
      setSearchResults(null);
    } finally {
      setSearchLoading(false);
    }
  };

  const handleGetRecommendations = async (book: SemanticBookResult) => {
    setSelectedBook(book);
    setRecsLoading(true);
    setRecsError(null);
    setRecsResponse(null);

    try {
      const res = await apiFetch<BookRecommendationResponse>(
        `/api/books/${book.id}/recommendations?limit=5`
      );
      setRecsResponse(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve recommendations';
      setRecsError(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setRecsLoading(false);
    }
  };

  const handleRefreshEmbeddings = async () => {
    setEmbRefreshLoading(true);
    setRefreshMessage(null);
    setRefreshErrors([]);

    try {
      const res = await apiFetch<EmbeddingRefreshResponse>(
        `/api/embeddings/refresh?force_refresh=${forceRefresh}`,
        { method: 'POST' }
      );
      setRefreshMessage(res.message);
      if (res.errors && res.errors.length > 0) {
        setRefreshErrors(res.errors);
      }
      await fetchEmbeddingStatus();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to refresh embeddings';
      setRefreshMessage(`Error: ${msg.replace(/^\d+:\s*/, '')}`);
    } finally {
      setEmbRefreshLoading(false);
    }
  };

  return (
    <div className="app-container">
      <header className="header-banner">
        <h1>AI Library Management System</h1>
        <p>Stage 5: Semantic Book Search & Content-Based Recommendations</p>
      </header>

      <div className="card-grid">
        {/* Card 1: Authentication / Session */}
        <div className="status-card">
          <h3>User Authentication & Session</h3>
          {authLoading ? (
            <span className="status-badge loading">Checking session...</span>
          ) : currentUser ? (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <span className={`role-badge ${currentUser.role}`}>{currentUser.role}</span>
                <button type="button" className="btn-secondary" onClick={handleLogout}>
                  Log Out
                </button>
              </div>
              <table className="meta-table">
                <tbody>
                  <tr>
                    <td>Name:</td>
                    <td>{currentUser.full_name}</td>
                  </tr>
                  <tr>
                    <td>Email:</td>
                    <td>{currentUser.email}</td>
                  </tr>
                  <tr>
                    <td>Status:</td>
                    <td>{currentUser.is_active ? 'Active' : 'Inactive'}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          ) : (
            <form className="auth-form" onSubmit={handleLogin}>
              <div className="form-group">
                <label htmlFor="email">Email Address</label>
                <input
                  id="email"
                  type="email"
                  className="form-input"
                  placeholder="student@university.edu"
                  value={emailInput}
                  onChange={(e) => setEmailInput(e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="password">Password</label>
                <input
                  id="password"
                  type="password"
                  className="form-input"
                  placeholder="••••••••"
                  value={passwordInput}
                  onChange={(e) => setPasswordInput(e.target.value)}
                  required
                />
              </div>
              {loginError && <div className="alert-error">{loginError}</div>}
              <button type="submit" className="btn-primary" disabled={isSubmitting}>
                {isSubmitting ? 'Authenticating...' : 'Sign In'}
              </button>
            </form>
          )}
        </div>

        {/* Card 2: Backend & Database Health */}
        <div className="status-card">
          <h3>Backend & Database Health</h3>
          {healthLoading && <span className="status-badge loading">Connecting...</span>}
          {healthError && <span className="status-badge loading" style={{ color: '#ef4444' }}>Offline ({healthError})</span>}
          {health && (
            <>
              <span className="status-badge healthy">{health.status}</span>
              <table className="meta-table">
                <tbody>
                  <tr>
                    <td>Database Status:</td>
                    <td>{health.database}</td>
                  </tr>
                  <tr>
                    <td>Environment:</td>
                    <td>{health.environment}</td>
                  </tr>
                  <tr>
                    <td>Project:</td>
                    <td>{health.project_name}</td>
                  </tr>
                </tbody>
              </table>
            </>
          )}
        </div>

        {/* Card 3: Security & RBAC Guards */}
        <div className="status-card">
          <h3>Security & RBAC Guards</h3>
          <table className="meta-table">
            <tbody>
              <tr>
                <td>Auth Mechanism:</td>
                <td>HttpOnly JWT Cookie (8h)</td>
              </tr>
              <tr>
                <td>CSRF Protection:</td>
                <td>Double Submit Cookie</td>
              </tr>
              <tr>
                <td>Roles Supported:</td>
                <td>Student, Librarian</td>
              </tr>
              <tr>
                <td>Model:</td>
                <td>sentence-transformers/all-MiniLM-L6-v2</td>
              </tr>
              <tr>
                <td>Vector Metric:</td>
                <td>Cosine Similarity [-1.0, 1.0]</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Card 4: Semantic Book Search (Full Width) */}
        {currentUser && (
          <div className="full-width-card">
            <div className="section-header">
              <h2>Semantic Book Search</h2>
              <span className="role-badge student">AI Vector Space</span>
            </div>

            <form className="search-form" onSubmit={handleSemanticSearch}>
              <div className="search-input-wrapper">
                <input
                  id="semantic-query-input"
                  type="text"
                  className="form-input"
                  placeholder="Search book concepts, themes, authors, descriptions (e.g. 'deep learning and vision')..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  maxLength={500}
                  required
                />
              </div>
              <button
                type="submit"
                className="btn-action"
                disabled={searchLoading || !searchQuery.trim()}
              >
                {searchLoading ? 'Searching...' : 'Semantic Search'}
              </button>
              {searchResults !== null && (
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => {
                    setSearchResults(null);
                    setSearchQuery('');
                    setSelectedBook(null);
                    setRecsResponse(null);
                  }}
                >
                  Clear
                </button>
              )}
            </form>

            {/* Model Unavailable Banner */}
            {isModelUnavailable && (
              <div className="banner-warning">
                <strong>Sentence Transformer Model Unavailable:</strong> The pretrained model{' '}
                <code>sentence-transformers/all-MiniLM-L6-v2</code> is not loaded on the server.
                Keyword catalogue search remains fully operational.
              </div>
            )}

            {/* Error Message */}
            {searchError && <div className="alert-error">{searchError}</div>}

            {/* Disclaimer Box */}
            {searchDisclaimer && (
              <div className="disclaimer-box">
                <strong>Scientific Disclaimer:</strong> {searchDisclaimer}
              </div>
            )}

            {/* Empty Results State */}
            {searchResults !== null && searchResults.length === 0 && !searchLoading && (
              <div className="empty-state">
                No active catalogue books matched your query with current embeddings.
              </div>
            )}

            {/* Search Results List */}
            {searchResults !== null && searchResults.length > 0 && (
              <div>
                <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
                  Found {searchTotal} matching book{searchTotal === 1 ? '' : 's'} ranked by cosine similarity:
                </p>
                <div className="book-results-grid">
                  {searchResults.map((book) => (
                    <div key={book.id} className="book-result-card">
                      <div className="book-card-header">
                        <span className="book-card-title">{book.title}</span>
                        <div className="badge-group">
                          <span className="category-tag">{book.category}</span>
                          <span className="score-badge">
                            Cosine Sim: {book.similarity_score.toFixed(4)}
                          </span>
                        </div>
                      </div>

                      <div className="book-card-meta">
                        <span><strong>Author:</strong> {book.author}</span>
                        <span><strong>ISBN:</strong> {book.isbn}</span>
                      </div>

                      {book.description && (
                        <p className="book-card-desc">{book.description}</p>
                      )}

                      <div className="book-card-footer">
                        <span className="copies-info">
                          Available: {book.available_copies} / {book.total_copies} copies
                        </span>
                        <button
                          type="button"
                          className="btn-recs"
                          onClick={() => handleGetRecommendations(book)}
                        >
                          Find Similar Books
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recommendations Panel */}
            {selectedBook && (
              <div className="recommendations-panel">
                <div className="recs-header">
                  <h4>Content-Based Recommendations for "{selectedBook.title}"</h4>
                  <button
                    type="button"
                    className="btn-close"
                    onClick={() => {
                      setSelectedBook(null);
                      setRecsResponse(null);
                      setRecsError(null);
                    }}
                    title="Close recommendations"
                  >
                    ✕
                  </button>
                </div>

                {recsLoading && (
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                    Computing vector similarity across catalogue...
                  </p>
                )}

                {recsError && <div className="alert-error">{recsError}</div>}

                {recsResponse && (
                  <div>
                    <div className="disclaimer-box">
                      <strong>Methodology Note:</strong> {recsResponse.disclaimer}
                    </div>

                    {recsResponse.recommendations.length === 0 ? (
                      <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                        No similar books found in the catalogue.
                      </p>
                    ) : (
                      <div className="book-results-grid">
                        {recsResponse.recommendations.map((rec) => (
                          <div key={rec.id} className="book-result-card" style={{ background: 'rgba(15, 23, 42, 0.7)' }}>
                            <div className="book-card-header">
                              <span className="book-card-title">{rec.title}</span>
                              <div className="badge-group">
                                <span className="category-tag">{rec.category}</span>
                                <span className="score-badge">
                                  Cosine Sim: {rec.similarity_score.toFixed(4)}
                                </span>
                              </div>
                            </div>
                            <div className="book-card-meta">
                              <span><strong>Author:</strong> {rec.author}</span>
                              <span><strong>ISBN:</strong> {rec.isbn}</span>
                            </div>
                            {rec.description && (
                              <p className="book-card-desc">{rec.description}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Librarian Embedding Operations */}
            {currentUser.role === 'librarian' && (
              <div className="librarian-panel">
                <div className="recs-header">
                  <h4>Librarian Embedding Controls & Model Metrics</h4>
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={fetchEmbeddingStatus}
                    disabled={embLoading}
                    style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem' }}
                  >
                    {embLoading ? 'Refreshing...' : 'Refresh Status'}
                  </button>
                </div>

                {embStatus && (
                  <div className="status-grid">
                    <div className="status-stat">
                      <div className="stat-value">{embStatus.total_books}</div>
                      <div className="stat-label">Total Books</div>
                    </div>
                    <div className="status-stat">
                      <div className="stat-value" style={{ color: '#34d399' }}>{embStatus.with_embedding}</div>
                      <div className="stat-label">Embedded</div>
                    </div>
                    <div className="status-stat">
                      <div className="status-stat" style={{ padding: 0 }}>
                        <div className="stat-value" style={{ color: embStatus.missing_embedding > 0 ? '#fbbf24' : 'inherit' }}>
                          {embStatus.missing_embedding}
                        </div>
                        <div className="stat-label">Missing</div>
                      </div>
                    </div>
                    <div className="status-stat">
                      <div className="stat-value" style={{ color: embStatus.stale_embedding > 0 ? '#f87171' : 'inherit' }}>
                        {embStatus.stale_embedding}
                      </div>
                      <div className="stat-label">Stale</div>
                    </div>
                    <div className="status-stat">
                      <div className="stat-value" style={{ fontSize: '0.9rem', color: embStatus.model_available ? '#34d399' : '#f87171' }}>
                        {embStatus.model_available ? 'Ready' : 'Unavailable'}
                      </div>
                      <div className="stat-label">Model Runtime</div>
                    </div>
                  </div>
                )}

                <div className="refresh-action-row">
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem', color: 'var(--text-muted)', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={forceRefresh}
                      onChange={(e) => setForceRefresh(e.target.checked)}
                    />
                    Force recompute all embeddings
                  </label>
                  <button
                    type="button"
                    className="btn-action"
                    onClick={handleRefreshEmbeddings}
                    disabled={embRefreshLoading || (embStatus !== null && !embStatus.model_available)}
                  >
                    {embRefreshLoading ? 'Generating Embeddings...' : 'Generate / Refresh Embeddings'}
                  </button>
                </div>

                {refreshMessage && (
                  <p style={{ marginTop: '0.75rem', fontSize: '0.85rem', color: refreshMessage.startsWith('Error') ? '#fca5a5' : '#34d399' }}>
                    {refreshMessage}
                  </p>
                )}

                {refreshErrors.length > 0 && (
                  <div className="alert-error" style={{ marginTop: '0.5rem' }}>
                    <strong>Failures ({refreshErrors.length}):</strong>
                    <ul style={{ paddingLeft: '1.25rem', marginTop: '0.25rem' }}>
                      {refreshErrors.map((err, i) => (
                        <li key={i}>{err}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
