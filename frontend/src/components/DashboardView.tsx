import React, { useEffect, useState } from 'react';
import { apiFetch } from '../services/apiClient';
import type { UserProfile, Loan, Book, BookPaginationResponse, LoanPaginationResponse } from '../types/library';
import type { SubjectTree } from '../types/knowledge';
import { BookCover } from './BookCover';

interface DashboardViewProps {
  currentUser: UserProfile | null;
  onSelectTab: (tab: string) => void;
  onOpenCopilot: () => void;
  onSelectBook: (id: number) => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  currentUser,
  onSelectTab,
  onOpenCopilot,
  onSelectBook,
}) => {
  const [activeLoans, setActiveLoans] = useState<Loan[]>([]);
  const [recommendedBooks, setRecommendedBooks] = useState<Book[]>([]);
  const [subjectCount, setSubjectCount] = useState<number>(3);
  const [availableSeatsCount, setAvailableSeatsCount] = useState<number>(148);
  const [loading, setLoading] = useState<boolean>(true);
  const [renewingLoanId, setRenewingLoanId] = useState<number | null>(null);
  const [renewSuccess, setRenewSuccess] = useState<string | null>(null);

  const isPatron = currentUser?.role === 'student' || currentUser?.role === 'teacher';
  const isLibrarian = currentUser?.role === 'librarian';

  useEffect(() => {
    let isMounted = true;
    setLoading(true);

    const loadData = async () => {
      // 1. Load active loans if patron
      if (currentUser && isPatron) {
        try {
          const res = await apiFetch<LoanPaginationResponse>('/api/loans/me?status=active&page=1&page_size=5');
          if (isMounted) setActiveLoans(res.items);
        } catch {
          // Fallback gracefully
        }
      }

      // 2. Load featured monographs
      try {
        const booksRes = await apiFetch<BookPaginationResponse>('/api/books?page=1&page_size=6');
        if (isMounted) setRecommendedBooks(booksRes.items);
      } catch {
        // Fallback gracefully
      }

      // 3. Load knowledge subject count
      try {
        const subjectsRes = await apiFetch<SubjectTree[]>('/api/knowledge/subjects/tree');
        if (isMounted && Array.isArray(subjectsRes) && subjectsRes.length > 0) {
          setSubjectCount(subjectsRes.length);
        }
      } catch {
        // Keep default estimate
      }

      // 4. Load spaces telemetry if available
      try {
        const zonesRes = await apiFetch<any[]>('/api/spaces/zones');
        if (isMounted && Array.isArray(zonesRes)) {
          const totalAvail = zonesRes.reduce((acc, z) => acc + (z.available_seats_count || 0), 0);
          if (totalAvail > 0) setAvailableSeatsCount(totalAvail);
        }
      } catch {
        // Keep default
      }

      if (isMounted) setLoading(false);
    };

    loadData();
    return () => {
      isMounted = false;
    };
  }, [currentUser, isPatron]);

  const handleRenew = async (loanId: number, title: string) => {
    setRenewingLoanId(loanId);
    setRenewSuccess(null);
    try {
      await apiFetch(`/api/loans/${loanId}/renew`, { method: 'POST' });
      setRenewSuccess(`"${title}" has been successfully extended!`);
      // Refresh active loans
      const updated = await apiFetch<LoanPaginationResponse>('/api/loans/me?status=active&page=1&page_size=5');
      setActiveLoans(updated.items);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Renewal failed';
      alert(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setRenewingLoanId(null);
    }
  };

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 17) return 'Good afternoon';
    return 'Good evening';
  };

  const calculateDaysRemaining = (dueDateStr: string | null) => {
    if (!dueDateStr) return 0;
    const due = new Date(dueDateStr);
    const now = new Date();
    const diff = Math.ceil((due.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
    return diff;
  };

  return (
    <div className="dashboard-container">
      {/* Hero Welcome Banner */}
      <section className="dashboard-hero-card">
        <div className="hero-content-col">
          <div className="hero-tag-pill">
            <span className="pulsing-neon-dot" />
            <span>ATHENAEUM ACADEMIC INTELLIGENCE PLATFORM</span>
          </div>
          <h1 className="hero-title">
            {getGreeting()}, {currentUser ? currentUser.full_name : 'Guest Scholar'}
          </h1>
          <p className="hero-subtitle">
            Welcome to your unified academic research environment. Explore verified collection monographs, run vector semantic inquiries, or access intelligent wayfinding across library floors.
          </p>

          <div className="hero-action-row">
            <button
              type="button"
              className="btn btn-primary"
              onClick={onOpenCopilot}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
            >
              <span>✨ Ask AI Copilot</span>
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => onSelectTab('semantic')}
            >
              <span>🧠 Vector Search</span>
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => onSelectTab('catalogue')}
            >
              <span>📚 Browse Catalogue</span>
            </button>
            {isPatron && (
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => onSelectTab('spaces')}
              >
                <span>🏛️ Floor Plans & Seats</span>
              </button>
            )}
            {isLibrarian && (
              <button
                type="button"
                className="btn btn-accent"
                onClick={() => onSelectTab('circulation')}
              >
                <span>🔄 Circulation Desk</span>
              </button>
            )}
          </div>
        </div>

        <div className="hero-stats-badge-col">
          <div className="hero-micro-card">
            <div className="hero-micro-label">Active Research Session</div>
            <div className="hero-micro-value">{currentUser ? currentUser.role.toUpperCase() : 'PUBLIC OPAC'}</div>
            <div className="hero-micro-sub">
              {new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric', year: 'numeric' })}
            </div>
          </div>
        </div>
      </section>

      {/* KPI Stat Cards Row */}
      <section className="dashboard-kpi-grid">
        <div className="kpi-card" onClick={() => onSelectTab(isPatron ? 'loans' : 'catalogue')}>
          <div className="kpi-icon-wrap" style={{ background: 'rgba(128, 87, 245, 0.15)', color: 'var(--color-primary)' }}>
            📖
          </div>
          <div className="kpi-body">
            <div className="kpi-label">Active Monograph Loans</div>
            <div className="kpi-value">
              {currentUser && isPatron ? `${activeLoans.length} / ${currentUser.role === 'teacher' ? 5 : 3}` : 'OPAC Mode'}
            </div>
            <div className="kpi-sub">
              {activeLoans.some((l) => calculateDaysRemaining(l.due_date) < 0) ? (
                <span style={{ color: 'var(--danger-text)', fontWeight: 600 }}>⚠️ Overdue loan requires attention</span>
              ) : (
                <span>All active loans in good standing</span>
              )}
            </div>
          </div>
        </div>

        <div className="kpi-card" onClick={() => onSelectTab(isPatron ? 'spaces' : 'catalogue')}>
          <div className="kpi-icon-wrap" style={{ background: 'rgba(34, 211, 238, 0.15)', color: 'var(--color-accent)' }}>
            🏛️
          </div>
          <div className="kpi-body">
            <div className="kpi-label">Campus Study Pods & Seats</div>
            <div className="kpi-value">{availableSeatsCount} Available</div>
            <div className="kpi-sub">
              <span>Across Ground, 1st, 2nd & 3rd Floors</span>
            </div>
          </div>
        </div>

        <div className="kpi-card" onClick={() => onSelectTab('knowledge')}>
          <div className="kpi-icon-wrap" style={{ background: 'rgba(52, 211, 153, 0.15)', color: 'var(--success-text)' }}>
            🔬
          </div>
          <div className="kpi-body">
            <div className="kpi-label">Academic Disciplines</div>
            <div className="kpi-value">{subjectCount} Taxonomies</div>
            <div className="kpi-sub">
              <span>CS, Mathematics, Information Science</span>
            </div>
          </div>
        </div>

        <div className="kpi-card" onClick={() => onSelectTab('semantic')}>
          <div className="kpi-icon-wrap" style={{ background: 'rgba(251, 191, 36, 0.15)', color: 'var(--warning-text)' }}>
            ⚡
          </div>
          <div className="kpi-body">
            <div className="kpi-label">AI Embedding Vectors</div>
            <div className="kpi-value">384-Dim Ready</div>
            <div className="kpi-sub">
              <span>sentence-transformers / MiniLM</span>
            </div>
          </div>
        </div>
      </section>

      {/* Active Loans Section (for authenticated students & teachers) */}
      {currentUser && isPatron && (
        <section className="dashboard-section">
          <div className="section-header-row">
            <div>
              <h2 className="section-title">My Active Circulation Loans</h2>
              <p className="section-subtitle">Monographs currently checked out to your patron account</p>
            </div>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => onSelectTab('loans')}
            >
              View Circulation History →
            </button>
          </div>

          {renewSuccess && (
            <div className="alert alert-success" style={{ margin: '0.5rem 0 1rem' }}>
              <span>{renewSuccess}</span>
            </div>
          )}

          {loading ? (
            <div className="dashboard-loading-box">Checking patron records...</div>
          ) : activeLoans.length === 0 ? (
            <div className="dashboard-empty-panel">
              <span className="empty-panel-icon">📚</span>
              <h4>No Active Loans Outstanding</h4>
              <p>You have not checked out any books today. You have all borrowing slots available!</p>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={() => onSelectTab('catalogue')}
              >
                Explore Catalogue Monographs
              </button>
            </div>
          ) : (
            <div className="dashboard-loans-grid">
              {activeLoans.map((loan) => {
                const daysLeft = calculateDaysRemaining(loan.due_date);
                const isOverdue = daysLeft < 0;
                return (
                  <div key={loan.id} className={`loan-card ${isOverdue ? 'overdue' : ''}`}>
                    <div className="loan-card-header">
                      <span className={`status-pill ${isOverdue ? 'pill-overdue' : 'pill-active'}`}>
                        {isOverdue ? `Overdue by ${Math.abs(daysLeft)}d` : `Due in ${daysLeft} days`}
                      </span>
                      <span className="barcode-tag">{loan.copy_code}</span>
                    </div>

                    <h4 className="loan-book-title">{loan.book_title}</h4>
                    <div className="loan-meta-row">
                      <span>Author: {loan.book_author || 'University Press'}</span>
                      <span>Due: {loan.due_date ? new Date(loan.due_date).toLocaleDateString() : '—'}</span>
                    </div>

                    <div className="loan-card-footer">
                      <span className="renewal-counter">
                        Renewals used: {loan.renewal_count || 0}/1
                      </span>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        disabled={renewingLoanId === loan.id || (loan.renewal_count || 0) >= 1}
                        onClick={() => handleRenew(loan.id, loan.book_title)}
                      >
                        {renewingLoanId === loan.id ? 'Renewing...' : (loan.renewal_count || 0) >= 1 ? 'Renewed' : 'Renew Loan'}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      )}

      {/* Recommended Academic Readings */}
      <section className="dashboard-section">
        <div className="section-header-row">
          <div>
            <h2 className="section-title">Recommended Academic Monographs</h2>
            <p className="section-subtitle">Core collection titles across Computer Science, AI, and Advanced Mathematics</p>
          </div>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => onSelectTab('catalogue')}
          >
            Browse Full Catalogue →
          </button>
        </div>

        <div className="book-grid">
          {recommendedBooks.map((book) => (
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
            >
              <BookCover title={book.title} author={book.author} category={book.category} />
              <div className="book-card-body">
                <h3 className="book-card-title">{book.title}</h3>
                <div className="book-card-author">{book.author}</div>
                <div className="book-card-footer">
                  <span className="badge badge-neutral">{book.category}</span>
                  <span className={`availability-indicator ${book.available_copies > 0 ? 'in-stock' : 'out-of-stock'}`}>
                    {book.available_copies > 0 ? `${book.available_copies} copies` : 'Checked out'}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Spatial Telemetry & Knowledge Discovery Teaser */}
      <section className="dashboard-split-grid">
        <div className="dashboard-feature-card">
          <div className="feature-card-header">
            <span className="feature-icon">🏛️</span>
            <div>
              <h3>Interactive Architectural Wayfinding</h3>
              <p>Explore real-time occupancy across Ground, 1st, 2nd, and 3rd Floors</p>
            </div>
          </div>
          <p className="feature-card-desc">
            Find quiet focus zones, check seminar room availability (Ada, Turing, Hopper, Shannon suites), or generate instant QR passes for seat verification.
          </p>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => onSelectTab(isPatron ? 'spaces' : 'catalogue')}
          >
            Open Floor Plans Canvas →
          </button>
        </div>

        <div className="dashboard-feature-card">
          <div className="feature-card-header">
            <span className="feature-icon">🧠</span>
            <div>
              <h3>Academic Knowledge Graph</h3>
              <p>Discover structured subject-topic-concept hierarchies</p>
            </div>
          </div>
          <p className="feature-card-desc">
            Explore mapped academic concepts from neural networks and distributed systems to spectral linear algebra, interconnected with library holdings.
          </p>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => onSelectTab('knowledge')}
          >
            Launch Knowledge Explorer →
          </button>
        </div>
      </section>
    </div>
  );
};

