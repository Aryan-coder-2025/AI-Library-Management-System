import React, { useEffect, useState } from 'react';
import { apiFetch } from '../services/apiClient';
import type { BookDetail, BookRecommendationResponse, BookRecommendationResult } from '../types/library';
import { BookCover } from './BookCover';

interface BookDetailModalProps {
  bookId: number | null;
  onClose: () => void;
  onSelectBook?: (id: number) => void;
}

export const BookDetailModal: React.FC<BookDetailModalProps> = ({
  bookId,
  onClose,
  onSelectBook,
}) => {
  const [detail, setDetail] = useState<BookDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Recommendations state
  const [recs, setRecs] = useState<BookRecommendationResult[]>([]);
  const [recsDisclaimer, setRecsDisclaimer] = useState<string>('');
  const [recsLoading, setRecsLoading] = useState<boolean>(false);
  const [recsError, setRecsError] = useState<string | null>(null);

  useEffect(() => {
    if (!bookId) return;

    let isMounted = true;
    setLoading(true);
    setError(null);
    setRecs([]);
    setRecsError(null);

    // 1. Fetch book details including physical copies
    apiFetch<BookDetail>(`/api/books/${bookId}`)
      .then((data) => {
        if (!isMounted) return;
        setDetail(data);
        setLoading(false);
      })
      .catch((err) => {
        if (!isMounted) return;
        setError(err.message || 'Failed to load book details');
        setLoading(false);
      });

    // 2. Fetch content-based recommendations
    setRecsLoading(true);
    apiFetch<BookRecommendationResponse>(`/api/books/${bookId}/recommendations?limit=5`)
      .then((data) => {
        if (!isMounted) return;
        setRecs(data.recommendations || []);
        setRecsDisclaimer(data.disclaimer || '');
        setRecsLoading(false);
      })
      .catch((err: Error) => {
        if (!isMounted) return;
        // Non-critical: book might have no embeddings or embeddings model offline
        setRecsError(err.message.replace(/^\d+:\s*/, ''));
        setRecsLoading(false);
      });

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);

    return () => {
      isMounted = false;
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [bookId, onClose]);

  if (!bookId) return null;

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div
        className="modal-dialog modal-dialog-large"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h3>Catalogue Record</h3>
          <button
            type="button"
            className="btn-close"
            onClick={onClose}
            aria-label="Close modal"
          >
            ✕
          </button>
        </div>

        <div className="modal-body">
          {loading && (
            <div style={{ textAlign: 'center', padding: '2rem 0', color: 'var(--text-muted)' }}>
              Loading book information...
            </div>
          )}

          {error && (
            <div className="alert alert-error">
              <span>{error}</span>
            </div>
          )}

          {detail && (
            <div>
              <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: '1.5rem', marginBottom: '1.5rem' }}>
                <div style={{ width: '140px', height: '190px' }}>
                  <BookCover title={detail.title} author={detail.author} category={detail.category} />
                </div>
                <div>
                  <h2 style={{ fontSize: '1.35rem', marginBottom: '0.35rem' }}>{detail.title}</h2>
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem', marginBottom: '0.5rem' }}>
                    By <strong>{detail.author}</strong>
                  </p>
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
                    <span className="badge badge-neutral">{detail.category}</span>
                    {detail.isbn && <span className="badge badge-neutral">ISBN: {detail.isbn}</span>}
                    <span className={`badge ${detail.available_copies > 0 ? 'badge-success' : 'badge-danger'}`}>
                      {detail.available_copies > 0
                        ? `${detail.available_copies} of ${detail.total_copies} available`
                        : 'Currently Unavailable'}
                    </span>
                    {detail.is_archived && <span className="badge badge-warning">Archived</span>}
                  </div>
                  <p style={{ fontSize: '0.885rem', lineHeight: 1.5, color: 'var(--text-secondary)' }}>
                    {detail.description || 'No extended summary provided in the catalogue entry.'}
                  </p>
                </div>
              </div>

              {/* Physical Inventory Copies */}
              <div style={{ marginTop: '1.5rem', borderTop: '1px solid var(--border-subtle)', paddingTop: '1.25rem' }}>
                <h4 style={{ fontSize: '1rem', marginBottom: '0.75rem' }}>
                  Physical Inventory Copies ({detail.copies?.length || 0})
                </h4>
                {detail.copies && detail.copies.length > 0 ? (
                  <div className="table-responsive">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Copy ID</th>
                          <th>Barcode</th>
                          <th>Operational Status</th>
                          <th>Circulation State</th>
                          <th>Notes</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detail.copies.map((copy) => (
                          <tr key={copy.id}>
                            <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                              #{copy.id}
                            </td>
                            <td style={{ fontFamily: 'var(--font-mono)' }}>
                              {copy.copy_code}
                            </td>
                            <td>
                              <span
                                className={`badge ${
                                  copy.operational_status === 'available'
                                    ? 'badge-success'
                                    : copy.operational_status === 'maintenance'
                                    ? 'badge-warning'
                                    : 'badge-danger'
                                }`}
                              >
                                {copy.operational_status}
                              </span>
                            </td>
                            <td>
                              {copy.is_borrowed ? (
                                <span className="badge badge-warning">On Loan</span>
                              ) : (
                                <span className="badge badge-success">On Shelf</span>
                              )}
                            </td>
                            <td style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                              {copy.notes || '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                    No physical copies have been catalogued for this title yet.
                  </p>
                )}
              </div>

              {/* Content-Based Recommendations */}
              <div style={{ marginTop: '1.75rem', borderTop: '1px solid var(--border-subtle)', paddingTop: '1.25rem' }}>
                <h4 style={{ fontSize: '1rem', marginBottom: '0.35rem' }}>Related Recommendations</h4>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
                  {recsDisclaimer || 'Similar titles calculated using pretrained vector embeddings.'}
                </p>

                {recsLoading && (
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                    Computing vector similarity...
                  </p>
                )}

                {recsError && (
                  <div className="alert alert-info" style={{ fontSize: '0.8rem', padding: '0.5rem 0.75rem' }}>
                    <span>Notice: {recsError}</span>
                  </div>
                )}

                {!recsLoading && !recsError && recs.length === 0 && (
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                    No related recommendations currently available for this title.
                  </p>
                )}

                {!recsLoading && recs.length > 0 && (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.85rem' }}>
                    {recs.map((rec) => (
                      <div
                        key={rec.id}
                        style={{
                          border: '1px solid var(--border-subtle)',
                          borderRadius: 'var(--radius-md)',
                          padding: '0.75rem',
                          backgroundColor: 'var(--bg-subtle)',
                          cursor: onSelectBook ? 'pointer' : 'default',
                        }}
                        onClick={() => onSelectBook && onSelectBook(rec.id)}
                      >
                        <div style={{ fontWeight: 600, fontSize: '0.875rem', marginBottom: '0.2rem', color: 'var(--color-primary)' }}>
                          {rec.title}
                        </div>
                        <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
                          {rec.author}
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span className="badge badge-neutral" style={{ fontSize: '0.68rem' }}>{rec.category}</span>
                          <span className="badge badge-info" style={{ fontSize: '0.68rem' }}>
                            Cosine Sim: {rec.similarity_score.toFixed(3)}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
