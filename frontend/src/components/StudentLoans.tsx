import React, { useEffect, useState, useCallback } from 'react';
import { apiFetch } from '../services/apiClient';
import type { Loan, LoanPaginationResponse, UserProfile } from '../types/library';

interface StudentLoansProps {
  currentUser?: UserProfile | null;
}

export const StudentLoans: React.FC<StudentLoansProps> = ({ currentUser }) => {
  const [loans, setLoans] = useState<Loan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [renewingLoanId, setRenewingLoanId] = useState<number | null>(null);
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'overdue' | 'returned'>('all');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  const isTeacher = currentUser?.role === 'teacher';
  const renewalDays = isTeacher ? 30 : 14;

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
      <div className="page-header">
        <div className="page-title-group">
          <h1>My Borrowing History & Active Loans</h1>
          <p className="page-subtitle">
            {isTeacher
              ? 'Faculty loan management, extended 30-day borrowing periods, and self-service renewals'
              : 'Track borrowed items, return dates, and circulation status'}
          </p>
        </div>
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

      {loading ? (
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
        <>
          <div style={{ marginBottom: '0.5rem', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            Total records: {totalCount}
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
                          <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Completed</span>
                        ) : isOverdue ? (
                          <span style={{ fontSize: '0.8rem', color: '#dc2626', fontWeight: 500 }} title="Overdue loans must be returned to the circulation desk">
                            Overdue (Visit Desk)
                          </span>
                        ) : hasRenewed ? (
                          <span style={{ fontSize: '0.8rem', color: '#64748b' }} title="Maximum 1 renewal limit reached">
                            Renewed (Limit 1)
                          </span>
                        ) : (
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            disabled={isRenewing}
                            onClick={() => handleRenewLoan(loan.id)}
                            style={{ whiteSpace: 'nowrap' }}
                            title={`Extend due date by ${renewalDays} days`}
                          >
                            {isRenewing ? 'Renewing...' : `Renew (+${renewalDays}d)`}
                          </button>
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
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Previous
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};
