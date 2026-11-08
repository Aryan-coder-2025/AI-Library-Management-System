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
    <div className="container" style={{ padding: '1.5rem 0' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.6rem', fontWeight: 700 }}>Study Space Circulation Desk</h2>
          <p style={{ margin: '0.25rem 0 0', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Staff management for study seats, discussion rooms, QR verification, and automated lifecycle sweeps.
          </p>
        </div>

        {/* Sweep Trigger Button */}
        <button
          type="button"
          className="btn btn-secondary"
          onClick={handleTriggerSweep}
          disabled={isSweeping}
          style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
        >
          {isSweeping ? 'Sweeping...' : '🧹 Run Lifecycle Sweep'}
        </button>
      </div>

      {/* Sub-Tab Navigation */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.25rem', borderBottom: '1px solid #e2e8f0', paddingBottom: '0.5rem', flexWrap: 'wrap' }}>
        <button
          type="button"
          className={`btn ${deskSubTab === 'reservations' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setDeskSubTab('reservations')}
        >
          Study Space Reservations Desk
        </button>
        <button
          type="button"
          className={`btn ${deskSubTab === 'occupancy' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setDeskSubTab('occupancy')}
        >
          📊 Occupancy & Telemetry Analytics
        </button>
        <button
          type="button"
          className={`btn ${deskSubTab === 'spatial' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setDeskSubTab('spatial')}
        >
          🗺️ Floor Plans & Spatial Manager
        </button>
      </div>

      {deskSubTab === 'spatial' ? (
        <LibrarianFloorPlanManager />
      ) : deskSubTab === 'occupancy' ? (
        <OccupancyAnalytics userRole="librarian" />
      ) : (
        <>
          {actionSuccess && (
            <div className="alert alert-success" style={{ marginBottom: '1rem' }}>
              ✓ {actionSuccess}
            </div>
          )}
          {error && (
            <div className="alert alert-danger" style={{ marginBottom: '1rem' }}>
              ✕ {error}
            </div>
          )}

      {/* Sweep Report Box */}
      {sweepReport && (
        <div className="card" style={{ padding: '1rem 1.25rem', marginBottom: '1.5rem', background: '#f8fafc', border: '1px solid #e2e8f0' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Last Sweep Execution Report</h4>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{sweepReport.timestamp}</span>
          </div>
          <div style={{ display: 'flex', gap: '2rem', marginTop: '0.5rem', fontSize: '0.875rem' }}>
            <div><strong>Processed:</strong> {sweepReport.processed_count}</div>
            <div style={{ color: 'var(--danger-color)' }}><strong>Marked No-Show:</strong> {sweepReport.no_show_count}</div>
            <div style={{ color: 'var(--success-color)' }}><strong>Marked Completed:</strong> {sweepReport.completed_count}</div>
          </div>
        </div>
      )}

      {/* Quick QR Scanner Form */}
      <div className="card" style={{ padding: '1.25rem', marginBottom: '1.5rem' }}>
        <h3 style={{ margin: '0 0 0.75rem', fontSize: '1.1rem', fontWeight: 600 }}>Kiosk / Desk Check-In by Token</h3>
        <form onSubmit={handleScanTokenSubmit} style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div style={{ flex: 3, minWidth: '240px' }}>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.25rem' }}>
              Scanned / Pasted Token:
            </label>
            <input
              type="text"
              className="form-control"
              placeholder="Paste or scan QR check-in token here..."
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
              required
            />
          </div>
          <div style={{ width: '130px' }}>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.25rem' }}>
              Attendees:
            </label>
            <input
              type="number"
              className="form-control"
              min={1}
              max={12}
              value={tokenAttendees}
              onChange={(e) => setTokenAttendees(Number(e.target.value))}
            />
          </div>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={isTokenCheckingIn || !tokenInput.trim()}
          >
            {isTokenCheckingIn ? 'Validating...' : 'Validate & Check In'}
          </button>
        </form>
      </div>

      {/* Reservation Management Table */}
      <div className="card" style={{ padding: '1.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
          <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 600 }}>All Reservations</h3>

          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            {/* Status Filter */}
            <select
              className="form-control"
              style={{ width: 'auto', fontSize: '0.85rem' }}
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
              className="form-control"
              style={{ width: 'auto', fontSize: '0.85rem' }}
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

        {loading ? (
          <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>Loading records...</div>
        ) : reservations.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>No reservations found.</div>
        ) : (
          <div className="table-responsive">
            <table className="table" style={{ width: '100%', fontSize: '0.875rem' }}>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Patron</th>
                  <th>Resource</th>
                  <th>Time Window</th>
                  <th>Status</th>
                  <th>Checked In</th>
                  <th>Staff Actions</th>
                </tr>
              </thead>
              <tbody>
                {reservations.map((r) => {
                  const canOverrideCheckIn = r.status === 'active' && !r.checked_in_at;
                  const canCancel = r.status === 'active';

                  return (
                    <tr key={r.id}>
                      <td>#{r.id}</td>
                      <td>
                        <strong>{r.user_id}</strong>
                      </td>
                      <td>
                        {r.resource_type === 'seat'
                          ? r.seat?.seat_code ? `Seat ${r.seat.seat_code}` : `Seat #${r.seat_id}`
                          : r.room?.name ? `Room ${r.room.name}` : `Room #${r.room_id}`}
                      </td>
                      <td>
                        {formatDateTime(r.start_time)} – {formatDateTime(r.end_time)}
                      </td>
                      <td>
                        {r.status === 'active' && !r.checked_in_at && <span className="badge badge-primary">Active</span>}
                        {r.status === 'active' && r.checked_in_at && <span className="badge badge-success">Checked In</span>}
                        {r.status === 'completed' && <span className="badge badge-secondary">Completed</span>}
                        {r.status === 'cancelled' && <span className="badge" style={{ background: '#94a3b8', color: '#fff' }}>Cancelled</span>}
                        {r.status === 'no_show' && <span className="badge badge-danger">No-Show</span>}
                      </td>
                      <td>
                        {r.checked_in_at ? formatDateTime(r.checked_in_at) : '—'}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: '0.35rem' }}>
                          {canOverrideCheckIn && (
                            <button
                              type="button"
                              className="btn btn-primary btn-sm"
                              onClick={() => handleStaffOverrideCheckIn(r.id)}
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
                            >
                              QR
                            </button>
                          )}
                          {canCancel && (
                            <button
                              type="button"
                              className="btn btn-danger btn-sm"
                              onClick={() => handleStaffCancel(r.id)}
                            >
                              Cancel
                            </button>
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
              disabled={page <= 1}
            >
              Previous
            </button>
            <span style={{ display: 'flex', alignItems: 'center', fontSize: '0.85rem' }}>
              Page {page} of {totalPages}
            </span>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
              disabled={page >= totalPages}
            >
              Next
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

