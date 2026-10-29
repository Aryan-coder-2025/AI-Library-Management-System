import React, { useEffect, useState, useCallback } from 'react';
import { apiFetch } from '../services/apiClient';
import type { EmbeddingRefreshResponse, EmbeddingStatusResponse } from '../types/library';

export const LibrarianEmbeddings: React.FC = () => {
  const [status, setStatus] = useState<EmbeddingStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Refresh Trigger State
  const [forceRefresh, setForceRefresh] = useState(false);
  const [refreshLoading, setRefreshLoading] = useState(false);
  const [refreshResult, setRefreshResult] = useState<EmbeddingRefreshResponse | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<EmbeddingStatusResponse>('/api/embeddings/status');
      setStatus(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve embedding status';
      setError(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const handleTriggerRefresh = async () => {
    setRefreshLoading(true);
    setRefreshResult(null);
    setRefreshError(null);

    try {
      const res = await apiFetch<EmbeddingRefreshResponse>(
        `/api/embeddings/refresh?force_refresh=${forceRefresh}`,
        { method: 'POST' }
      );
      setRefreshResult(res);
      await fetchStatus();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to refresh embeddings';
      setRefreshError(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setRefreshLoading(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div className="page-title-group">
          <h1>AI Vector Embeddings Management</h1>
          <p className="page-subtitle">
            Inspect model runtime availability, vector index coverage, and trigger embedding recomputation
          </p>
        </div>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={fetchStatus}
          disabled={loading || refreshLoading}
        >
          {loading ? 'Checking...' : 'Refresh Status'}
        </button>
      </div>

      {error && (
        <div className="alert alert-error">
          <span>{error}</span>
        </div>
      )}

      {/* Model & Runtime Status */}
      {status && (
        <>
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-value">{status.total_books}</div>
              <div className="stat-label">Total Catalogue Books</div>
            </div>

            <div className="stat-card">
              <div className="stat-value" style={{ color: '#059669' }}>
                {status.with_embedding}
              </div>
              <div className="stat-label">Up-to-Date Vectors</div>
            </div>

            <div className="stat-card">
              <div
                className="stat-value"
                style={{ color: status.missing_embedding > 0 ? '#d97706' : 'inherit' }}
              >
                {status.missing_embedding}
              </div>
              <div className="stat-label">Missing Vectors</div>
            </div>

            <div className="stat-card">
              <div
                className="stat-value"
                style={{ color: status.stale_embedding > 0 ? '#dc2626' : 'inherit' }}
              >
                {status.stale_embedding}
              </div>
              <div className="stat-label">Stale Vectors (Outdated)</div>
            </div>
          </div>

          <div className="card" style={{ padding: '1.25rem', marginBottom: '1.5rem' }}>
            <h3 style={{ fontSize: '1.05rem', marginBottom: '0.75rem' }}>
              Vector Architecture & Model Specifications
            </h3>
            <table className="data-table" style={{ border: 'none' }}>
              <tbody>
                <tr>
                  <td style={{ width: '220px', color: 'var(--text-muted)' }}>Embedding Architecture:</td>
                  <td style={{ fontWeight: 600 }}>Sentence Transformers (MiniLM-L6-v2)</td>
                </tr>
                <tr>
                  <td style={{ color: 'var(--text-muted)' }}>Vector Space Dimension:</td>
                  <td>384-dimensional dense float vector</td>
                </tr>
                <tr>
                  <td style={{ color: 'var(--text-muted)' }}>Similarity Metric:</td>
                  <td>Cosine Similarity [-1.0 to 1.0]</td>
                </tr>
                <tr>
                  <td style={{ color: 'var(--text-muted)' }}>Server Model Runtime:</td>
                  <td>
                    {status.model_available ? (
                      <span className="badge badge-success">Online & Ready</span>
                    ) : (
                      <span className="badge badge-warning">
                        Offline / Dependency not loaded (sentence-transformers)
                      </span>
                    )}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Trigger Refresh Controls */}
          <div className="card" style={{ padding: '1.25rem' }}>
            <h3 style={{ fontSize: '1.05rem', marginBottom: '0.35rem' }}>
              Embedding Generation & Index Synchronization
            </h3>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
              Process missing and stale books into dense vectors. Books updated more recently than their stored vector timestamp are automatically identified as stale.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem', maxWidth: '480px' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.875rem', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={forceRefresh}
                  onChange={(e) => setForceRefresh(e.target.checked)}
                />
                Force recompute all books (re-encodes existing valid vectors)
              </label>

              <button
                type="button"
                className="btn btn-primary"
                onClick={handleTriggerRefresh}
                disabled={refreshLoading || !status.model_available}
              >
                {refreshLoading ? 'Generating & Storing Vectors...' : 'Run Embedding Synchronization'}
              </button>

              {!status.model_available && (
                <p style={{ fontSize: '0.8rem', color: 'var(--warning-text)' }}>
                  Note: The server embedding model is currently offline. Background embeddings cannot be recomputed until <code>sentence-transformers</code> is installed on the host.
                </p>
              )}
            </div>

            {refreshError && (
              <div className="alert alert-error" style={{ marginTop: '1.25rem' }}>
                <span>{refreshError}</span>
              </div>
            )}

            {refreshResult && (
              <div className="alert alert-success" style={{ marginTop: '1.25rem' }}>
                <div>
                  <strong>{refreshResult.message}</strong>
                  <div style={{ marginTop: '0.35rem', fontSize: '0.82rem' }}>
                    Processed: {refreshResult.processed} • Failed: {refreshResult.failed} • Candidates: {refreshResult.total_candidates}
                  </div>
                  {refreshResult.errors && refreshResult.errors.length > 0 && (
                    <ul style={{ marginTop: '0.5rem', paddingLeft: '1.25rem' }}>
                      {refreshResult.errors.map((err, idx) => (
                        <li key={idx}>{err}</li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};
