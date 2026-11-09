import React, { useState, useEffect, useCallback } from 'react';
import { apiFetch, getCsrfToken } from '../../services/apiClient';

interface ExecutiveSnapshot {
  active_loans_count: number;
  overdue_loans_count: number;
  overdue_rate_pct: number;
  active_holds_count: number;
  current_occupancy_pct: number;
  peak_occupancy_hour: number;
  monograph_count: number;
  generated_at: string;
}

interface CirculationPoint {
  date: string;
  issues: number;
  returns: number;
}

interface CirculationTrends {
  points: CirculationPoint[];
  total_issues: number;
  total_returns: number;
  velocity_ratio: number;
}

interface InventoryMetrics {
  total_monographs: number;
  total_physical_copies: number;
  available_copies: number;
  borrowed_copies: number;
  maintenance_copies: number;
  damaged_copies: number;
  lost_copies: number;
  high_demand_titles_count: number;
  zero_borrow_titles_count: number;
  collection_turnover_rate: number;
  total_audit_events_count: number;
}

interface DemandProjection {
  date: string;
  day_of_week: string;
  projected_checkouts: number;
  lower_bound: number;
  upper_bound: number;
}

interface DemandForecast {
  projections: DemandProjection[];
  baseline_daily_average: number;
  trend_direction: string;
  methodology: string;
}

interface AcquisitionRequest {
  id: number;
  suggested_title: string;
  suggested_author?: string;
  isbn?: string;
  status: 'suggested' | 'approved' | 'ordered' | 'received' | 'rejected';
  requested_by_id?: number;
  rationale?: string;
  estimated_cost?: number;
  created_at: string;
}

interface ZeroResultSuggestion {
  query_text: string;
  frequency: number;
  last_searched: string;
}

