import React, { useEffect, useState } from 'react';
import { apiFetch } from '../services/apiClient';
import type { BookDetail, BookHold, BookRecommendationResponse, BookRecommendationResult } from '../types/library';
import { BookCover } from './BookCover';
import { QRCollectionModal } from './QRCollectionModal';
import { BookShelfLocationModal } from './BookShelfLocationModal';

interface BookDetailModalProps {
  bookId: number | null;
  onClose: () => void;
  onSelectBook?: (id: number) => void;
  onNavigateToLoans?: () => void;
}

export const BookDetailModal: React.FC<BookDetailModalProps> = ({
  bookId,
  onClose,
  onSelectBook,
  onNavigateToLoans,
}) => {
  const [detail, setDetail] = useState<BookDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Recommendations state
  const [recs, setRecs] = useState<BookRecommendationResult[]>([]);
  const [recsDisclaimer, setRecsDisclaimer] = useState<string>('');
  const [recsLoading, setRecsLoading] = useState<boolean>(false);
  const [recsError, setRecsError] = useState<string | null>(null);

  // Hold / Online Booking state
  const [showShelfLocationModal, setShowShelfLocationModal] = useState<boolean>(false);
  const [placingHold, setPlacingHold] = useState(false);
  const [createdHold, setCreatedHold] = useState<BookHold | null>(null);
  const [showQRPassModal, setShowQRPassModal] = useState<boolean>(false);
  const [tokenCopied, setTokenCopied] = useState<boolean>(false);
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
      setCreatedHold(res);
      if (res.status === 'ready_for_pickup') {
        const deadlineStr = res.pickup_expires_at
          ? new Date(res.pickup_expires_at).toLocaleDateString()
          : '7 days';
        setHoldMessage(
          `🎉 Online Reservation Confirmed! Copy ${res.copy_code ? `(#${res.copy_code})` : ''} is locked and reserved for you at the front desk. Collection pass valid until ${deadlineStr}.`
        );
      } else {
        setHoldMessage(
          `Waitlist hold placed! You are #${res.queue_position || 1} in queue. You will be notified automatically when a copy is returned.`
        );
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to book loan reservation';
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
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.75rem', alignItems: 'center' }}>
                    <span className="badge badge-neutral">{detail.category}</span>
                    {detail.isbn && <span className="badge badge-neutral">ISBN: {detail.isbn}</span>}
                    <span className={`badge ${detail.available_copies > 0 ? 'badge-success' : 'badge-danger'}`}>
                      {detail.available_copies > 0
                        ? `${detail.available_copies} of ${detail.total_copies} available`
                        : 'Currently Unavailable'}
                    </span>
                    {detail.is_archived && <span className="badge badge-warning">Archived</span>}
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => setShowShelfLocationModal(true)}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.35rem',
                        padding: '0.2rem 0.65rem',
                        fontSize: '0.78rem',
                        borderRadius: '6px',
                        background: 'rgba(99, 102, 241, 0.15)',
                        border: '1px solid rgba(99, 102, 241, 0.4)',
                        color: '#a5b4fc',
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                      title="Pinpoint exact bookcase, tier, and book number on floor plan"
                    >
                      <span>📍</span> Locate on Shelf
                    </button>
                  </div>
                  <p style={{ fontSize: '0.885rem', lineHeight: 1.5, color: 'var(--text-secondary)' }}>
                    {detail.description || 'No extended summary provided in the catalogue entry.'}
                  </p>

                  {!detail.is_archived && detail.user_has_active_loan ? (
                    <div
                      style={{
                        marginTop: '0.85rem',
                        padding: '1rem 1.15rem',
                        borderRadius: '10px',
                        background: 'rgba(37, 99, 235, 0.08)',
                        border: '1px solid rgba(56, 189, 248, 0.35)',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                            <span style={{ fontSize: '1.25rem' }}>📖</span>
                            <strong style={{ fontSize: '0.95rem', color: 'var(--text-primary)' }}>
                              Active Loan in Progress
                            </strong>
                            <span className="badge badge-success" style={{ fontSize: '0.7rem' }}>
                              Currently Borrowed by You
                            </span>
                          </div>
                          <p style={{ margin: '0.35rem 0 0', fontSize: '0.825rem', color: 'var(--text-secondary)', maxWidth: '480px' }}>
                            You currently have an active physical copy of this monograph checked out to your patron account{detail.user_active_loan_due_date ? ` (Due date: ${new Date(detail.user_active_loan_due_date).toLocaleDateString()})` : ''}.
                            Under library circulation rules, duplicate loans of the same monograph are restricted. Please return your current copy at the circulation desk before borrowing again.
                          </p>
                        </div>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => {
                            if (onNavigateToLoans) {
                              onNavigateToLoans();
                            } else {
                              onClose();
                              (document.querySelector('[data-tour="nav-loans"]') as HTMLButtonElement)?.click();
                            }
                          }}
                          style={{ whiteSpace: 'nowrap' }}
                        >
                          View in My Loans →
                        </button>
                      </div>
                    </div>
                  ) : !detail.is_archived && detail.user_has_active_hold && !createdHold ? (
                    <div
                      style={{
                        marginTop: '0.85rem',
                        padding: '1rem 1.15rem',
                        borderRadius: '10px',
                        background: detail.user_active_hold_status === 'ready_for_pickup' ? 'rgba(16, 185, 129, 0.08)' : 'rgba(234, 179, 8, 0.08)',
                        border: `1px solid ${detail.user_active_hold_status === 'ready_for_pickup' ? 'rgba(16, 185, 129, 0.35)' : 'rgba(234, 179, 8, 0.35)'}`,
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                            <span style={{ fontSize: '1.25rem' }}>🔖</span>
                            <strong style={{ fontSize: '0.95rem', color: 'var(--text-primary)' }}>
                              {detail.user_active_hold_status === 'ready_for_pickup'
                                ? 'Monograph Reserved & Ready for Collection'
                                : 'You are on the Waitlist for this Monograph'}
                            </strong>
                            <span
                              className={`badge ${detail.user_active_hold_status === 'ready_for_pickup' ? 'badge-success' : 'badge-warning'}`}
                              style={{ fontSize: '0.7rem' }}
                            >
                              {detail.user_active_hold_status === 'ready_for_pickup' ? 'Awaiting Desk Collection' : 'In Waitlist Queue'}
                            </span>
                          </div>
                          <p style={{ margin: '0.35rem 0 0', fontSize: '0.825rem', color: 'var(--text-secondary)', maxWidth: '480px' }}>
                            {detail.user_active_hold_status === 'ready_for_pickup'
                              ? 'An available physical copy is held for you at the front desk. Present your collection token or QR code to the librarian to approve your loan.'
                              : 'You already have an active waitlist reservation for this monograph. You will receive an in-app notification the moment a copy is returned.'}
                          </p>
                        </div>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => {
                            if (onNavigateToLoans) {
                              onNavigateToLoans();
                            } else {
                              onClose();
                              (document.querySelector('[data-tour="nav-loans"]') as HTMLButtonElement)?.click();
                            }
                          }}
                          style={{ whiteSpace: 'nowrap' }}
                        >
                          View in My Holds →
                        </button>
                      </div>
                    </div>
                  ) : !detail.is_archived && (
                    <div
                      style={{
                        marginTop: '0.85rem',
                        padding: '1rem 1.15rem',
                        borderRadius: '10px',
                        background: detail.available_copies > 0 ? 'rgba(37, 99, 235, 0.08)' : 'rgba(234, 179, 8, 0.08)',
                        border: `1px solid ${detail.available_copies > 0 ? 'rgba(37, 99, 235, 0.32)' : 'rgba(234, 179, 8, 0.28)'}`,
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                            <strong style={{ fontSize: '0.95rem', color: 'var(--text-primary)' }}>
                              {detail.available_copies > 0
                                ? '📚 Online Loan Booking & Shelf Reservation'
                                : '🔖 Reserve Monograph (Waitlist Queue)'}
                            </strong>
                            <span
                              className={`badge ${detail.available_copies > 0 ? 'badge-success' : 'badge-warning'}`}
                              style={{ fontSize: '0.7rem' }}
                            >
                              {detail.available_copies > 0 ? 'Available for Collection' : 'All Copies on Loan'}
                            </span>
                          </div>
                          <p style={{ margin: '0.25rem 0 0', fontSize: '0.825rem', color: 'var(--text-secondary)', maxWidth: '460px' }}>
                            {detail.available_copies > 0
                              ? 'Book a physical copy online now. It will be immediately set aside at the library front desk with a 7-day pickup window and Collection QR pass.'
                              : 'All copies are currently borrowed. Place an online reservation to claim the next copy returned by another student.'}
                          </p>
                        </div>

                        <button
                          type="button"
                          className="btn btn-primary"
                          onClick={handlePlaceHold}
                          disabled={placingHold || !!createdHold}
                          style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.55rem 1.15rem', whiteSpace: 'nowrap' }}
                        >
                          <span>{detail.available_copies > 0 ? '⚡' : '🔖'}</span>
                          <span>
                            {placingHold
                              ? 'Processing...'
                              : createdHold
                              ? 'Reserved ✓'
                              : detail.available_copies > 0
                              ? 'Book Loan Online'
                              : 'Join Waitlist Queue'}
                          </span>
                        </button>
                      </div>

                      {holdMessage && (
                        <div
                          className="alert alert-success"
                          style={{
                            marginTop: '0.75rem',
                            padding: '0.75rem 0.9rem',
                            fontSize: '0.835rem',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
                            <span>{holdMessage}</span>
                            {createdHold?.status === 'ready_for_pickup' && (
                              <button
                                type="button"
                                className="btn btn-primary btn-sm"
                                onClick={() => setShowQRPassModal(true)}
                                style={{ fontSize: '0.78rem', whiteSpace: 'nowrap' }}
                              >
                                📱 Show Collection QR Pass
                              </button>
                            )}
                          </div>

                          {createdHold?.status === 'ready_for_pickup' && (
                            <div
                              style={{
                                marginTop: '0.75rem',
                                padding: '0.75rem 0.85rem',
                                background: 'rgba(14, 22, 38, 0.85)',
                                border: '1px solid rgba(56, 189, 248, 0.4)',
                                borderRadius: '8px',
                              }}
                            >
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
                                <div>
                                  <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.06em', color: '#94a3b8', fontWeight: 600 }}>
                                    Unique Token Number for Librarian Collection Approval:
                                  </div>
                                  <div style={{ fontSize: '1.25rem', fontFamily: 'monospace', fontWeight: 800, color: '#38bdf8', letterSpacing: '0.06em', marginTop: '0.15rem' }}>
                                    {createdHold.pickup_token || createdHold.copy_code || `#${createdHold.id}`}
                                  </div>
                                </div>
                                {createdHold.pickup_token && (
                                  <button
                                    type="button"
                                    className="btn btn-secondary btn-sm"
                                    onClick={() => {
                                      navigator.clipboard.writeText(createdHold.pickup_token!);
                                      setTokenCopied(true);
                                      setTimeout(() => setTokenCopied(false), 2000);
                                    }}
                                    style={{ fontSize: '0.75rem', padding: '0.3rem 0.65rem' }}
                                  >
                                    {tokenCopied ? '✓ Copied!' : '📋 Copy Token'}
                                  </button>
                                )}
                              </div>
                              <p style={{ margin: '0.35rem 0 0', fontSize: '0.76rem', color: '#94a3b8', lineHeight: 1.4 }}>
                                Present this token number to the librarian at the circulation desk. After handing you the physical copy, the librarian will verify the token to approve and activate your loan.
                              </p>
                            </div>
                          )}
                        </div>
                      )}

                      {holdError && (
                        <div className="alert alert-error" style={{ marginTop: '0.75rem', padding: '0.65rem 0.85rem', fontSize: '0.835rem' }}>
                          <span>{holdError}</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* Physical Inventory Copies */}
              <div style={{ marginTop: '1.5rem', borderTop: '1px solid var(--border-subtle)', paddingTop: '1.25rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                  <h4 style={{ fontSize: '1rem', margin: 0 }}>
                    Physical Inventory Copies ({detail.copies?.length || 0})
                  </h4>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => setShowShelfLocationModal(true)}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.4rem',
                      padding: '0.35rem 0.75rem',
                      fontSize: '0.8rem',
                      borderRadius: '6px',
                      background: 'rgba(99, 102, 241, 0.15)',
                      border: '1px solid rgba(99, 102, 241, 0.4)',
                      color: '#a5b4fc',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    <span>📍</span> Pinpoint Shelf Slot & Floor
                  </button>
                </div>
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

      {showQRPassModal && createdHold && (
        <QRCollectionModal
          holdId={createdHold.id}
          bookTitle={detail?.title || 'Monograph Collection'}
          onClose={() => setShowQRPassModal(false)}
        />
      )}

      {showShelfLocationModal && detail && (
        <BookShelfLocationModal
          bookId={detail.id}
          isOpen={showShelfLocationModal}
          onClose={() => setShowShelfLocationModal(false)}
        />
      )}
    </div>
  );
};
