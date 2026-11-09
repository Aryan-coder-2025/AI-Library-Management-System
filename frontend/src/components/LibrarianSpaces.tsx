import React, { useEffect, useState, useCallback } from 'react';
import type {
  StudySpaceReservation,
  ReservationSweepReport,
  ReservationQRResponse,
} from '../types/library';
import {
  getAllReservations,
  checkInReservation,
  checkInByToken,
  cancelReservation,
  sweepReservations,
  getReservationQR,
} from '../services/spacesApi';
import { QRCodeModal } from './QRCodeModal';
import { OccupancyAnalytics } from './OccupancyAnalytics';
import { LibrarianFloorPlanManager } from './spatial/LibrarianFloorPlanManager';

export const LibrarianSpaces: React.FC = () => {
  const [deskSubTab, setDeskSubTab] = useState<'reservations' | 'spatial' | 'occupancy'>('reservations');
  const [reservations, setReservations] = useState<StudySpaceReservation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Filters & Pagination
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [resourceTypeFilter, setResourceTypeFilter] = useState<string>('all');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  // Token Scan Check-in State
  const [tokenInput, setTokenInput] = useState('');
  const [tokenAttendees, setTokenAttendees] = useState<number>(1);
  const [isTokenCheckingIn, setIsTokenCheckingIn] = useState(false);

  // Sweeper State
  const [isSweeping, setIsSweeping] = useState(false);
  const [sweepReport, setSweepReport] = useState<ReservationSweepReport | null>(null);

  // QR Modal State
  const [activeQRData, setActiveQRData] = useState<ReservationQRResponse | null>(null);

  const fetchReservations = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAllReservations(statusFilter, resourceTypeFilter, page, 15);
      setReservations(data.items);
      setTotalPages(data.total_pages || 1);
    } catch (err) {
      setError(err instanceof Error ? err.message.replace(/^\d+:\s*/, '') : 'Failed to fetch reservations.');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, resourceTypeFilter, page]);

  useEffect(() => {
    fetchReservations();
  }, [fetchReservations]);

  const handleStaffOverrideCheckIn = async (resId: number) => {
    setError(null);
    try {
      await checkInReservation(resId);
      setActionSuccess(`Staff override check-in confirmed for reservation #${resId}!`);
      fetchReservations();
      setTimeout(() => setActionSuccess(null), 4000);
    } catch (err) {
      setError(err instanceof Error ? err.message.replace(/^\d+:\s*/, '') : 'Check-in override failed.');
    }
  };

  const handleScanTokenSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tokenInput.trim()) return;

    setIsTokenCheckingIn(true);
    setError(null);
    try {
      const res = await checkInByToken(tokenInput.trim(), tokenAttendees > 1 ? tokenAttendees : undefined);
      setActionSuccess(`Token validated! Reservation #${res.id} (${res.resource_type.toUpperCase()}) successfully checked in.`);
      setTokenInput('');
      fetchReservations();
      setTimeout(() => setActionSuccess(null), 5000);
    } catch (err) {
      setError(err instanceof Error ? err.message.replace(/^\d+:\s*/, '') : 'Invalid or expired QR token.');
    } finally {
      setIsTokenCheckingIn(false);
    }
  };

  const handleTriggerSweep = async () => {
    setIsSweeping(true);
    setError(null);
    try {
      const report = await sweepReservations();
      setSweepReport(report);
      setActionSuccess(`Lifecycle sweep completed: ${report.no_show_count} marked no-show, ${report.completed_count} marked completed.`);
      fetchReservations();
    } catch (err) {
      setError(err instanceof Error ? err.message.replace(/^\d+:\s*/, '') : 'Sweep failed.');
    } finally {
      setIsSweeping(false);
    }
  };

  const handleViewQR = async (resId: number) => {
    setError(null);
    try {
      const qr = await getReservationQR(resId);
      setActiveQRData(qr);
    } catch (err) {
      setError(err instanceof Error ? err.message.replace(/^\d+:\s*/, '') : 'Failed to retrieve QR pass.');
    }
  };

  const handleStaffCancel = async (resId: number) => {
    if (!window.confirm(`Are you sure you want to cancel reservation #${resId}?`)) return;
    setError(null);
    try {
      await cancelReservation(resId);
      setActionSuccess(`Reservation #${resId} cancelled.`);
      fetchReservations();
      setTimeout(() => setActionSuccess(null), 4000);
    } catch (err) {
      setError(err instanceof Error ? err.message.replace(/^\d+:\s*/, '') : 'Cancellation failed.');
    }
  };

  const formatDateTime = (iso: string) => {
    try {
      const d = new Date(iso);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' ' + d.toLocaleDateString([], { month: 'short', day: 'numeric' });
    } catch {
      return iso;
    }
  };

  return (
    <div style={{ maxWidth: '1360px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1.5rem', paddingBottom: '3rem' }}>
      {/* Header */}
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
              Study Space Circulation Desk
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
              SPATIAL OPS
            </span>
          </div>
          <p style={{ margin: '0.4rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-secondary, #94A3B8)', maxWidth: '780px', lineHeight: 1.5 }}>
            Staff management for study seats, discussion rooms, QR verification, and automated lifecycle sweeps.
          </p>
        </div>

        {/* Sweep Trigger Button */}
        <button
          type="button"
          className="btn btn-secondary"
          onClick={handleTriggerSweep}
          disabled={isSweeping}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.6rem 1.15rem',
            fontSize: '0.825rem',
            fontWeight: 600,
          }}
        >
          <span>🧹</span>
          <span>{isSweeping ? 'Sweeping...' : 'Run Lifecycle Sweep'}</span>
        </button>
      </div>

      {/* Sub-Tab Navigation */}
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
          { key: 'reservations', label: '🪑 Study Space Reservations Desk' },
          { key: 'occupancy', label: '📊 Occupancy & Telemetry Analytics' },
          { key: 'spatial', label: '🗺️ Floor Plans & Spatial Manager' },
        ].map((tab) => {
          const isActive = deskSubTab === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => setDeskSubTab(tab.key as any)}
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

      {deskSubTab === 'spatial' ? (
        <LibrarianFloorPlanManager />
      ) : deskSubTab === 'occupancy' ? (
        <OccupancyAnalytics userRole="librarian" />
      ) : (
        <>
          {actionSuccess && (
            <div className="alert alert-success" style={{ margin: 0 }}>
              ✓ {actionSuccess}
            </div>
          )}
          {error && (
            <div className="alert alert-danger" style={{ margin: 0 }}>
              ✕ {error}
            </div>
          )}

          {/* Sweep Report Box */}
          {sweepReport && (
            <div
              style={{
                background: 'var(--card-bg, #0E1626)',
                border: '1px solid var(--border-medium, rgba(148, 163, 184, 0.25))',
                borderRadius: '12px',
                padding: '1.25rem 1.5rem',
                boxShadow: 'var(--card-shadow)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-primary, #F8FAFC)' }}>
                  🧹 Last Sweep Execution Report
                </h4>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted, #64748B)', fontFamily: 'monospace' }}>
                  {sweepReport.timestamp}
                </span>
              </div>
              <div style={{ display: 'flex', gap: '2rem', fontSize: '0.85rem', flexWrap: 'wrap' }}>
                <div>
                  <span style={{ color: 'var(--text-secondary, #94A3B8)' }}>Processed: </span>
                  <strong style={{ color: 'var(--text-primary, #F8FAFC)' }}>{sweepReport.processed_count}</strong>
                </div>
                <div>
                  <span style={{ color: 'var(--text-secondary, #94A3B8)' }}>Marked No-Show: </span>
                  <strong style={{ color: '#FB7185' }}>{sweepReport.no_show_count}</strong>
                </div>
                <div>
                  <span style={{ color: 'var(--text-secondary, #94A3B8)' }}>Marked Completed: </span>
                  <strong style={{ color: '#34D399' }}>{sweepReport.completed_count}</strong>
                </div>
              </div>
            </div>
          )}

          {/* Quick QR Scanner Form */}
          <div
            style={{
              background: 'var(--card-bg, #0E1626)',
              border: '1px solid var(--card-border, rgba(148, 163, 184, 0.16))',
              borderRadius: '14px',
              padding: '1.5rem',
              boxShadow: 'var(--card-shadow)',
            }}
          >
            <h3 style={{ margin: '0 0 1rem 0', fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary, #F8FAFC)' }}>
              🎟️ Kiosk / Desk Check-In by Token
            </h3>
            <form onSubmit={handleScanTokenSubmit} style={{ display: 'flex', gap: '0.85rem', flexWrap: 'wrap', alignItems: 'flex-end' }}>
              <div style={{ flex: 3, minWidth: '260px' }}>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary, #94A3B8)', marginBottom: '0.35rem' }}>
                  Scanned / Pasted Token:
                </label>
                <input
                  type="text"
                  placeholder="Paste or scan QR check-in token here..."
                  value={tokenInput}
                  onChange={(e) => setTokenInput(e.target.value)}
                  required
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

              <div style={{ width: '130px' }}>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary, #94A3B8)', marginBottom: '0.35rem' }}>
                  Attendees:
                </label>
                <input
                  type="number"
                  min={1}
                  max={12}
                  value={tokenAttendees}
                  onChange={(e) => setTokenAttendees(Number(e.target.value))}
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

              <button
                type="submit"
                className="btn btn-primary"
                disabled={isTokenCheckingIn || !tokenInput.trim()}
                style={{
                  padding: '0.65rem 1.35rem',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  cursor: isTokenCheckingIn || !tokenInput.trim() ? 'not-allowed' : 'pointer',
                }}
              >
                {isTokenCheckingIn ? 'Validating...' : 'Validate & Check In'}
              </button>
            </form>
          </div>

          {/* Reservation Management Table */}
          <div
            style={{
              background: 'var(--card-bg, #0E1626)',
              border: '1px solid var(--card-border, rgba(148, 163, 184, 0.16))',
              borderRadius: '14px',
              padding: '1.5rem',
              boxShadow: 'var(--card-shadow)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.75rem' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary, #F8FAFC)' }}>
                  All Study Space Reservations
                </h3>
                <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.78rem', color: 'var(--text-muted, #64748B)' }}>
                  Real-time patron reservations across seats and study rooms.
                </p>
              </div>

              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                {/* Status Filter */}
                <select
                  style={{
                    padding: '0.45rem 0.85rem',
                    borderRadius: '8px',
                    border: '1px solid var(--border-medium, rgba(148, 163, 184, 0.25))',
                    background: 'var(--bg-tertiary, #141F36)',
                    color: 'var(--text-primary, #F8FAFC)',
                    fontSize: '0.825rem',
                    outline: 'none',
                    cursor: 'pointer',
                  }}
                  value={statusFilter}
                  onChange={(e) => {
                    setStatusFilter(e.target.value);
                    setPage(1);
                  }}
                >
                  <option value="all">All Statuses</option>
                  <option value="active">Active</option>
                  <option value="completed">Completed</option>
                  <option value="cancelled">Cancelled</option>
                  <option value="no_show">No-Show</option>
                </select>

                {/* Resource Type Filter */}
                <select
                  style={{
                    padding: '0.45rem 0.85rem',
                    borderRadius: '8px',
                    border: '1px solid var(--border-medium, rgba(148, 163, 184, 0.25))',
                    background: 'var(--bg-tertiary, #141F36)',
                    color: 'var(--text-primary, #F8FAFC)',
                    fontSize: '0.825rem',
                    outline: 'none',
                    cursor: 'pointer',
                  }}
                  value={resourceTypeFilter}
                  onChange={(e) => {
                    setResourceTypeFilter(e.target.value);
                    setPage(1);
                  }}
                >
                  <option value="all">All Resources</option>
                  <option value="seat">Seats Only</option>
                  <option value="room">Rooms Only</option>
                </select>
              </div>
            </div>

            {loading && reservations.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '3rem 1rem', color: 'var(--text-muted, #64748B)' }}>
                Loading reservation records...
              </div>
            ) : reservations.length === 0 ? (
              <div
                style={{
                  textAlign: 'center',
                  padding: '3rem 1rem',
                  background: 'var(--bg-tertiary, #141F36)',
                  borderRadius: '10px',
                  border: '1px solid var(--border-subtle, rgba(148, 163, 184, 0.12))',
                  color: 'var(--text-secondary, #94A3B8)',
                }}
              >
                No reservations found matching the selected filter criteria.
              </div>
            ) : (
              <div style={{ overflowX: 'auto', borderRadius: '10px', border: '1px solid var(--border-subtle, rgba(148, 163, 184, 0.16))' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                  <thead>
                    <tr style={{ background: 'var(--bg-subtle, #1C2B4A)', borderBottom: '1px solid var(--border-medium, rgba(148, 163, 184, 0.2))' }}>
                      <th style={{ padding: '0.75rem 1rem', textAlign: 'left', fontWeight: 700, color: 'var(--text-muted, #64748B)', textTransform: 'uppercase', fontSize: '0.72rem', letterSpacing: '0.05em' }}>ID</th>
                      <th style={{ padding: '0.75rem 1rem', textAlign: 'left', fontWeight: 700, color: 'var(--text-muted, #64748B)', textTransform: 'uppercase', fontSize: '0.72rem', letterSpacing: '0.05em' }}>Patron</th>
                      <th style={{ padding: '0.75rem 1rem', textAlign: 'left', fontWeight: 700, color: 'var(--text-muted, #64748B)', textTransform: 'uppercase', fontSize: '0.72rem', letterSpacing: '0.05em' }}>Resource</th>
                      <th style={{ padding: '0.75rem 1rem', textAlign: 'left', fontWeight: 700, color: 'var(--text-muted, #64748B)', textTransform: 'uppercase', fontSize: '0.72rem', letterSpacing: '0.05em' }}>Time Window</th>
                      <th style={{ padding: '0.75rem 1rem', textAlign: 'left', fontWeight: 700, color: 'var(--text-muted, #64748B)', textTransform: 'uppercase', fontSize: '0.72rem', letterSpacing: '0.05em' }}>Status</th>
                      <th style={{ padding: '0.75rem 1rem', textAlign: 'left', fontWeight: 700, color: 'var(--text-muted, #64748B)', textTransform: 'uppercase', fontSize: '0.72rem', letterSpacing: '0.05em' }}>Checked In</th>
                      <th style={{ padding: '0.75rem 1rem', textAlign: 'right', fontWeight: 700, color: 'var(--text-muted, #64748B)', textTransform: 'uppercase', fontSize: '0.72rem', letterSpacing: '0.05em' }}>Staff Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reservations.map((r) => {
                      const canOverrideCheckIn = r.status === 'active' && !r.checked_in_at;
                      const canCancel = r.status === 'active';

                      const patronDisplayName = r.patron_name || `Patron #${r.user_id}`;
                      const patronDisplaySub = r.patron_email || `User ID: ${r.user_id}`;

                      return (
                        <tr
                          key={r.id}
                          style={{
                            borderBottom: '1px solid var(--border-subtle, rgba(148, 163, 184, 0.12))',
                            transition: 'background 0.15s ease',
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.background = 'rgba(56, 189, 248, 0.04)';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.background = 'transparent';
                          }}
                        >
                          <td style={{ padding: '0.85rem 1rem', fontFamily: 'monospace', color: 'var(--accent-cyan, #38BDF8)', fontWeight: 700 }}>
                            #{r.id}
                          </td>
                          <td style={{ padding: '0.85rem 1rem' }}>
                            <div style={{ fontWeight: 600, color: 'var(--text-primary, #F8FAFC)' }}>
                              {patronDisplayName}
                            </div>
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted, #64748B)' }}>
                              {patronDisplaySub}
                            </div>
                          </td>
                          <td style={{ padding: '0.85rem 1rem' }}>
                            <span
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '0.35rem',
                                padding: '2px 8px',
                                borderRadius: '6px',
                                fontSize: '0.78rem',
                                fontWeight: 600,
                                background: r.resource_type === 'room' ? 'rgba(129, 140, 248, 0.14)' : 'rgba(56, 189, 248, 0.12)',
                                color: r.resource_type === 'room' ? '#818CF8' : 'var(--brand-secondary, #38BDF8)',
                                border: `1px solid ${r.resource_type === 'room' ? 'rgba(129, 140, 248, 0.3)' : 'rgba(56, 189, 248, 0.25)'}`,
                              }}
                            >
                              {r.resource_type === 'room' ? '🚪' : '🪑'}
                              {r.resource_type === 'seat'
                                ? r.seat?.seat_code ? `Seat ${r.seat.seat_code}` : `Seat #${r.seat_id}`
                                : r.room?.name ? `Room ${r.room.name}` : `Room #${r.room_id}`}
                            </span>
                          </td>
                          <td style={{ padding: '0.85rem 1rem', color: 'var(--text-secondary, #94A3B8)', fontSize: '0.8rem', whiteSpace: 'nowrap' }}>
                            {formatDateTime(r.start_time)} – {formatDateTime(r.end_time)}
                          </td>
                          <td style={{ padding: '0.85rem 1rem' }}>
                            {r.status === 'active' && !r.checked_in_at && (
                              <span style={{ fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', padding: '3px 8px', borderRadius: '4px', background: 'rgba(56, 189, 248, 0.15)', color: '#38BDF8', border: '1px solid rgba(56, 189, 248, 0.3)' }}>
                                Active (Pending)
                              </span>
                            )}
                            {r.status === 'active' && r.checked_in_at && (
                              <span style={{ fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', padding: '3px 8px', borderRadius: '4px', background: 'rgba(52, 211, 153, 0.15)', color: '#34D399', border: '1px solid rgba(52, 211, 153, 0.3)' }}>
                                Checked In
                              </span>
                            )}
                            {r.status === 'completed' && (
                              <span style={{ fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', padding: '3px 8px', borderRadius: '4px', background: 'rgba(129, 140, 248, 0.15)', color: '#818CF8', border: '1px solid rgba(129, 140, 248, 0.3)' }}>
                                Completed
                              </span>
                            )}
                            {r.status === 'cancelled' && (
                              <span style={{ fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', padding: '3px 8px', borderRadius: '4px', background: 'rgba(100, 116, 139, 0.18)', color: '#94A3B8', border: '1px solid rgba(100, 116, 139, 0.3)' }}>
                                Cancelled
                              </span>
                            )}
                            {r.status === 'no_show' && (
                              <span style={{ fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', padding: '3px 8px', borderRadius: '4px', background: 'rgba(239, 68, 68, 0.15)', color: '#EF4444', border: '1px solid rgba(239, 68, 68, 0.3)' }}>
                                No-Show
                              </span>
                            )}
                          </td>
                          <td style={{ padding: '0.85rem 1rem', color: 'var(--text-secondary, #94A3B8)', fontSize: '0.8rem' }}>
                            {r.checked_in_at ? formatDateTime(r.checked_in_at) : '—'}
                          </td>
                          <td style={{ padding: '0.85rem 1rem', textAlign: 'right' }}>
                            <div style={{ display: 'inline-flex', gap: '0.35rem' }}>
                              {canOverrideCheckIn && (
                                <button
                                  type="button"
                                  className="btn btn-primary btn-sm"
                                  onClick={() => handleStaffOverrideCheckIn(r.id)}
                                  style={{ padding: '0.3rem 0.65rem', fontSize: '0.75rem' }}
                                  title="Override check-in within reservation duration"
                                >
                                  Check In
                                </button>
                              )}
                              {r.status === 'active' && (
                                <button
                                  type="button"
                                  className="btn btn-secondary btn-sm"
                                  onClick={() => handleViewQR(r.id)}
                                  style={{ padding: '0.3rem 0.65rem', fontSize: '0.75rem' }}
                                >
                                  QR Pass
                                </button>
                              )}
                              {canCancel && (
                                <button
                                  type="button"
                                  className="btn btn-danger btn-sm"
                                  onClick={() => handleStaffCancel(r.id)}
                                  style={{ padding: '0.3rem 0.65rem', fontSize: '0.75rem', background: '#DC2626', color: '#fff', border: 'none' }}
                                >
                                  Cancel
                                </button>
                              )}
                              {!canOverrideCheckIn && r.status !== 'active' && (
                                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted, #64748B)' }}>
                                  Archived
                                </span>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <div style={{ display: 'flex', justifyContent: 'center', gap: '0.5rem', marginTop: '1.25rem' }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => setPage((p) => Math.max(p - 1, 1))}
                  disabled={page <= 1 || loading}
                >
                  ← Previous
                </button>
                <span style={{ display: 'flex', alignItems: 'center', fontSize: '0.85rem', color: 'var(--text-secondary, #94A3B8)' }}>
                  Page {page} of {totalPages}
                </span>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
                  disabled={page >= totalPages || loading}
                >
                  Next →
                </button>
              </div>
            )}
          </div>
        </>
      )}

      {/* QR Modal */}
      {activeQRData && (
        <QRCodeModal
          qrData={activeQRData}
          onClose={() => setActiveQRData(null)}
        />
      )}
    </div>
  );
};
export default LibrarianSpaces;
