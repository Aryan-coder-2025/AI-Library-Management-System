import React, { useEffect, useState, useCallback } from 'react';
import { apiFetch } from '../services/apiClient';
import type { Loan, LoanPaginationResponse } from '../types/library';

export const LibrarianCirculation: React.FC = () => {
  const [loans, setLoans] = useState<Loan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Filters & Pagination
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'overdue' | 'returned'>('all');
  const [studentIdFilter, setStudentIdFilter] = useState('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  // Issue Loan Form State
  const [issueCopyId, setIssueCopyId] = useState('');
  const [issueStudentId, setIssueStudentId] = useState('');
  const [issueSubmitting, setIssueSubmitting] = useState(false);
  const [issueError, setIssueError] = useState<string | null>(null);

  // Return action in-flight ID
  const [returningLoanId, setReturningLoanId] = useState<number | null>(null);

  const fetchLoans = useCallback(async () => {
    setLoading(true);
    setError(null);

    const params = new URLSearchParams();
    params.set('page', page.toString());
    params.set('page_size', '15');
    if (statusFilter !== 'all') {
      params.set('status', statusFilter);
    }
    if (studentIdFilter.trim()) {
      params.set('student_id', studentIdFilter.trim());
    }

    try {
      const data = await apiFetch<LoanPaginationResponse>(`/api/loans?${params.toString()}`);
      setLoans(data.items);
      setTotalPages(data.total_pages);
      setTotalCount(data.total);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve loans';
      setError(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter, studentIdFilter]);

  useEffect(() => {
    fetchLoans();
  }, [fetchLoans]);

  const handleIssueLoan = async (e: React.FormEvent) => {
    e.preventDefault();
    const copyIdNum = parseInt(issueCopyId.trim(), 10);
    const studentIdNum = parseInt(issueStudentId.trim(), 10);

    if (isNaN(copyIdNum) || isNaN(studentIdNum)) {
      setIssueError('Please provide valid integer Copy ID and Student ID');
      return;
    }

    setIssueSubmitting(true);
    setIssueError(null);

    try {
      const issued = await apiFetch<Loan>('/api/loans/issue', {
        method: 'POST',
        body: JSON.stringify({
          copy_id: copyIdNum,
          student_id: studentIdNum,
        }),
      });
      setActionSuccess(`Loan #${issued.id} issued successfully for "${issued.book_title}" (Barcode: ${issued.copy_code})`);
      setIssueCopyId('');
      setIssueStudentId('');
      fetchLoans();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to issue loan';
      setIssueError(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setIssueSubmitting(false);
    }
  };

  const handleReturnLoan = async (loan: Loan) => {
    const confirmReturn = window.confirm(
      `Confirm return for "${loan.book_title}" (Copy: ${loan.copy_code})?`
    );
    if (!confirmReturn) return;

    setReturningLoanId(loan.id);
    try {
      await apiFetch<Loan>(`/api/loans/${loan.id}/return`, {
        method: 'POST',
      });
      setActionSuccess(`Returned "${loan.book_title}" (Copy: ${loan.copy_code}) successfully.`);
      fetchLoans();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to return loan';
      alert(`Error returning loan: ${msg.replace(/^\d+:\s*/, '')}`);
    } finally {
      setReturningLoanId(null);
    }
  };

  const formatDate = (isoStr: string | null) => {
    if (!isoStr) return '—';
    try {
      return new Date(isoStr).toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
    } catch {
      return isoStr;
    }
  };

  return (
    <div>
      <div className="page-header">
        <div className="page-title-group">
          <h1>Circulation Desk</h1>
          <p className="page-subtitle">
            Issue physical book copies, process returns, and inspect active loans
          </p>
        </div>
      </div>

      {actionSuccess && (
        <div className="alert alert-success" style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span>{actionSuccess}</span>
          <button
            type="button"
            onClick={() => setActionSuccess(null)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', fontWeight: 600 }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Quick Issue Panel */}
      <div className="card" style={{ padding: '1.25rem', marginBottom: '1.75rem' }}>
        <h3 style={{ fontSize: '1.05rem', marginBottom: '0.35rem' }}>Issue Copy to Student</h3>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
          Assign an available physical copy to an active registered student account.
        </p>

        {issueError && (
          <div className="alert alert-error" style={{ marginBottom: '1rem' }}>
            <span>{issueError}</span>
          </div>
        )}

        <form onSubmit={handleIssueLoan} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr)) 160px', gap: '0.75rem', alignItems: 'end' }}>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label" htmlFor="issue-copy-id">
              Physical Copy ID *
              <span className="form-label-hint">(See Catalogue Management &gt; Copies)</span>
            </label>
            <input
              id="issue-copy-id"
              type="number"
              min="1"
              className="form-input"
              placeholder="e.g. 2"
              value={issueCopyId}
              onChange={(e) => setIssueCopyId(e.target.value)}
              required
            />
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label" htmlFor="issue-student-id">
              Student User ID *
              <span className="form-label-hint">(Patron user ID, e.g. 3)</span>
            </label>
            <input
              id="issue-student-id"
              type="number"
              min="1"
              className="form-input"
              placeholder="e.g. 3"
              value={issueStudentId}
              onChange={(e) => setIssueStudentId(e.target.value)}
              required
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            style={{ height: '38px' }}
            disabled={issueSubmitting || !issueCopyId.trim() || !issueStudentId.trim()}
          >
            {issueSubmitting ? 'Issuing...' : 'Issue Book Loan'}
          </button>
        </form>
      </div>

      {/* Circulation Records Search & Tabs */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', marginBottom: '1rem' }}>
        <div className="tab-group" style={{ marginBottom: 0 }}>
          <button
            type="button"
            className={`tab-btn ${statusFilter === 'all' ? 'active' : ''}`}
            onClick={() => {
              setStatusFilter('all');
              setPage(1);
            }}
          >
            All Loans
          </button>
          <button
            type="button"
            className={`tab-btn ${statusFilter === 'active' ? 'active' : ''}`}
            onClick={() => {
              setStatusFilter('active');
              setPage(1);
            }}
          >
            Active
          </button>
          <button
            type="button"
            className={`tab-btn ${statusFilter === 'overdue' ? 'active' : ''}`}
            onClick={() => {
              setStatusFilter('overdue');
              setPage(1);
            }}
          >
            Overdue
          </button>
          <button
            type="button"
            className={`tab-btn ${statusFilter === 'returned' ? 'active' : ''}`}
            onClick={() => {
              setStatusFilter('returned');
              setPage(1);
            }}
          >
            Returned
          </button>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <input
            type="number"
            min="1"
            className="form-input"
            style={{ width: '160px' }}
            placeholder="Filter by Student ID"
            value={studentIdFilter}
            onChange={(e) => {
              setStudentIdFilter(e.target.value);
              setPage(1);
            }}
          />
          {studentIdFilter && (
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => {
                setStudentIdFilter('');
                setPage(1);
              }}
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="alert alert-error">
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: 'center', padding: '3rem 0', color: 'var(--text-muted)' }}>
          Loading circulation records...
        </div>
      ) : loans.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-title">No circulation loans found</div>
          <p className="empty-state-text">
            No records matched your status or Student ID filter.
          </p>
        </div>
      ) : (
        <>
          <div style={{ marginBottom: '0.5rem', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            Showing {loans.length} of {totalCount} total loan records
          </div>

          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Loan ID</th>
                  <th>Student</th>
                  <th>Book Title</th>
                  <th>Barcode</th>
                  <th>Issued Date</th>
                  <th>Due Date</th>
                  <th>Status</th>
                  <th style={{ textAlign: 'right' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {loans.map((loan) => {
                  const isOverdue = loan.status === 'overdue' || loan.is_overdue;
                  const isReturned = loan.status === 'returned' || loan.returned_at !== null;

                  return (
                    <tr key={loan.id} style={isOverdue ? { backgroundColor: '#fff5f5' } : {}}>
                      <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                        #{loan.id}
                      </td>
                      <td>
                        <div style={{ fontWeight: 600 }}>
                          {loan.student_name || `Student #${loan.student_id}`}
                        </div>
                        <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                          ID: {loan.student_id} {loan.student_email ? `• ${loan.student_email}` : ''}
                        </div>
                      </td>
                      <td>
                        <div style={{ fontWeight: 500 }}>{loan.book_title}</div>
                        <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
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
                      <td style={{ textAlign: 'right' }}>
                        {!isReturned ? (
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            disabled={returningLoanId === loan.id}
                            onClick={() => handleReturnLoan(loan)}
                          >
                            {returningLoanId === loan.id ? 'Processing...' : 'Record Return'}
                          </button>
                        ) : (
                          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                            {formatDate(loan.returned_at)}
                          </span>
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
