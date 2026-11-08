import React, { useEffect, useState } from 'react';
import { apiFetch } from '../services/apiClient';
import type { BookDetail, BookHold, BookRecommendationResponse, BookRecommendationResult } from '../types/library';
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

  // Hold / Waitlist state
  const [placingHold, setPlacingHold] = useState(false);
  const [holdMessage, setHoldMessage] = useState<string | null>(null);
  const [holdError, setHoldError] = useState<string | null>(null);

  const handlePlaceHold = async () => {
    if (!detail) return;
    setPlacingHold(true);
    setHoldMessage(null);
    setHoldError(null);
    try {
      const res = await apiFetch<BookHold>('/api/holds', {
        method: 'POST',
        body: JSON.stringify({ book_id: detail.id }),
      });
      setHoldMessage(
        `Waitlist hold placed! You are #${res.queue_position || 1} in queue. You will be notified when a copy is returned.`
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to place hold';
      setHoldError(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setPlacingHold(false);
    }
  };

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

                  {detail.available_copies === 0 && !detail.is_archived && (
                    <div
                      style={{
                        marginTop: '0.75rem',
                        padding: '0.85rem',
                        borderRadius: '8px',
                        background: 'var(--bg-glass)',
                        border: '1px solid var(--card-border)',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
                        <div>
                          <strong style={{ fontSize: '0.9rem', color: 'var(--text-primary)' }}>All copies currently on loan</strong>
                          <p style={{ margin: '0.2rem 0 0', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                            Join the waitlist to reserve the next copy returned by another patron.
                          </p>
                        </div>
                        <button
                          type="button"
                          className="btn btn-primary btn-sm"
                          onClick={handlePlaceHold}
                          disabled={placingHold}
                          style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}
                        >
                          <span>🔖</span>
                          <span>{placingHold ? 'Joining Waitlist...' : 'Place Hold'}</span>
                        </button>
                      </div>

                      {holdMessage && (
                        <div className="alert alert-success" style={{ marginTop: '0.65rem', padding: '0.5rem', fontSize: '0.82rem' }}>
                          <span>{holdMessage}</span>
                        </div>
                      )}
                      {holdError && (
                        <div className="alert alert-error" style={{ marginTop: '0.65rem', padding: '0.5rem', fontSize: '0.82rem' }}>
                          <span>{holdError}</span>
                        </div>
                      )}
                    </div>
                  )}
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
                ) : detail.total_copies > 0 ? (
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', backgroundColor: '#f8fafc', padding: '0.75rem', borderRadius: '6px' }}>
                    Inventory Status: <strong>{detail.available_copies} of {detail.total_copies} copies</strong> available on shelf. Sign in with a patron or staff account to inspect physical accession barcodes and copy details.
                  </p>
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
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(215px, 1fr))', gap: '0.85rem' }}>
                    {recs.map((rec) => (
                      <div
                        key={rec.id}
                        style={{
                          border: '1px solid var(--border-subtle)',
                          borderRadius: 'var(--radius-md)',
                          padding: '0.85rem',
                          backgroundColor: 'var(--bg-subtle)',
                          cursor: onSelectBook ? 'pointer' : 'default',
                          display: 'flex',
                          flexDirection: 'column',
                          justifyContent: 'space-between',
                          minHeight: '136px',
                          overflow: 'hidden',
                          boxSizing: 'border-box',
                        }}
                        onClick={() => onSelectBook && onSelectBook(rec.id)}
                      >
                        <div>
                          <div
                            style={{
                              fontWeight: 600,
                              fontSize: '0.875rem',
                              color: 'var(--color-primary)',
                              lineHeight: 1.25,
                              marginBottom: '0.25rem',
                              display: '-webkit-box',
                              WebkitLineClamp: 2,
                              WebkitBoxOrient: 'vertical',
                              overflow: 'hidden',
                              minHeight: '2.5em',
                            }}
                            title={rec.title}
                          >
                            {rec.title}
                          </div>
                          <div
                            style={{
                              fontSize: '0.78rem',
                              color: 'var(--text-muted)',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                              marginBottom: '0.5rem',
                            }}
                            title={rec.author}
                          >
                            {rec.author}
                          </div>
                        </div>

                        <div
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            gap: '0.4rem',
                            flexWrap: 'wrap',
                            marginTop: 'auto',
                            paddingTop: '0.45rem',
                            borderTop: '1px solid var(--border-subtle)',
                          }}
                        >
                          <span
                            className="badge badge-neutral"
                            style={{
                              fontSize: '0.68rem',
                              maxWidth: '110px',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}
                            title={rec.category}
                          >
                            {rec.category}
                          </span>
                          <span
                            className="badge badge-info"
                            style={{
                              fontSize: '0.68rem',
                              whiteSpace: 'nowrap',
                              flexShrink: 0,
                              fontFamily: 'var(--font-mono, monospace)',
                            }}
                          >
                            Cosine: {rec.similarity_score.toFixed(3)}
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
