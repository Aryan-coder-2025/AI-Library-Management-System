import React, { useEffect, useState, useCallback } from 'react';
import type {
  UserProfile,
  StudySpaceReservation,
  StudyZone,
  StudySeat,
  StudyRoom,
  ReservationQRResponse,
} from '../types/library';
import {
  getMyReservations,
  getReservationQR,
  checkInReservation,
  cancelReservation,
  querySpaceAvailability,
  getStudyZones,
  createReservation,
} from '../services/spacesApi';
import { QRCodeModal } from './QRCodeModal';
import { OccupancyAnalytics } from './OccupancyAnalytics';
import { StudentFloorPlan } from './spatial/StudentFloorPlan';

interface StudentSpacesProps {
  currentUser: UserProfile;
}

export const StudentSpaces: React.FC<StudentSpacesProps> = ({ currentUser }) => {
  const [activeSubTab, setActiveSubTab] = useState<'my_reservations' | 'book_space' | 'floor_plans' | 'occupancy'>('my_reservations');

  // Reservations list state
  const [reservations, setReservations] = useState<StudySpaceReservation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // QR Modal state
  const [activeQRData, setActiveQRData] = useState<ReservationQRResponse | null>(null);
  const [qrLoadingId, setQrLoadingId] = useState<number | null>(null);

  // Room Check-in Attendee Modal state
  const [roomCheckInTarget, setRoomCheckInTarget] = useState<StudySpaceReservation | null>(null);
  const [actualAttendeesInput, setActualAttendeesInput] = useState<number>(1);
  const [isCheckingIn, setIsCheckingIn] = useState(false);

  // Space Booking Form state
  const [zones, setZones] = useState<StudyZone[]>([]);
  const [bookingDate, setBookingDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    return d.toISOString().split('T')[0];
  });
  const [bookingStartTime, setBookingStartTime] = useState('10:00');
  const [bookingEndTime, setBookingEndTime] = useState('12:00');
  const [resourceTypeFilter, setResourceTypeFilter] = useState<'seat' | 'room'>('seat');
  const [selectedZoneId, setSelectedZoneId] = useState<number | ''>('');
  const [expectedAttendees, setExpectedAttendees] = useState(1);

  // Availability query state
  const [isSearchingAvailability, setIsSearchingAvailability] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [availableSeats, setAvailableSeats] = useState<StudySeat[]>([]);
  const [availableRooms, setAvailableRooms] = useState<StudyRoom[]>([]);
  const [bookingSubmittingId, setBookingSubmittingId] = useState<string | null>(null);

  const fetchReservations = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getMyReservations(statusFilter, page, 10);
      setReservations(data.items);
      setTotalPages(data.total_pages || 1);
    } catch (err) {
      setError(err instanceof Error ? err.message.replace(/^\d+:\s*/, '') : 'Failed to load reservations.');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, page]);

  useEffect(() => {
    if (activeSubTab === 'my_reservations') {
      fetchReservations();
    }
  }, [activeSubTab, fetchReservations]);

  useEffect(() => {
    getStudyZones().then(setZones).catch(() => { });
  }, []);

  const handleShowQR = async (resId: number) => {
    setQrLoadingId(resId);
    setError(null);
    try {
      const qrData = await getReservationQR(resId);
      setActiveQRData(qrData);
    } catch (err) {
      setError(err instanceof Error ? err.message.replace(/^\d+:\s*/, '') : 'Failed to retrieve QR pass.');
    } finally {
      setQrLoadingId(null);
    }
  };

  const handleExecuteCheckIn = async (res: StudySpaceReservation, attendees?: number) => {
    setIsCheckingIn(true);
    setError(null);
    try {
      const updated = await checkInReservation(res.id, attendees);
      setActionSuccess(`Check-in successful for reservation #${updated.id}!`);
      setRoomCheckInTarget(null);
      fetchReservations();
      setTimeout(() => setActionSuccess(null), 4000);
    } catch (err) {
      setError(err instanceof Error ? err.message.replace(/^\d+:\s*/, '') : 'Check-in failed.');
    } finally {
      setIsCheckingIn(false);
    }
  };

  const handleCheckInClick = (res: StudySpaceReservation) => {
    if (res.resource_type === 'room') {
      setActualAttendeesInput(res.expected_attendees || 2);
      setRoomCheckInTarget(res);
    } else {
      handleExecuteCheckIn(res, 1);
    }
  };

  const handleCancel = async (resId: number) => {
    if (!window.confirm('Are you sure you want to cancel this reservation?')) return;
    setError(null);
    try {
      await cancelReservation(resId);
      setActionSuccess('Reservation cancelled successfully.');
      fetchReservations();
      setTimeout(() => setActionSuccess(null), 4000);
    } catch (err) {
      setError(err instanceof Error ? err.message.replace(/^\d+:\s*/, '') : 'Cancellation failed.');
    }
  };

  const handleSearchAvailability = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSearchingAvailability(true);
    setHasSearched(true);

    try {
      // Build ISO UTC strings from date and time
      const startIso = `${bookingDate}T${bookingStartTime}:00Z`;
      const endIso = `${bookingDate}T${bookingEndTime}:00Z`;

      const zoneParam = selectedZoneId ? Number(selectedZoneId) : undefined;
      const res = await querySpaceAvailability(startIso, endIso, resourceTypeFilter, zoneParam);
      setAvailableSeats(res.available_seats || []);
      setAvailableRooms(res.available_rooms || []);
    } catch (err) {
      setError(err instanceof Error ? err.message.replace(/^\d+:\s*/, '') : 'Failed to query space availability.');
    } finally {
      setIsSearchingAvailability(false);
    }
  };

  const handleBookResource = async (resourceId: number, type: 'seat' | 'room') => {
    setError(null);
    const key = `${type}-${resourceId}`;
    setBookingSubmittingId(key);

    try {
      const startIso = `${bookingDate}T${bookingStartTime}:00Z`;
      const endIso = `${bookingDate}T${bookingEndTime}:00Z`;

      const payload = {
        resource_type: type,
        seat_id: type === 'seat' ? resourceId : null,
        room_id: type === 'room' ? resourceId : null,
        start_time: startIso,
        end_time: endIso,
        expected_attendees: type === 'seat' ? 1 : expectedAttendees,
      };

      const created = await createReservation(payload);
      setActionSuccess(`Successfully reserved ${type.toUpperCase()} #${resourceId}! Reservation ID: ${created.id}`);
      setActiveSubTab('my_reservations');
      fetchReservations();
      setTimeout(() => setActionSuccess(null), 5000);
    } catch (err) {
      setError(err instanceof Error ? err.message.replace(/^\d+:\s*/, '') : 'Failed to book space.');
    } finally {
      setBookingSubmittingId(null);
    }
  };

  const formatDateTime = (iso: string) => {
    try {
      const d = new Date(iso);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ', ' + d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return iso;
    }
  };

  const getStatusBadge = (res: StudySpaceReservation) => {
    if (res.status === 'completed') return <span className="badge badge-secondary">Completed</span>;
    if (res.status === 'cancelled') return <span className="badge" style={{ background: '#94a3b8', color: '#fff' }}>Cancelled</span>;
    if (res.status === 'no_show') return <span className="badge badge-danger">No-Show</span>;
    if (res.checked_in_at) return <span className="badge badge-success">Checked In</span>;
    return <span className="badge badge-primary">Active (Upcoming)</span>;
  };

  return (
    <div className="container" style={{ padding: '1.5rem 0' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.6rem', fontWeight: 700 }}>Study Spaces & Room Reservations</h2>
          <p style={{ margin: '0.25rem 0 0', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            {currentUser.role === 'teacher' ? 'Faculty quota: 2 active reservations up to 14 days in advance.' : 'Student quota: 1 active reservation up to 7 days in advance.'}
          </p>
        </div>

        {/* View Switcher */}
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            className={`btn ${activeSubTab === 'my_reservations' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveSubTab('my_reservations')}
          >
            My Reservations
          </button>
          <button
            type="button"
            className={`btn ${activeSubTab === 'book_space' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveSubTab('book_space')}
          >
            + Reserve Space
          </button>
          <button
            type="button"
            className={`btn ${activeSubTab === 'floor_plans' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveSubTab('floor_plans')}
          >
            🗺️ Interactive Floor Plan
          </button>
          <button
            type="button"
            className={`btn ${activeSubTab === 'occupancy' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveSubTab('occupancy')}
          >
            📊 Occupancy & Live Capacity
          </button>
        </div>
      </div>

      {/* Notifications */}
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

      {/* SUBTAB 1: My Reservations */}
      {activeSubTab === 'my_reservations' && (
        <div>
          {/* Filter Bar */}
          <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.25rem', alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-muted)' }}>Status:</span>
            {['all', 'active', 'completed', 'cancelled', 'no_show'].map((st) => (
              <button
                key={st}
                type="button"
                className={`btn btn-sm ${statusFilter === st ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => {
                  setStatusFilter(st);
                  setPage(1);
                }}
              >
                {st.replace('_', '-').toUpperCase()}
              </button>
            ))}
          </div>

          {loading && reservations.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
              Loading study space reservations...
            </div>
          ) : reservations.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '3.5rem 1rem', background: 'var(--card-bg)', borderRadius: '12px', border: '1px dashed var(--border-color)' }}>
              <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>🏛️</div>
              <h3 style={{ margin: '0 0 0.5rem', fontWeight: 600 }}>No reservations found</h3>
              <p style={{ color: 'var(--text-muted)', marginBottom: '1.5rem', fontSize: '0.9rem' }}>
                You have no {statusFilter !== 'all' ? statusFilter : ''} study space reservations.
              </p>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => setActiveSubTab('book_space')}
              >
                Book a Study Seat or Room Now
              </button>
            </div>
          ) : (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
                gap: '1.25rem',
              }}
            >
              {reservations.map((res) => {
                const canCheckIn = res.status === 'active' && !res.checked_in_at;
                const canViewQR = res.status === 'active';
                const canCancel = res.status === 'active' && !res.checked_in_at;

                return (
                  <div
                    key={res.id}
                    className="card"
                    style={{
                      padding: '1.25rem',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      borderLeft: res.status === 'active' ? '4px solid var(--primary-color)' : undefined,
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
                        <div>
                          <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
                            {res.resource_type === 'seat' ? '💺 Individual Seat' : '🚪 Discussion Room'}
                          </span>
                          <h4 style={{ margin: '0.2rem 0 0', fontSize: '1.1rem', fontWeight: 600 }}>
                            {res.resource_type === 'seat'
                              ? res.seat?.seat_code ? `Seat ${res.seat.seat_code}` : `Seat #${res.seat_id}`
                              : res.room?.name ? `Room ${res.room.name}` : `Room #${res.room_id}`}
                          </h4>
                        </div>
                        {getStatusBadge(res)}
                      </div>

                      <div style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                        <div>📅 {formatDateTime(res.start_time)}</div>
                        <div style={{ marginLeft: '1.25rem' }}>to {formatDateTime(res.end_time)}</div>
                      </div>

                      <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
                        {res.resource_type === 'room' && (
                          <div>👥 Expected attendees: {res.expected_attendees} {res.actual_attendees ? `(Actual: ${res.actual_attendees})` : ''}</div>
                        )}
                        {res.checked_in_at && (
                          <div style={{ color: 'var(--success-color)', fontWeight: 500 }}>
                            ✓ Checked in: {formatDateTime(res.checked_in_at)}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Actions */}
                    <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', borderTop: '1px solid var(--border-color)', paddingTop: '0.75rem' }}>
                      {canViewQR && (
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          style={{ flex: 1 }}
                          onClick={() => handleShowQR(res.id)}
                          disabled={qrLoadingId === res.id}
                        >
                          {qrLoadingId === res.id ? 'Loading...' : '📱 QR Pass'}
                        </button>
                      )}

                      {canCheckIn && (
                        <button
                          type="button"
                          className="btn btn-primary btn-sm"
                          style={{ flex: 1 }}
                          onClick={() => handleCheckInClick(res)}
                          disabled={isCheckingIn}
                        >
                          Check In
                        </button>
                      )}

                      {canCancel && (
                        <button
                          type="button"
                          className="btn btn-danger btn-sm"
                          onClick={() => handleCancel(res.id)}
                        >
                          Cancel
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div style={{ display: 'flex', justifyContent: 'center', gap: '0.5rem', marginTop: '1.5rem' }}>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setPage((p) => Math.max(p - 1, 1))}
                disabled={page <= 1 || loading}
              >
                Previous
              </button>
              <span style={{ display: 'flex', alignItems: 'center', fontSize: '0.875rem' }}>
                Page {page} of {totalPages}
              </span>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
                disabled={page >= totalPages || loading}
              >
                Next
              </button>
            </div>
          )}
        </div>
      )}

      {/* SUBTAB 2: Reserve a Space Form & Availability Results */}
      {activeSubTab === 'book_space' && (
        <div style={{ maxWidth: '800px', margin: '0 auto' }}>
          <div className="card" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
            <h3 style={{ margin: '0 0 1rem', fontSize: '1.25rem', fontWeight: 600 }}>1. Choose Date & Time Window</h3>

            <form onSubmit={handleSearchAvailability}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                    Date:
                  </label>
                  <input
                    type="date"
                    className="form-control"
                    value={bookingDate}
                    onChange={(e) => setBookingDate(e.target.value)}
                    required
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                    Start Time:
                  </label>
                  <input
                    type="time"
                    className="form-control"
                    value={bookingStartTime}
                    onChange={(e) => setBookingStartTime(e.target.value)}
                    required
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                    End Time:
                  </label>
                  <input
                    type="time"
                    className="form-control"
                    value={bookingEndTime}
                    onChange={(e) => setBookingEndTime(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '1.25rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                    Resource Type:
                  </label>
                  <select
                    className="form-control"
                    value={resourceTypeFilter}
                    onChange={(e) => setResourceTypeFilter(e.target.value as 'seat' | 'room')}
                  >
                    <option value="seat">Study Seat (1 person)</option>
                    <option value="room">Discussion Room (Group)</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                    Zone (Optional):
                  </label>
                  <select
                    className="form-control"
                    value={selectedZoneId}
                    onChange={(e) => setSelectedZoneId(e.target.value ? Number(e.target.value) : '')}
                  >
                    <option value="">All Library Zones</option>
                    {zones.map((z) => (
                      <option key={z.id} value={z.id}>
                        {z.name} (Floor {z.floor}, {z.noise_policy})
                      </option>
                    ))}
                  </select>
                </div>

                {resourceTypeFilter === 'room' && (
                  <div>
                    <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                      Expected Attendees:
                    </label>
                    <input
                      type="number"
                      className="form-control"
                      min={1}
                      max={12}
                      value={expectedAttendees}
                      onChange={(e) => setExpectedAttendees(Number(e.target.value))}
                      required
                    />
                  </div>
                )}
              </div>

              <button
                type="submit"
                className="btn btn-primary"
                disabled={isSearchingAvailability}
                style={{ width: '100%' }}
              >
                {isSearchingAvailability ? 'Checking Live Availability...' : '🔍 Check Live Space Availability'}
              </button>
            </form>
          </div>

          {/* Availability Results */}
          {hasSearched && (
            <div>
              <h3 style={{ margin: '0 0 1rem', fontSize: '1.25rem', fontWeight: 600 }}>
                2. Available {resourceTypeFilter === 'seat' ? 'Seats' : 'Rooms'}
              </h3>

              {resourceTypeFilter === 'seat' ? (
                availableSeats.length === 0 ? (
                  <div className="alert alert-info">No available seats match your criteria for this time window. Try another slot or zone.</div>
                ) : (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '1rem' }}>
                    {availableSeats.map((seat) => {
                      const isSubmitting = bookingSubmittingId === `seat-${seat.id}`;
                      return (
                        <div key={seat.id} className="card" style={{ padding: '1rem', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                          <div>
                            <div style={{ fontWeight: 600, fontSize: '1.05rem', marginBottom: '0.25rem' }}>
                              Seat {seat.seat_code}
                            </div>
                            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
                              {seat.has_power_outlet ? '⚡ Power Outlet' : 'No Outlet'}<br />
                              {seat.has_monitor ? '🖥️ Monitor Display' : 'No Monitor'}<br />
                              {seat.is_accessible ? '♿ Accessible' : ''}
                            </div>
                          </div>
                          <button
                            type="button"
                            className="btn btn-primary btn-sm"
                            onClick={() => handleBookResource(seat.id, 'seat')}
                            disabled={isSubmitting}
                          >
                            {isSubmitting ? 'Booking...' : 'Book This Seat'}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )
              ) : (
                availableRooms.length === 0 ? (
                  <div className="alert alert-info">No available rooms match your criteria for this time window. Try another slot or attendee count.</div>
                ) : (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '1rem' }}>
                    {availableRooms.map((room) => {
                      const isSubmitting = bookingSubmittingId === `room-${room.id}`;
                      return (
                        <div key={room.id} className="card" style={{ padding: '1rem', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                          <div>
                            <div style={{ fontWeight: 600, fontSize: '1.05rem', marginBottom: '0.25rem' }}>
                              {room.name} ({room.room_code})
                            </div>
                            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
                              👥 Capacity: Up to {room.capacity} people<br />
                              📺 Display: {room.display_type.toUpperCase()}<br />
                              {room.has_whiteboard ? '📋 Whiteboard Available' : ''}
                            </div>
                          </div>
                          <button
                            type="button"
                            className="btn btn-primary btn-sm"
                            onClick={() => handleBookResource(room.id, 'room')}
                            disabled={isSubmitting}
                          >
                            {isSubmitting ? 'Booking...' : `Reserve Room (${room.capacity} max)`}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )
              )}
            </div>
          )}
        </div>
      )}

      {/* Interactive Floor Plans & Wayfinding View */}
      {activeSubTab === 'floor_plans' && (
        <StudentFloorPlan
          onInitiateBooking={(type, _id) => {
            setResourceTypeFilter(type);
            setActiveSubTab('book_space');
          }}
        />
      )}

      {/* Occupancy Analytics & Telemetry View */}
      {activeSubTab === 'occupancy' && (
        <OccupancyAnalytics userRole={currentUser.role} />
      )}

      {/* QR Pass Modal */}
      {activeQRData && (
        <QRCodeModal
          qrData={activeQRData}
          onClose={() => setActiveQRData(null)}
        />
      )}

      {/* Room Check-in Attendee Validation Modal */}
      {roomCheckInTarget && (
        <div className="modal-overlay" onClick={() => setRoomCheckInTarget(null)} role="dialog" aria-modal="true">
          <div className="modal-card" style={{ maxWidth: '400px' }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 600 }}>Room Check-In</h3>
              <button type="button" className="btn-close" onClick={() => setRoomCheckInTarget(null)}>✕</button>
            </div>
            <div style={{ padding: '1rem 0' }}>
              <p style={{ margin: '0 0 1rem', fontSize: '0.9rem', color: 'var(--text-muted)' }}>
                Please specify the actual number of attendees present for room check-in:
              </p>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                Actual Attendees Count:
              </label>
              <input
                type="number"
                className="form-control"
                min={1}
                max={12}
                value={actualAttendeesInput}
                onChange={(e) => setActualAttendeesInput(Number(e.target.value))}
                required
              />
            </div>
            <div className="modal-footer" style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
              <button type="button" className="btn btn-secondary" onClick={() => setRoomCheckInTarget(null)}>
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => handleExecuteCheckIn(roomCheckInTarget, actualAttendeesInput)}
                disabled={isCheckingIn || actualAttendeesInput < 1}
              >
                {isCheckingIn ? 'Checking In...' : 'Confirm Check-In'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

