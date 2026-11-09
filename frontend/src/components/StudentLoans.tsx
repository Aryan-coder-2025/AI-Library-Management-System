import React, { useEffect, useState, useCallback } from 'react';
import { apiFetch } from '../services/apiClient';
import type { BookHold, BookHoldListResponse, Loan, LoanPaginationResponse, UserProfile } from '../types/library';
import { QRCollectionModal } from './QRCollectionModal';
import { QRReturnModal } from './QRReturnModal';
import { ReturnReceiptModal } from './ReturnReceiptModal';
import { ClearanceCertificateModal } from './ClearanceCertificateModal';

interface StudentLoansProps {
  currentUser?: UserProfile | null;
}

export const StudentLoans: React.FC<StudentLoansProps> = ({ currentUser }) => {
  const [activeTabSection, setActiveTabSection] = useState<'loans' | 'holds'>('loans');
  const [loans, setLoans] = useState<Loan[]>([]);
  const [holds, setHolds] = useState<BookHold[]>([]);
  const [holdsLoading, setHoldsLoading] = useState(false);
  const [cancellingHoldId, setCancellingHoldId] = useState<number | null>(null);
  const [selectedHoldForQR, setSelectedHoldForQR] = useState<{ id: number; book_title: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [renewingLoanId, setRenewingLoanId] = useState<number | null>(null);
  const [selectedLoanForReturn, setSelectedLoanForReturn] = useState<{ id: number; book_title: string; copy_code?: string } | null>(null);
  const [selectedLoanForReceipt, setSelectedLoanForReceipt] = useState<number | null>(null);
  const [showClearanceModal, setShowClearanceModal] = useState<boolean>(false);
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'overdue' | 'returned'>('all');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  const isTeacher = currentUser?.role === 'teacher';
  const renewalDays = isTeacher ? 30 : 14;

  const fetchMyHolds = useCallback(async () => {
    setHoldsLoading(true);
    try {
      const data = await apiFetch<BookHoldListResponse>('/api/holds/me');
      setHolds(data.items);
    } catch (err: unknown) {
      console.error('Failed to load holds', err);
    } finally {
      setHoldsLoading(false);
    }
  }, []);

  const handleCancelHold = async (holdId: number) => {
    setCancellingHoldId(holdId);
    setError(null);
    try {
      await apiFetch(`/api/holds/${holdId}/cancel`, { method: 'POST' });
      setSuccessMsg('Hold cancelled successfully.');
      fetchMyHolds();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to cancel hold';
      setError(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setCancellingHoldId(null);
    }
  };

  const fetchMyLoans = useCallback(async () => {
    setLoading(true);
    setError(null);

    const params = new URLSearchParams();
    params.set('page', page.toString());
    params.set('page_size', '15');
    if (statusFilter !== 'all') {
      params.set('status', statusFilter);
    }

    try {
      const data = await apiFetch<LoanPaginationResponse>(`/api/loans/me?${params.toString()}`);
      setLoans(data.items);
      setTotalPages(data.total_pages);
      setTotalCount(data.total);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve your loans';
      setError(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter]);

  useEffect(() => {
    fetchMyLoans();
  }, [fetchMyLoans]);

  useEffect(() => {
    if (activeTabSection === 'holds') {
      fetchMyHolds();
    }
  }, [activeTabSection, fetchMyHolds]);

  const handleRenewLoan = async (loanId: number) => {
    setError(null);
    setSuccessMsg(null);
    setRenewingLoanId(loanId);

    try {
      const updated = await apiFetch<Loan>(`/api/loans/${loanId}/renew`, {
        method: 'POST',
      });
      setSuccessMsg(
        `Loan for "${updated.book_title}" successfully renewed! New due date is ${formatDate(updated.due_date)} (+${renewalDays} days).`
      );
      await fetchMyLoans();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to renew loan';
      setError(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setRenewingLoanId(null);
    }
  };

  const formatDate = (isoString: string | null) => {
    if (!isoString) return '—';
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
    } catch {
      return isoString;
    }
  };

  const getDaysRemainingText = (dueDateStr: string, isOverdue: boolean, returnedAt: string | null) => {
    if (returnedAt) return 'Returned';
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const due = new Date(dueDateStr);
    due.setHours(0, 0, 0, 0);
    const diffMs = due.getTime() - today.getTime();
    const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays < 0 || isOverdue) {
      return `Overdue by ${Math.abs(diffDays)} day${Math.abs(diffDays) === 1 ? '' : 's'}`;
    }
    if (diffDays === 0) return 'Due today';
    if (diffDays === 1) return 'Due tomorrow';
    return `${diffDays} days remaining`;
  };

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
        <div className="page-title-group">
          <h1>My Borrowing History & Active Loans</h1>
          <p className="page-subtitle">
            {isTeacher
              ? 'Faculty loan management, extended 30-day borrowing periods, and self-service renewals'
              : 'Track borrowed items, return dates, and circulation status'}
          </p>
        </div>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => setShowClearanceModal(true)}
          style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(56, 189, 248, 0.1)', borderColor: 'rgba(56, 189, 248, 0.4)', color: '#38bdf8' }}
          title="Inspect institutional circulation clearance & No-Dues certificate status"
        >
          <span>🎓</span>
          <span style={{ fontWeight: 600 }}>Library Clearance & No-Dues</span>
        </button>
      </div>

      <div className="alert alert-info" style={{ marginBottom: '1.25rem' }}>
        <div>
          <strong>Circulation Policy ({isTeacher ? 'Faculty' : 'Student'}): </strong>
          {isTeacher
            ? 'Faculty members may borrow up to 10 books concurrently for 30 days. Active loans can be renewed once for an additional 30 days if not overdue.'
            : 'Students may borrow up to 3 books concurrently for 14 days. Active loans can be renewed once for an additional 14 days if not overdue.'}
        </div>
      </div>

      {successMsg && (
        <div className="alert alert-success" style={{ marginBottom: '1.25rem' }}>
          <span>{successMsg}</span>
        </div>
      )}

      {error && (
        <div className="alert alert-error" style={{ marginBottom: '1.25rem' }}>
          <span>{error}</span>
        </div>
      )}

      {/* Primary Section Switcher */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.25rem', borderBottom: '1px solid var(--card-border)', paddingBottom: '0.75rem' }}>
        <button
          type="button"
          className={`btn ${activeTabSection === 'loans' ? 'btn-primary' : 'btn-secondary'} btn-sm`}
          onClick={() => setActiveTabSection('loans')}
        >
          📖 Active Loans & History ({totalCount})
        </button>
        <button
          type="button"
          className={`btn ${activeTabSection === 'holds' ? 'btn-primary' : 'btn-secondary'} btn-sm`}
          onClick={() => setActiveTabSection('holds')}
        >
          🔖 My Online Reservations & Waitlists
        </button>
      </div>

      {activeTabSection === 'holds' ? (
        <div>
          {holdsLoading ? (
            <div style={{ textAlign: 'center', padding: '3rem 0', color: 'var(--text-muted)' }}>
              Loading your book reservations...
            </div>
          ) : holds.length === 0 ? (
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
              <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>📚</div>
              <h4>No Active Reservations or Holds</h4>
              <p style={{ fontSize: '0.875rem' }}>
                You have not booked any monograph reservations. Browse the catalogue and click <strong>Book Loan Online</strong> on any available monograph to reserve a copy for desk collection with a QR pass.
              </p>
            </div>
          ) : (
            <div className="table-responsive">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Hold ID</th>
                    <th>Book Monograph</th>
                    <th>Status</th>
                    <th>Queue Position</th>
                    <th>Allocated Copy</th>
                    <th>Pickup Deadline</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {holds.map((hold) => (
                    <tr key={hold.id}>
                      <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>#{hold.id}</td>
                      <td>
                        <strong>{hold.book_title}</strong>
                        {hold.book_author && <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{hold.book_author}</div>}
                      </td>
                      <td>
                        <span
                          className={`badge ${
                            hold.status === 'ready_for_pickup'
                              ? 'badge-success'
                              : hold.status === 'waiting'
                              ? 'badge-warning'
                              : hold.status === 'fulfilled'
                              ? 'badge-neutral'
                              : 'badge-danger'
                          }`}
                        >
                          {hold.status === 'ready_for_pickup' ? '🎉 Ready for Pickup' : hold.status}
                        </span>
                      </td>
                      <td>
                        {hold.status === 'waiting' ? (
                          <span style={{ fontWeight: 600, color: 'var(--brand-secondary)' }}>
                            #{hold.queue_position || 1} in queue
                          </span>
                        ) : hold.status === 'ready_for_pickup' ? (
                          <span style={{ color: '#10b981', fontWeight: 600 }}>First in line (Copy allocated)</span>
                        ) : (
                          <span style={{ color: 'var(--text-muted)' }}>—</span>
                        )}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>
                        {hold.copy_code || 'Awaiting return'}
                      </td>
                      <td>
                        {hold.pickup_expires_at ? (
                          <span style={{ color: '#f59e0b', fontSize: '0.85rem' }}>
                            {new Date(hold.pickup_expires_at).toLocaleDateString()}
                          </span>
                        ) : (
                          <span style={{ color: 'var(--text-muted)' }}>—</span>
                        )}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                          {hold.status === 'ready_for_pickup' && (
                            <button
                              type="button"
                              className="btn btn-primary btn-sm"
                              onClick={() => setSelectedHoldForQR({ id: hold.id, book_title: hold.book_title })}
                              style={{ whiteSpace: 'nowrap' }}
                            >
                              📱 Collection Token & QR
                            </button>
                          )}
                          {(hold.status === 'waiting' || hold.status === 'ready_for_pickup') && (
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              disabled={cancellingHoldId === hold.id}
                              onClick={() => handleCancelHold(hold.id)}
                              style={{ color: '#ef4444' }}
                            >
                              {cancellingHoldId === hold.id ? 'Cancelling...' : 'Cancel Hold'}
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : (
        <>
          {/* Status Filter Tabs */}
      <div className="tab-group">
        <button
          type="button"
          className={`tab-btn ${statusFilter === 'all' ? 'active' : ''}`}
          onClick={() => {
            setStatusFilter('all');
            setPage(1);
          }}
        >
          All Records
        </button>
        <button
          type="button"
          className={`tab-btn ${statusFilter === 'active' ? 'active' : ''}`}
          onClick={() => {
            setStatusFilter('active');
            setPage(1);
          }}
        >
          Active Loans
        </button>
        <button
          type="button"
          className={`tab-btn ${statusFilter === 'overdue' ? 'active' : ''}`}
          onClick={() => {
            setStatusFilter('overdue');
            setPage(1);
          }}
        >
          Overdue Items
        </button>
        <button
          type="button"
          className={`tab-btn ${statusFilter === 'returned' ? 'active' : ''}`}
          onClick={() => {
            setStatusFilter('returned');
            setPage(1);
          }}
        >
          Returned History
        </button>
      </div>

      {loading && loans.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '3rem 0', color: 'var(--text-muted)' }}>
          Loading your borrowing record...
        </div>
      ) : loans.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-title">No loans found</div>
          <p className="empty-state-text">
            {statusFilter === 'active'
              ? 'You do not currently have any active loans checked out.'
              : statusFilter === 'overdue'
              ? 'Excellent! You have no overdue library books.'
              : 'You have no recorded borrowing history.'}
          </p>
        </div>
      ) : (
        <div>
          <div style={{ marginBottom: '0.5rem', fontSize: '0.85rem', color: 'var(--text-muted)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>Total records: {totalCount}</span>
          </div>

          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Book Title & Author</th>
                  <th>Barcode</th>
                  <th>Issued Date</th>
                  <th>Due Date</th>
                  <th>Status</th>
                  <th>Timeline</th>
                  <th>Self-Service Action</th>
                </tr>
              </thead>
              <tbody>
                {loans.map((loan) => {
                  const isOverdue = loan.status === 'overdue' || loan.is_overdue;
                  const isReturned = loan.status === 'returned' || loan.returned_at !== null;
                  const hasRenewed = (loan.renewal_count || 0) >= 1;
                  const isRenewing = renewingLoanId === loan.id;

                  return (
                    <tr key={loan.id} style={isOverdue ? { backgroundColor: '#fff5f5' } : {}}>
                      <td>
                        <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                          {loan.book_title}
                        </div>
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                          {loan.book_author}
                        </div>
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem' }}>
                        {loan.copy_code}
                      </td>
                      <td>{formatDate(loan.issued_at)}</td>
                      <td>
                        <span style={{ fontWeight: isOverdue ? 600 : 400, color: isOverdue ? 'var(--danger-text)' : 'inherit' }}>
                          {formatDate(loan.due_date)}
                        </span>
                        {hasRenewed && (
                          <div style={{ fontSize: '0.75rem', color: '#0d9488', fontWeight: 500 }}>
                            (Renewed {loan.renewal_count}x)
                          </div>
                        )}
                      </td>
                      <td>
                        <span
                          className={`badge ${
                            isReturned
                              ? 'badge-neutral'
                              : isOverdue
                              ? 'badge-danger'
                              : 'badge-success'
                          }`}
                        >
                          {isReturned ? '↩ Returned' : isOverdue ? '⚠️ Overdue' : '✓ Active'}
                        </span>
                      </td>
                      <td style={{ fontSize: '0.8rem', color: isOverdue ? 'var(--danger-text)' : 'var(--text-muted)' }}>
                        {getDaysRemainingText(loan.due_date, isOverdue, loan.returned_at)}
                      </td>
                      <td>
                        {isReturned ? (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <span style={{ fontSize: '0.8rem', color: '#10b981', fontWeight: 500 }}>Completed</span>
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              onClick={() => setSelectedLoanForReceipt(loan.id)}
                              style={{ padding: '0.2rem 0.55rem', fontSize: '0.75rem', borderColor: 'rgba(56, 189, 248, 0.4)', color: '#38bdf8' }}
                              title="View official return discharge receipt"
                            >
                              📄 Receipt
                            </button>
                          </div>
                        ) : (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexWrap: 'wrap' }}>
                            <button
                              type="button"
                              className="btn btn-primary btn-sm"
                              onClick={() => setSelectedLoanForReturn({ id: loan.id, book_title: loan.book_title, copy_code: loan.copy_code })}
                              style={{ padding: '0.25rem 0.6rem', fontSize: '0.78rem', background: '#2563eb', whiteSpace: 'nowrap' }}
                              title="Generate Return Clearance Pass & QR code for librarian check-in"
                            >
                              ↩ Return Pass
                            </button>

                            {!isOverdue && !hasRenewed && (
                              <button
                                type="button"
                                className="btn btn-secondary btn-sm"
                                disabled={isRenewing}
                                onClick={() => handleRenewLoan(loan.id)}
                                style={{ padding: '0.25rem 0.6rem', fontSize: '0.78rem', whiteSpace: 'nowrap' }}
                                title={`Extend due date by ${renewalDays} days`}
                              >
                                {isRenewing ? 'Renewing...' : `Renew (+${renewalDays}d)`}
                              </button>
                            )}
                            {hasRenewed && !isOverdue && (
                              <span style={{ fontSize: '0.75rem', color: '#64748b' }} title="Maximum 1 renewal limit reached">
                                Renewed (Max 1)
                              </span>
                            )}
                            {isOverdue && (
                              <span style={{ fontSize: '0.75rem', color: '#ef4444', fontWeight: 600 }}>
                                Overdue
                              </span>
                            )}
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="pagination-container">
              <span className="pagination-info">
                Page {page} of {totalPages}
              </span>
              <div className="pagination-controls">
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={page <= 1 || loading}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Previous
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={page >= totalPages || loading}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  )}
  {selectedHoldForQR && (
    <QRCollectionModal
      holdId={selectedHoldForQR.id}
      bookTitle={selectedHoldForQR.book_title}
      onClose={() => {
        setSelectedHoldForQR(null);
        fetchMyHolds();
        fetchMyLoans();
      }}
    />
  )}

  {selectedLoanForReturn && (
    <QRReturnModal
      loanId={selectedLoanForReturn.id}
      bookTitle={selectedLoanForReturn.book_title}
      copyCode={selectedLoanForReturn.copy_code}
      onClose={() => {
        setSelectedLoanForReturn(null);
        fetchMyLoans();
      }}
      onCancelled={() => {
        setSelectedLoanForReturn(null);
        fetchMyLoans();
      }}
    />
  )}

  {selectedLoanForReceipt !== null && (
    <ReturnReceiptModal
      loanId={selectedLoanForReceipt}
      onClose={() => setSelectedLoanForReceipt(null)}
    />
  )}

  {showClearanceModal && (
    <ClearanceCertificateModal
      onClose={() => setShowClearanceModal(false)}
      onInitiateReturn={(loanId, bookTitle, copyCode) => {
        setShowClearanceModal(false);
        setSelectedLoanForReturn({ id: loanId, book_title: bookTitle, copy_code: copyCode });
      }}
    />
  )}
</div>
);
};