export const LibrarianIntelligenceCenter: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'snapshot' | 'inventory' | 'forecast' | 'acquisitions'>('snapshot');

  const [snapshot, setSnapshot] = useState<ExecutiveSnapshot | null>(null);
  const [trends, setTrends] = useState<CirculationTrends | null>(null);
  const [inventory, setInventory] = useState<InventoryMetrics | null>(null);
  const [forecast, setForecast] = useState<DemandForecast | null>(null);
  const [acquisitions, setAcquisitions] = useState<AcquisitionRequest[]>([]);
  const [suggestions, setSuggestions] = useState<ZeroResultSuggestion[]>([]);

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Modal State for new candidate request
  const [showAddModal, setShowAddModal] = useState<boolean>(false);
  const [reqTitle, setReqTitle] = useState('');
  const [reqAuthor, setReqAuthor] = useState('');
  const [reqIsbn, setReqIsbn] = useState('');
  const [reqNotes, setReqNotes] = useState('');
  const [submittingReq, setSubmittingReq] = useState(false);

  const fetchAllIntelligenceData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [snapRes, trendsRes, invRes, foreRes, acqRes, suggRes] = await Promise.all([
        apiFetch<ExecutiveSnapshot>('/api/intelligence/snapshot').catch(() => null),
        apiFetch<CirculationTrends>('/api/intelligence/circulation-velocity?days=14').catch(() => null),
        apiFetch<InventoryMetrics>('/api/intelligence/inventory-turnover').catch(() => null),
        apiFetch<DemandForecast>('/api/intelligence/demand-forecast?days=14').catch(() => null),
        apiFetch<AcquisitionRequest[]>('/api/intelligence/acquisitions').catch(() => []),
        apiFetch<ZeroResultSuggestion[]>('/api/intelligence/zero-result-suggestions').catch(() => []),
      ]);

      if (snapRes) setSnapshot(snapRes);
      if (trendsRes) setTrends(trendsRes);
      if (invRes) setInventory(invRes);
      if (foreRes) setForecast(foreRes);
      if (acqRes) setAcquisitions(acqRes);
      if (suggRes) setSuggestions(suggRes);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve intelligence analytics.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAllIntelligenceData();
  }, [fetchAllIntelligenceData]);

  const handleCreateAcquisitionRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reqTitle.trim()) return;

    setSubmittingReq(true);
    try {
      const csrfToken = getCsrfToken();
      const res = await fetch('/api/intelligence/acquisitions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken,
        },
        body: JSON.stringify({
          suggested_title: reqTitle.trim(),
          suggested_author: reqAuthor.trim() || undefined,
          isbn: reqIsbn.trim() || undefined,
          rationale: reqNotes.trim() || undefined,
        }),
      });

      if (res.ok) {
        setShowAddModal(false);
        setReqTitle('');
        setReqAuthor('');
        setReqIsbn('');
        setReqNotes('');
        fetchAllIntelligenceData();
      }
    } catch (err) {
      console.error('Failed to create acquisition candidate:', err);
    } finally {
      setSubmittingReq(false);
    }
  };

  const handleUpdateAcquisitionStatus = async (reqId: number, newStatus: string) => {
    try {
      const csrfToken = getCsrfToken();
      const res = await fetch(`/api/intelligence/acquisitions/${reqId}/status`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken,
        },
        body: JSON.stringify({ status: newStatus }),
      });

      if (res.ok) {
        setAcquisitions((prev) =>
          prev.map((item) => (item.id === reqId ? { ...item, status: newStatus as any } : item))
        );
      }
    } catch (err) {
      console.error('Failed to update acquisition status:', err);
    }
  };

  return (
    <div style={{ maxWidth: '1360px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1.5rem', paddingBottom: '3rem' }}>
      {/* Cockpit Header */}
      <div
        style={{
          background: 'var(--card-bg, #0E1626)',
          border: '1px solid var(--card-border, rgba(148, 163, 184, 0.16))',
          borderRadius: '14px',
          padding: '1.5rem 1.75rem',
          boxShadow: 'var(--card-shadow)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '1rem',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ fontSize: '1.75rem' }}>🏛️</span>
            <h2 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-primary, #F8FAFC)', letterSpacing: '-0.02em' }}>
              Librarian Intelligence Centre
            </h2>
            <span
              style={{
                fontSize: '0.7rem',
                fontWeight: 700,
                textTransform: 'uppercase',
                padding: '3px 8px',
                borderRadius: '6px',
                background: 'rgba(56, 189, 248, 0.12)',
                color: 'var(--brand-secondary, #38BDF8)',
                border: '1px solid rgba(56, 189, 248, 0.3)',
              }}
            >
              ADMIN COCKPIT
            </span>
          </div>
          <p style={{ margin: '0.4rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-secondary, #94A3B8)', maxWidth: '780px', lineHeight: 1.5 }}>
            Unified administrative intelligence cockpit for institutional circulation trends, collection turnover, predictive demand forecasting, and zero-search procurement workflows.
          </p>
        </div>

        <button
          type="button"
          onClick={fetchAllIntelligenceData}
          className="btn btn-secondary"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.6rem 1.15rem',
            fontSize: '0.825rem',
            fontWeight: 600,
          }}
        >
          <span>🔄</span>
          <span>Refresh Data</span>
        </button>
      </div>

      {error && (
        <div className="alert alert-error">
          <span>⚠️ {error}</span>
          <button type="button" className="btn btn-secondary btn-sm" onClick={fetchAllIntelligenceData}>
            Retry
          </button>
        </div>
      )}

      {/* Navigation Sub-Tabs */}
      <div
        style={{
          display: 'flex',
          gap: '0.5rem',
          borderBottom: '1px solid var(--border-medium, rgba(148, 163, 184, 0.2))',
          paddingBottom: '0.75rem',
          flexWrap: 'wrap',
        }}
      >
        {[
          { key: 'snapshot', label: '📊 Executive Snapshot (INTEL-02)' },
          { key: 'inventory', label: '📦 Inventory & Turnover (INTEL-04)' },
          { key: 'forecast', label: '📈 2-Week Demand Forecast (INTEL-03)' },
          { key: 'acquisitions', label: '🛍️ Acquisitions Pipeline (INTEL-05)' },
        ].map((tab) => {
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key as any)}
              style={{
                padding: '0.6rem 1.15rem',
                borderRadius: '8px',
                fontSize: '0.85rem',
                fontWeight: 600,
                border: isActive
                  ? '1px solid var(--brand-secondary, #38BDF8)'
                  : '1px solid var(--border-subtle, rgba(148, 163, 184, 0.16))',
                background: isActive ? 'var(--nav-item-active-bg, rgba(56, 189, 248, 0.14))' : 'var(--bg-surface, #0E1626)',
                color: isActive ? 'var(--brand-secondary, #38BDF8)' : 'var(--text-secondary, #94A3B8)',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {loading ? (
        <div
          style={{
            background: 'var(--card-bg, #0E1626)',
            padding: '4rem 1rem',
            borderRadius: '12px',
            border: '1px solid var(--card-border, rgba(148, 163, 184, 0.16))',
            textAlign: 'center',
            color: 'var(--text-secondary, #94A3B8)',
            fontSize: '0.95rem',
          }}
        >
          <span style={{ fontSize: '2rem', display: 'block', marginBottom: '0.75rem' }}>⏳</span>
          Aggregating institutional telemetry & circulation intelligence...
        </div>
      ) : (
        <div>
          {/* TAB 1: EXECUTIVE SNAPSHOT */}
          {activeTab === 'snapshot' && snapshot && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              {/* 4 KPI Cards Grid */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
                  gap: '1rem',
                }}
              >
                <div
                  style={{
                    background: 'var(--card-bg, #0E1626)',
                    border: '1px solid var(--card-border, rgba(148, 163, 184, 0.16))',
                    borderRadius: '12px',
                    padding: '1.25rem',
                    boxShadow: 'var(--card-shadow)',
                  }}
                >
                  <span style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted, #64748B)', letterSpacing: '0.05em' }}>
                    Active Loans
                  </span>
                  <div style={{ fontSize: '2.2rem', fontWeight: 800, color: 'var(--accent-cyan, #38BDF8)', margin: '0.35rem 0' }}>
                    {snapshot.active_loans_count}
                  </div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary, #94A3B8)' }}>
                    Total circulating monograph copies
                  </div>
                </div>

                <div
                  style={{
                    background: 'var(--card-bg, #0E1626)',
                    border: '1px solid var(--card-border, rgba(148, 163, 184, 0.16))',
                    borderRadius: '12px',
                    padding: '1.25rem',
                    boxShadow: 'var(--card-shadow)',
                  }}
                >
                  <span style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted, #64748B)', letterSpacing: '0.05em' }}>
                    Overdue Rate
                  </span>
                  <div style={{ fontSize: '2.2rem', fontWeight: 800, color: snapshot.overdue_rate_pct > 0 ? '#FB7185' : '#34D399', margin: '0.35rem 0' }}>
                    {snapshot.overdue_rate_pct}%
                  </div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary, #94A3B8)' }}>
                    {snapshot.overdue_loans_count} overdue patron accounts
                  </div>
                </div>

                <div
                  style={{
                    background: 'var(--card-bg, #0E1626)',
                    border: '1px solid var(--card-border, rgba(148, 163, 184, 0.16))',
                    borderRadius: '12px',
                    padding: '1.25rem',
                    boxShadow: 'var(--card-shadow)',
                  }}
                >
                  <span style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted, #64748B)', letterSpacing: '0.05em' }}>
                    Active Holds
                  </span>
                  <div style={{ fontSize: '2.2rem', fontWeight: 800, color: '#FBBF24', margin: '0.35rem 0' }}>
                    {snapshot.active_holds_count}
                  </div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary, #94A3B8)' }}>
                    Patrons currently in reservation waitlist
                  </div>
                </div>

                <div
                  style={{
                    background: 'var(--card-bg, #0E1626)',
                    border: '1px solid var(--card-border, rgba(148, 163, 184, 0.16))',
                    borderRadius: '12px',
                    padding: '1.25rem',
                    boxShadow: 'var(--card-shadow)',
                  }}
                >
                  <span style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted, #64748B)', letterSpacing: '0.05em' }}>
                    Space Occupancy
                  </span>
                  <div style={{ fontSize: '2.2rem', fontWeight: 800, color: '#34D399', margin: '0.35rem 0' }}>
                    {snapshot.current_occupancy_pct}%
                  </div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary, #94A3B8)' }}>
                    Diurnal Peak Hour: ~{snapshot.peak_occupancy_hour}:00
                  </div>
                </div>
              </div>

              {/* 14-Day Circulation Trends Visual Velocity */}
              {trends && (
                <div
                  style={{
                    background: 'var(--card-bg, #0E1626)',
                    border: '1px solid var(--card-border, rgba(148, 163, 184, 0.16))',
                    borderRadius: '14px',
                    padding: '1.5rem',
                    boxShadow: 'var(--card-shadow)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                    <div>
                      <h3 style={{ margin: 0, fontSize: '1.05rem', color: 'var(--text-primary, #F8FAFC)' }}>
                        14-Day Circulation Velocity
                      </h3>
                      <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.8rem', color: 'var(--text-secondary, #94A3B8)' }}>
                        Daily monograph checkout issues and returns velocity across the library network.
                      </p>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', fontSize: '0.8rem' }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--accent-cyan, #38BDF8)', fontWeight: 600 }}>
                        <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#38BDF8' }} />
                        Issues ({trends.total_issues})
                      </span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#34D399', fontWeight: 600 }}>
                        <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#34D399' }} />
                        Returns ({trends.total_returns})
                      </span>
                    </div>
                  </div>

                  {/* 14 Daily Velocity Cards */}
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(70px, 1fr))',
                      gap: '0.5rem',
                      paddingTop: '0.5rem',
                    }}
                  >
                    {trends.points.map((pt) => (
                      <div
                        key={pt.date}
                        style={{
                          background: 'var(--bg-tertiary, #141F36)',
                          border: '1px solid var(--border-subtle, rgba(148, 163, 184, 0.15))',
                          borderRadius: '8px',
                          padding: '0.65rem 0.35rem',
                          textAlign: 'center',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '0.35rem',
                          alignItems: 'center',
                        }}
                      >
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted, #64748B)', fontFamily: 'monospace' }}>
                          {pt.date.slice(5)}
                        </div>
                        <div style={{ width: '100%', display: 'flex', justifyContent: 'space-around', gap: '2px' }}>
                          <span
                            title="Issues"
                            style={{
                              fontSize: '0.75rem',
                              fontWeight: 700,
                              color: '#38BDF8',
                              background: 'rgba(56, 189, 248, 0.15)',
                              padding: '2px 5px',
                              borderRadius: '4px',
                            }}
                          >
                            {pt.issues}
                          </span>
                          <span
                            title="Returns"
                            style={{
                              fontSize: '0.75rem',
                              fontWeight: 700,
                              color: '#34D399',
                              background: 'rgba(52, 211, 153, 0.15)',
                              padding: '2px 5px',
                              borderRadius: '4px',
                            }}
                          >
                            {pt.returns}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 2: INVENTORY ANALYTICS */}
          {activeTab === 'inventory' && inventory && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
                  gap: '1.25rem',
                }}
              >
                <div
                  style={{
                    background: 'var(--card-bg, #0E1626)',
                    border: '1px solid var(--card-border, rgba(148, 163, 184, 0.16))',
                    borderRadius: '12px',
                    padding: '1.5rem',
                    boxShadow: 'var(--card-shadow)',
                  }}
                >
                  <span style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted, #64748B)' }}>
                    Collection Turnover
                  </span>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', margin: '0.5rem 0' }}>
                    <span style={{ fontSize: '2.5rem', fontWeight: 900, color: 'var(--brand-secondary, #38BDF8)' }}>
                      {inventory.collection_turnover_rate}x
                    </span>
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary, #94A3B8)' }}>
                      lifetime loan turnover
                    </span>
                  </div>
                  <p style={{ margin: 0, fontSize: '0.825rem', color: 'var(--text-secondary, #94A3B8)', lineHeight: 1.5 }}>
                    Evaluated across {inventory.total_monographs} monograph titles and {inventory.total_physical_copies} total physical items in collection.
                  </p>
                </div>

                <div
                  style={{
                    background: 'var(--card-bg, #0E1626)',
                    border: '1px solid var(--card-border, rgba(148, 163, 184, 0.16))',
                    borderRadius: '12px',
                    padding: '1.5rem',
                    boxShadow: 'var(--card-shadow)',
                  }}
                >
                  <span style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted, #64748B)' }}>
                    Demand Distribution
                  </span>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem', marginTop: '0.75rem', fontSize: '0.85rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle, rgba(148, 163, 184, 0.1))', paddingBottom: '0.4rem' }}>
                      <span style={{ color: 'var(--text-secondary, #94A3B8)' }}>High-Demand Titles:</span>
                      <strong style={{ color: '#FBBF24' }}>{inventory.high_demand_titles_count}</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle, rgba(148, 163, 184, 0.1))', paddingBottom: '0.4rem' }}>
                      <span style={{ color: 'var(--text-secondary, #94A3B8)' }}>Zero-Borrow Titles:</span>
                      <strong style={{ color: 'var(--text-primary, #F8FAFC)' }}>{inventory.zero_borrow_titles_count}</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--text-secondary, #94A3B8)' }}>Audit Events Recorded:</span>
                      <strong style={{ color: '#38BDF8' }}>{inventory.total_audit_events_count}</strong>
                    </div>
                  </div>
                </div>

                <div
                  style={{
                    background: 'var(--card-bg, #0E1626)',
                    border: '1px solid var(--card-border, rgba(148, 163, 184, 0.16))',
                    borderRadius: '12px',
                    padding: '1.5rem',
                    boxShadow: 'var(--card-shadow)',
                  }}
                >
                  <span style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted, #64748B)' }}>
                    Degradation & Loss Status
                  </span>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem', marginTop: '0.75rem', fontSize: '0.85rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle, rgba(148, 163, 184, 0.1))', paddingBottom: '0.4rem' }}>
                      <span style={{ color: 'var(--text-secondary, #94A3B8)' }}>Under Maintenance:</span>
                      <strong style={{ color: '#FBBF24' }}>{inventory.maintenance_copies}</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle, rgba(148, 163, 184, 0.1))', paddingBottom: '0.4rem' }}>
                      <span style={{ color: 'var(--text-secondary, #94A3B8)' }}>Damaged Flagged:</span>
                      <strong style={{ color: '#FB7185' }}>{inventory.damaged_copies}</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--text-secondary, #94A3B8)' }}>Lost Reported:</span>
                      <strong style={{ color: '#EF4444' }}>{inventory.lost_copies}</strong>
                    </div>
                  </div>
                </div>
              </div>

              {/* Physical Copy Operational Status Bar */}
              <div
                style={{
                  background: 'var(--card-bg, #0E1626)',
                  border: '1px solid var(--card-border, rgba(148, 163, 184, 0.16))',
                  borderRadius: '14px',
                  padding: '1.5rem',
                  boxShadow: 'var(--card-shadow)',
                }}
              >
                <h3 style={{ margin: '0 0 1rem 0', fontSize: '1rem', color: 'var(--text-primary, #F8FAFC)' }}>
                  Physical Copy Operational Fleet Distribution ({inventory.total_physical_copies} copies)
                </h3>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                    gap: '0.75rem',
                  }}
                >
                  {[
                    { label: 'Available (Shelf)', count: inventory.available_copies, color: '#34D399', bg: 'rgba(52, 211, 153, 0.12)' },
                    { label: 'On Loan', count: inventory.borrowed_copies, color: '#38BDF8', bg: 'rgba(56, 189, 248, 0.12)' },
                    { label: 'Maintenance', count: inventory.maintenance_copies, color: '#FBBF24', bg: 'rgba(251, 191, 36, 0.12)' },
                    { label: 'Damaged', count: inventory.damaged_copies, color: '#FB7185', bg: 'rgba(251, 113, 133, 0.12)' },
                    { label: 'Lost', count: inventory.lost_copies, color: '#EF4444', bg: 'rgba(239, 68, 68, 0.12)' },
                  ].map((stat) => (
                    <div
                      key={stat.label}
                      style={{
                        padding: '1rem',
                        background: 'var(--bg-tertiary, #141F36)',
                        border: `1px solid ${stat.color}40`,
                        borderRadius: '10px',
                        textAlign: 'center',
                      }}
                    >
                      <span style={{ fontSize: '0.75rem', fontWeight: 600, color: stat.color, display: 'block', marginBottom: '0.25rem' }}>
                        {stat.label}
                      </span>
                      <span style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-primary, #F8FAFC)' }}>
                        {stat.count}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: DEMAND FORECASTING */}
          {activeTab === 'forecast' && forecast && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              <div
                style={{
                  background: 'var(--card-bg, #0E1626)',
                  border: '1px solid var(--card-border, rgba(148, 163, 184, 0.16))',
                  borderRadius: '14px',
                  padding: '1.5rem',
                  boxShadow: 'var(--card-shadow)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.25rem' }}>
                  <div>
                    <h3 style={{ margin: 0, fontSize: '1.05rem', color: 'var(--text-primary, #F8FAFC)' }}>
                      14-Day Forward Checkout Demand Projection
                    </h3>
                    <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.8rem', color: 'var(--text-secondary, #94A3B8)' }}>
                      {forecast.methodology}
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: '0.75rem' }}>
                    <span
                      style={{
                        padding: '0.35rem 0.75rem',
                        borderRadius: '8px',
                        background: 'var(--bg-tertiary, #141F36)',
                        border: '1px solid var(--border-subtle, rgba(148, 163, 184, 0.2))',
                        fontSize: '0.8rem',
                        color: 'var(--text-secondary, #94A3B8)',
                      }}
                    >
                      Baseline: <strong style={{ color: '#38BDF8' }}>{forecast.baseline_daily_average}/day</strong>
                    </span>
                    <span
                      style={{
                        padding: '0.35rem 0.75rem',
                        borderRadius: '8px',
                        background: 'var(--bg-tertiary, #141F36)',
                        border: '1px solid var(--border-subtle, rgba(148, 163, 184, 0.2))',
                        fontSize: '0.8rem',
                        color: 'var(--text-secondary, #94A3B8)',
                      }}
                    >
                      Trend: <strong style={{ color: '#34D399', textTransform: 'uppercase' }}>{forecast.trend_direction}</strong>
                    </span>
                  </div>
                </div>

                {/* 14 Daily Forecast Cards */}
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(75px, 1fr))',
                    gap: '0.5rem',
                  }}
                >
                  {forecast.projections.map((p) => (
                    <div
                      key={p.date}
                      style={{
                        background: 'var(--bg-tertiary, #141F36)',
                        border: '1px solid var(--border-subtle, rgba(148, 163, 184, 0.15))',
                        borderRadius: '10px',
                        padding: '0.75rem 0.35rem',
                        textAlign: 'center',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '0.2rem',
                      }}
                    >
                      <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary, #94A3B8)' }}>
                        {p.day_of_week.slice(0, 3)}
                      </span>
                      <span style={{ fontSize: '0.7rem', color: 'var(--text-muted, #64748B)', fontFamily: 'monospace' }}>
                        {p.date.slice(5)}
                      </span>
                      <div style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--brand-secondary, #38BDF8)', margin: '0.25rem 0' }}>
                        {p.projected_checkouts}
                      </div>
                      <span style={{ fontSize: '0.68rem', color: 'var(--text-muted, #64748B)', fontFamily: 'monospace' }}>
                        [{p.lower_bound} - {p.upper_bound}]
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: ACQUISITIONS PIPELINE */}
          {activeTab === 'acquisitions' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: '1.05rem', color: 'var(--text-primary, #F8FAFC)' }}>
                    Zero-Result Search Demand Signals (INTEL-05)
                  </h3>
                  <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.8rem', color: 'var(--text-secondary, #94A3B8)' }}>
                    Unmet student search demand revealing holdings gaps and candidate procurement recommendations.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setShowAddModal(true)}
                  className="btn btn-primary"
                  style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.825rem', padding: '0.55rem 1rem' }}
                >
                  <span>+</span>
                  <span>Add Candidate Title</span>
                </button>
              </div>

              {/* Zero-Result Search Suggestions Table */}
              <div
                style={{
                  background: 'var(--card-bg, #0E1626)',
                  border: '1px solid var(--card-border, rgba(148, 163, 184, 0.16))',
                  borderRadius: '14px',
                  padding: '1.25rem',
                  boxShadow: 'var(--card-shadow)',
                }}
              >
                <h4 style={{ margin: '0 0 0.85rem 0', fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-muted, #64748B)', textTransform: 'uppercase' }}>
                  Patron Search Telemetry Signals
                </h4>
                {suggestions.length === 0 ? (
                  <p style={{ margin: 0, textAlign: 'center', padding: '1.5rem', color: 'var(--text-muted, #64748B)', fontSize: '0.85rem' }}>
                    No zero-result searches logged in the current telemetry window.
                  </p>
                ) : (
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
                      gap: '0.75rem',
                    }}
                  >
                    {suggestions.map((s, idx) => (
                      <div
                        key={idx}
                        style={{
                          background: 'var(--bg-tertiary, #141F36)',
                          border: '1px solid var(--border-subtle, rgba(148, 163, 184, 0.16))',
                          borderRadius: '10px',
                          padding: '0.85rem 1rem',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                        }}
                      >
                        <div>
                          <div style={{ fontWeight: 600, color: 'var(--text-primary, #F8FAFC)', fontSize: '0.875rem' }}>
                            "{s.query_text}"
                          </div>
                          <span style={{ fontSize: '0.72rem', color: 'var(--text-muted, #64748B)' }}>
                            Last queried: {new Date(s.last_searched).toLocaleDateString()}
                          </span>
                        </div>
                        <span
                          style={{
                            background: 'rgba(56, 189, 248, 0.15)',
                            color: 'var(--accent-cyan, #38BDF8)',
                            border: '1px solid rgba(56, 189, 248, 0.3)',
                            padding: '3px 8px',
                            borderRadius: '6px',
                            fontWeight: 700,
                            fontSize: '0.78rem',
                          }}
                        >
                          {s.frequency}x
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Acquisition Requests Review Triage Table */}
              <div
                style={{
                  background: 'var(--card-bg, #0E1626)',
                  border: '1px solid var(--card-border, rgba(148, 163, 184, 0.16))',
                  borderRadius: '14px',
                  padding: '1.25rem',
                  boxShadow: 'var(--card-shadow)',
                }}
              >
                <h4 style={{ margin: '0 0 0.85rem 0', fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-muted, #64748B)', textTransform: 'uppercase' }}>
                  Collection Development Triage
                </h4>
                {acquisitions.length === 0 ? (
                  <p style={{ margin: 0, textAlign: 'center', padding: '1.5rem', color: 'var(--text-muted, #64748B)', fontSize: '0.85rem' }}>
                    No acquisition requests pending review.
                  </p>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                    {acquisitions.map((item) => (
                      <div
                        key={item.id}
                        style={{
                          background: 'var(--bg-tertiary, #141F36)',
                          border: '1px solid var(--border-subtle, rgba(148, 163, 184, 0.16))',
                          borderRadius: '10px',
                          padding: '0.85rem 1.15rem',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          flexWrap: 'wrap',
                          gap: '0.75rem',
                        }}
                      >
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <span
                              style={{
                                fontSize: '0.7rem',
                                fontWeight: 700,
                                textTransform: 'uppercase',
                                padding: '2px 8px',
                                borderRadius: '4px',
                                background:
                                  item.status === 'approved'
                                    ? 'rgba(52, 211, 153, 0.15)'
                                    : item.status === 'ordered'
                                    ? 'rgba(56, 189, 248, 0.15)'
                                    : item.status === 'received'
                                    ? 'rgba(99, 102, 241, 0.15)'
                                    : item.status === 'rejected'
                                    ? 'rgba(239, 68, 68, 0.15)'
                                    : 'rgba(251, 191, 36, 0.15)',
                                color:
                                  item.status === 'approved'
                                    ? '#34D399'
                                    : item.status === 'ordered'
                                    ? '#38BDF8'
                                    : item.status === 'received'
                                    ? '#818CF8'
                                    : item.status === 'rejected'
                                    ? '#EF4444'
                                    : '#FBBF24',
                              }}
                            >
                              {item.status}
                            </span>
                            <strong style={{ fontSize: '0.95rem', color: 'var(--text-primary, #F8FAFC)' }}>
                              {item.suggested_title}
                            </strong>
                          </div>
                          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary, #94A3B8)', marginTop: '0.25rem' }}>
                            Author: {item.suggested_author || 'N/A'} {item.isbn && `• ISBN: ${item.isbn}`}
                          </div>
                        </div>

                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                          {item.status === 'suggested' && (
                            <>
                              <button
                                type="button"
                                onClick={() => handleUpdateAcquisitionStatus(item.id, 'approved')}
                                className="btn btn-sm"
                                style={{ background: '#059669', color: '#fff', border: 'none', padding: '0.35rem 0.75rem' }}
                              >
                                Approve
                              </button>
                              <button
                                type="button"
                                onClick={() => handleUpdateAcquisitionStatus(item.id, 'rejected')}
                                className="btn btn-sm"
                                style={{ background: '#DC2626', color: '#fff', border: 'none', padding: '0.35rem 0.75rem' }}
                              >
                                Reject
                              </button>
                            </>
                          )}
                          {item.status === 'approved' && (
                            <button
                              type="button"
                              onClick={() => handleUpdateAcquisitionStatus(item.id, 'ordered')}
                              className="btn btn-sm btn-primary"
                              style={{ padding: '0.35rem 0.75rem' }}
                            >
                              Mark Ordered
                            </button>
                          )}
                          {item.status === 'ordered' && (
                            <button
                              type="button"
                              onClick={() => handleUpdateAcquisitionStatus(item.id, 'received')}
                              className="btn btn-sm"
                              style={{ background: '#4F46E5', color: '#fff', border: 'none', padding: '0.35rem 0.75rem' }}
                            >
                              Mark Received
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Modal: Create Acquisition Candidate */}
      {showAddModal && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(8, 13, 26, 0.75)',
            backdropFilter: 'blur(4px)',
            zIndex: 9999,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1rem',
          }}
        >
          <div
            style={{
              background: 'var(--bg-surface, #0E1626)',
              border: '1px solid var(--border-medium, rgba(148, 163, 184, 0.25))',
              borderRadius: '14px',
              maxWidth: '460px',
              width: '100%',
              boxShadow: 'var(--shadow-modal)',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '1.25rem 1.5rem',
                borderBottom: '1px solid var(--border-subtle, rgba(148, 163, 184, 0.16))',
                background: 'var(--bg-subtle, #1C2B4A)',
              }}
            >
              <h3 style={{ margin: 0, fontSize: '1.1rem', color: 'var(--text-primary, #F8FAFC)' }}>
                Add Acquisition Candidate
              </h3>
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted, #94A3B8)', fontSize: '1.25rem', cursor: 'pointer' }}
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateAcquisitionRequest} style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary, #94A3B8)', marginBottom: '0.35rem' }}>
                  Book Title *
                </label>
                <input
                  type="text"
                  required
                  value={reqTitle}
                  onChange={(e) => setReqTitle(e.target.value)}
                  placeholder="e.g. Deep Reinforcement Learning in Practice"
                  style={{
                    width: '100%',
                    padding: '0.65rem 0.85rem',
                    borderRadius: '8px',
                    border: '1px solid var(--border-medium, rgba(148, 163, 184, 0.25))',
                    background: 'var(--bg-tertiary, #141F36)',
                    color: 'var(--text-primary, #F8FAFC)',
                    fontSize: '0.875rem',
                    outline: 'none',
                    boxSizing: 'border-box',
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary, #94A3B8)', marginBottom: '0.35rem' }}>
                  Author
                </label>
                <input
                  type="text"
                  value={reqAuthor}
                  onChange={(e) => setReqAuthor(e.target.value)}
                  placeholder="e.g. Richard S. Sutton"
                  style={{
                    width: '100%',
                    padding: '0.65rem 0.85rem',
                    borderRadius: '8px',
                    border: '1px solid var(--border-medium, rgba(148, 163, 184, 0.25))',
                    background: 'var(--bg-tertiary, #141F36)',
                    color: 'var(--text-primary, #F8FAFC)',
                    fontSize: '0.875rem',
                    outline: 'none',
                    boxSizing: 'border-box',
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary, #94A3B8)', marginBottom: '0.35rem' }}>
                  ISBN
                </label>
                <input
                  type="text"
                  value={reqIsbn}
                  onChange={(e) => setReqIsbn(e.target.value)}
                  placeholder="e.g. 9780262039246"
                  style={{
                    width: '100%',
                    padding: '0.65rem 0.85rem',
                    borderRadius: '8px',
                    border: '1px solid var(--border-medium, rgba(148, 163, 184, 0.25))',
                    background: 'var(--bg-tertiary, #141F36)',
                    color: 'var(--text-primary, #F8FAFC)',
                    fontSize: '0.875rem',
                    outline: 'none',
                    boxSizing: 'border-box',
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary, #94A3B8)', marginBottom: '0.35rem' }}>
                  Notes / Rationale
                </label>
                <input
                  type="text"
                  value={reqNotes}
                  onChange={(e) => setReqNotes(e.target.value)}
                  placeholder="e.g. Requested for CS-400 Machine Learning seminar"
                  style={{
                    width: '100%',
                    padding: '0.65rem 0.85rem',
                    borderRadius: '8px',
                    border: '1px solid var(--border-medium, rgba(148, 163, 184, 0.25))',
                    background: 'var(--bg-tertiary, #141F36)',
                    color: 'var(--text-primary, #F8FAFC)',
                    fontSize: '0.875rem',
                    outline: 'none',
                    boxSizing: 'border-box',
                  }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="btn btn-secondary"
                  style={{ padding: '0.6rem 1.15rem' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingReq}
                  className="btn btn-primary"
                  style={{ padding: '0.6rem 1.25rem' }}
                >
                  {submittingReq ? 'Submitting...' : 'Submit Request'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
export default LibrarianIntelligenceCenter;
