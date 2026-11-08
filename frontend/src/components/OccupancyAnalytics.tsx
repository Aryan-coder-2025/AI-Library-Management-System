import React, { useEffect, useState, useCallback, useMemo } from 'react';
import {
  getCurrentOccupancy,
  getResourceOccupancy,
  getHistoricalOccupancy,
  getPeakUsageHours,
  ingestTelemetryObservation,
} from '../services/spacesApi';
import type {
  CurrentOccupancyResponse,
  ResourceOccupancyResponse,
  HistoricalOccupancyResponse,
  PeakUsageAnalysisResponse,
} from '../types/library';

interface OccupancyAnalyticsProps {
  userRole?: string;
}

export const OccupancyAnalytics: React.FC<OccupancyAnalyticsProps> = ({ userRole = 'student' }) => {
  const isStaff = userRole === 'librarian' || userRole === 'admin';

  // ── Live Occupancy State ────────────────────────────────────────────────────
  const [liveOccupancy, setLiveOccupancy] = useState<CurrentOccupancyResponse | null>(null);
  const [resourceDetails, setResourceDetails] = useState<ResourceOccupancyResponse | null>(null);
  const [loadingLive, setLoadingLive] = useState<boolean>(true);
  const [liveError, setLiveError] = useState<string | null>(null);

  // ── Historical Trends State ────────────────────────────────────────────────
  const [historicalData, setHistoricalData] = useState<HistoricalOccupancyResponse | null>(null);
  const [loadingHistory, setLoadingHistory] = useState<boolean>(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [historyDaysBack, setHistoryDaysBack] = useState<number>(30);
  const [historyInterval, setHistoryInterval] = useState<'day' | 'hour'>('day');
  const [selectedZoneId, setSelectedZoneId] = useState<number | 'all'>('all');

  // ── Peak Usage Hours State ─────────────────────────────────────────────────
  const [peakData, setPeakData] = useState<PeakUsageAnalysisResponse | null>(null);
  const [loadingPeak, setLoadingPeak] = useState<boolean>(false);
  const [peakError, setPeakError] = useState<string | null>(null);

  // ── Telemetry Ingestion State (Staff Only) ──────────────────────────────────
  const [ingestZoneId, setIngestZoneId] = useState<number>(1);
  const [ingestCount, setIngestCount] = useState<number>(5);
  const [ingestSensorId, setIngestSensorId] = useState<string>('SENSOR-MANUAL-01');
  const [ingestSubmitting, setIngestSubmitting] = useState<boolean>(false);
  const [ingestMessage, setIngestMessage] = useState<{ type: 'success' | 'info' | 'error'; text: string } | null>(null);

  // ── Active Tab inside Occupancy View ────────────────────────────────────────
  const [activeTab, setActiveTab] = useState<'live' | 'trends' | 'peak' | 'telemetry'>('live');

  // Hover state for SVG chart tooltips
  const [hoveredDataPoint, setHoveredDataPoint] = useState<any | null>(null);
  const [hoveredHour, setHoveredHour] = useState<any | null>(null);

  // ── Fetch Live Occupancy ────────────────────────────────────────────────────
  const fetchLive = useCallback(async () => {
    setLoadingLive(true);
    setLiveError(null);
    try {
      const [current, resources] = await Promise.all([
        getCurrentOccupancy(),
        getResourceOccupancy().catch(() => null),
      ]);
      setLiveOccupancy(current);
      if (resources) setResourceDetails(resources);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve live occupancy data';
      setLiveError(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setLoadingLive(false);
    }
  }, []);

  // ── Fetch Historical Trends ────────────────────────────────────────────────
  const fetchHistorical = useCallback(async () => {
    setLoadingHistory(true);
    setHistoryError(null);
    try {
      const zoneParam = selectedZoneId === 'all' ? undefined : Number(selectedZoneId);
      const res = await getHistoricalOccupancy({
        zoneId: zoneParam,
        interval: historyInterval,
        daysBack: historyDaysBack,
      });
      setHistoricalData(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load historical occupancy trends';
      setHistoryError(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setLoadingHistory(false);
    }
  }, [selectedZoneId, historyInterval, historyDaysBack]);

  // ── Fetch Peak Usage Hours ─────────────────────────────────────────────────
  const fetchPeakHours = useCallback(async () => {
    setLoadingPeak(true);
    setPeakError(null);
    try {
      const zoneParam = selectedZoneId === 'all' ? undefined : Number(selectedZoneId);
      const res = await getPeakUsageHours({
        zoneId: zoneParam,
        daysBack: historyDaysBack,
      });
      setPeakData(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load peak usage profile';
      setPeakError(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setLoadingPeak(false);
    }
  }, [selectedZoneId, historyDaysBack]);

  // Initial load
  useEffect(() => {
    fetchLive();
  }, [fetchLive]);

  useEffect(() => {
    if (activeTab === 'trends') {
      fetchHistorical();
    } else if (activeTab === 'peak') {
      fetchPeakHours();
    }
  }, [activeTab, fetchHistorical, fetchPeakHours]);

  // ── Telemetry Ingestion Handler ─────────────────────────────────────────────
  const handleIngestTelemetry = async (e: React.FormEvent) => {
    e.preventDefault();
    if (ingestCount < 0) {
      setIngestMessage({ type: 'error', text: 'Observed headcount cannot be negative.' });
      return;
    }
    setIngestSubmitting(true);
    setIngestMessage(null);
    try {
      const res = await ingestTelemetryObservation({
        zone_id: ingestZoneId,
        observed_count: ingestCount,
        source_sensor_id: ingestSensorId.trim() || undefined,
      });
      const statusDesc =
        res.status === 'idempotent_duplicate'
          ? 'Duplicate observation detected (idempotent write).'
          : res.status === 'updated'
          ? 'Existing observation updated with corrected headcount.'
          : 'New telemetry observation successfully recorded.';

      setIngestMessage({
        type: res.status === 'idempotent_duplicate' ? 'info' : 'success',
        text: `${statusDesc} ID: #${res.id}, Utilization: ${(res.capacity_utilization * 100).toFixed(1)}%`,
      });
      // Refresh live & historical
      fetchLive();
      if (activeTab === 'trends') fetchHistorical();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Telemetry ingestion failed';
      setIngestMessage({ type: 'error', text: msg.replace(/^\d+:\s*/, '') });
    } finally {
      setIngestSubmitting(false);
    }
  };

  // Helper: Progress bar color based on utilization
  const getProgressColor = (pct: number) => {
    if (pct >= 85) return '#dc2626'; // Red
    if (pct >= 60) return '#d97706'; // Amber
    return '#059669'; // Emerald
  };

  // Maximum value in historical points for SVG scaling
  const maxHistoricalVal = useMemo(() => {
    if (!historicalData || historicalData.data_points.length === 0) return 10;
    const maxVal = Math.max(...historicalData.data_points.map((p) => p.avg_observed_count));
    return Math.max(maxVal, 10);
  }, [historicalData]);

  // Maximum value in peak hourly distribution for SVG scaling
  const maxPeakVal = useMemo(() => {
    if (!peakData || peakData.hourly_distribution.length === 0) return 10;
    const maxVal = Math.max(...peakData.hourly_distribution.map((h) => h.avg_observed_count));
    return Math.max(maxVal, 10);
  }, [peakData]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* ── Header ───────────────────────────────────────────────────────── */}
      <div className="page-header" style={{ marginBottom: '0.5rem' }}>
        <div className="page-title-group">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <h1 style={{ margin: 0 }}>Library Occupancy & Telemetry Analytics</h1>
            <span
              className="badge"
              style={{
                backgroundColor: '#eff6ff',
                color: '#1d4ed8',
                border: '1px solid #bfdbfe',
                fontSize: '0.75rem',
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
              }}
            >
              SPAC-05 Live
            </span>
          </div>
          <p className="page-subtitle" style={{ margin: '0.25rem 0 0 0' }}>
            Real-time reservation-derived capacity, zone heatmaps, and recorded 20,000-observation sensor telemetry
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => {
              fetchLive();
              if (activeTab === 'trends') fetchHistorical();
              if (activeTab === 'peak') fetchPeakHours();
            }}
            disabled={loadingLive || loadingHistory || loadingPeak}
          >
            {loadingLive || loadingHistory || loadingPeak ? 'Refreshing...' : '↻ Refresh'}
          </button>
        </div>
      </div>

      {/* ── Sub Navigation Tabs ───────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: '0.5rem', borderBottom: '1px solid #e2e8f0', paddingBottom: '0.5rem' }}>
        <button
          type="button"
          className={`btn btn-sm ${activeTab === 'live' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setActiveTab('live')}
        >
          ● Real-Time Library Occupancy
        </button>
        <button
          type="button"
          className={`btn btn-sm ${activeTab === 'trends' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setActiveTab('trends')}
        >
          📊 Historical Telemetry Trends
        </button>
        <button
          type="button"
          className={`btn btn-sm ${activeTab === 'peak' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setActiveTab('peak')}
        >
          🕒 24-Hour Peak Usage Profile
        </button>
        {isStaff && (
          <button
            type="button"
            className={`btn btn-sm ${activeTab === 'telemetry' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('telemetry')}
          >
            📡 Ingest Sensor Telemetry
          </button>
        )}
      </div>

      {/* ── Live Occupancy Tab ────────────────────────────────────────────── */}
      {activeTab === 'live' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {liveError && (
            <div className="alert alert-error">
              <span>{liveError}</span>
              <button type="button" className="btn btn-secondary btn-sm" onClick={fetchLive}>
                Retry
              </button>
            </div>
          )}

          {loadingLive && !liveOccupancy ? (
            <div className="card" style={{ padding: '2rem', textAlign: 'center', color: '#64748b' }}>
              Calculating real-time study space occupancy from checked-in bookings...
            </div>
          ) : liveOccupancy ? (
            <>
              {/* Provenance Banner */}
              <div
                style={{
                  background: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  borderRadius: '8px',
                  padding: '0.85rem 1.25rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: '0.75rem',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <span
                    style={{
                      display: 'inline-block',
                      width: '10px',
                      height: '10px',
                      borderRadius: '50%',
                      backgroundColor: '#10b981',
                      boxShadow: '0 0 0 3px rgba(16, 185, 129, 0.2)',
                    }}
                  />
                  <div>
                    <span style={{ fontWeight: 600, color: '#1e293b', fontSize: '0.9rem' }}>
                      Data Provenance:{' '}
                    </span>
                    <span
                      className="badge"
                      style={{
                        background: '#e0f2fe',
                        color: '#0369a1',
                        border: '1px solid #bae6fd',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        marginLeft: '0.25rem',
                      }}
                    >
                      {liveOccupancy.provenance === 'reservation_estimate'
                        ? 'Reservation-Based Estimate'
                        : liveOccupancy.provenance}
                    </span>
                    <span style={{ color: '#64748b', fontSize: '0.825rem', marginLeft: '0.5rem' }}>
                      (Active, checked-in bookings. Excludes cancelled, completed, and no-shows.)
                    </span>
                  </div>
                </div>
                <div style={{ fontSize: '0.8rem', color: '#64748b' }}>
                  As of: {new Date(liveOccupancy.as_of).toLocaleTimeString()}
                </div>
              </div>

              {/* Overall Summary Stats Grid */}
              <div className="stats-grid">
                {/* Total Library Occupancy */}
                <div className="stat-card" style={{ borderLeft: '4px solid #3b82f6' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                    <div className="stat-value">{liveOccupancy.total_library_occupancy}</div>
                    <span style={{ fontSize: '0.85rem', color: '#64748b' }}>
                      / {liveOccupancy.total_library_capacity} cap
                    </span>
                  </div>
                  <div className="stat-label">Total Library Occupancy</div>
                  <div style={{ marginTop: '0.5rem' }}>
                    <div
                      style={{
                        background: '#e2e8f0',
                        borderRadius: '999px',
                        height: '6px',
                        overflow: 'hidden',
                      }}
                    >
                      <div
                        style={{
                          width: `${liveOccupancy.overall_utilization_percentage}%`,
                          background: getProgressColor(liveOccupancy.overall_utilization_percentage),
                          height: '100%',
                          transition: 'width 0.3s ease',
                        }}
                      />
                    </div>
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        fontSize: '0.75rem',
                        color: '#64748b',
                        marginTop: '0.25rem',
                      }}
                    >
                      <span>{liveOccupancy.overall_utilization_percentage}% Utilized</span>
                      <span>{liveOccupancy.total_library_available} Available</span>
                    </div>
                  </div>
                </div>

                {/* Individual Study Seats */}
                <div className="stat-card" style={{ borderLeft: '4px solid #10b981' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                    <div className="stat-value">{liveOccupancy.occupied_seats}</div>
                    <span style={{ fontSize: '0.85rem', color: '#64748b' }}>
                      / {liveOccupancy.total_seats} seats
                    </span>
                  </div>
                  <div className="stat-label">Occupied Study Seats</div>
                  <div style={{ marginTop: '0.5rem' }}>
                    <div
                      style={{
                        background: '#e2e8f0',
                        borderRadius: '999px',
                        height: '6px',
                        overflow: 'hidden',
                      }}
                    >
                      <div
                        style={{
                          width: `${liveOccupancy.seat_utilization_percentage}%`,
                          background: getProgressColor(liveOccupancy.seat_utilization_percentage),
                          height: '100%',
                          transition: 'width 0.3s ease',
                        }}
                      />
                    </div>
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        fontSize: '0.75rem',
                        color: '#64748b',
                        marginTop: '0.25rem',
                      }}
                    >
                      <span>{liveOccupancy.seat_utilization_percentage}% Utilized</span>
                      <span>
                        {resourceDetails
                          ? `${resourceDetails.seats.available_seats} Available`
                          : `${liveOccupancy.total_seats - liveOccupancy.occupied_seats} Avail`}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Study Rooms & Attendees */}
                <div className="stat-card" style={{ borderLeft: '4px solid #2563eb' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                    <div className="stat-value">{liveOccupancy.occupied_room_attendees}</div>
                    <span style={{ fontSize: '0.85rem', color: '#64748b' }}>
                      / {liveOccupancy.total_room_capacity} cap
                    </span>
                  </div>
                  <div className="stat-label">
                    Room Attendees ({liveOccupancy.active_rooms_count}/{liveOccupancy.total_rooms_count} rooms active)
                  </div>
                  <div style={{ marginTop: '0.5rem' }}>
                    <div
                      style={{
                        background: '#e2e8f0',
                        borderRadius: '999px',
                        height: '6px',
                        overflow: 'hidden',
                      }}
                    >
                      <div
                        style={{
                          width: `${liveOccupancy.room_attendees_utilization_percentage}%`,
                          background: getProgressColor(liveOccupancy.room_attendees_utilization_percentage),
                          height: '100%',
                          transition: 'width 0.3s ease',
                        }}
                      />
                    </div>
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        fontSize: '0.75rem',
                        color: '#64748b',
                        marginTop: '0.25rem',
                      }}
                    >
                      <span>{liveOccupancy.room_attendees_utilization_percentage}% Utilized</span>
                      <span>
                        {liveOccupancy.total_room_capacity - liveOccupancy.occupied_room_attendees} Attendee Cap Left
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Resource Amenities Breakdown (if available) */}
              {resourceDetails && (
                <div
                  className="card"
                  style={{
                    padding: '1rem 1.25rem',
                    background: '#ffffff',
                    border: '1px solid #e2e8f0',
                    display: 'flex',
                    flexWrap: 'wrap',
                    justifyContent: 'space-around',
                    gap: '1rem',
                  }}
                >
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#334155' }}>
                      {resourceDetails.seats.power_outlet_seats_count}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#64748b' }}>⚡ Power Outlet Seats</div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#334155' }}>
                      {resourceDetails.seats.monitor_seats_count}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#64748b' }}>🖥️ Monitor Equipped Seats</div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#334155' }}>
                      {resourceDetails.seats.accessible_seats_count}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#64748b' }}>♿ Accessible Seats</div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#334155' }}>
                      {resourceDetails.rooms.total_rooms}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#64748b' }}>🚪 Total Study Rooms</div>
                  </div>
                </div>
              )}

              {/* Zone Heatmap Cards */}
              <div>
                <h3 style={{ margin: '0 0 1rem 0', color: '#1e293b' }}>
                  Study Zones Real-Time Capacity Heatmap (8 Zones)
                </h3>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
                    gap: '1rem',
                  }}
                >
                  {liveOccupancy.zones.map((zone) => {
                    const noiseBadgeColor =
                      zone.noise_policy === 'silent'
                        ? { bg: '#ede9fe', text: '#6d28d9', border: '#ddd6fe' }
                        : zone.noise_policy === 'quiet'
                        ? { bg: '#e0f2fe', text: '#0369a1', border: '#bae6fd' }
                        : { bg: '#fef3c7', text: '#b45309', border: '#fde68a' };

                    return (
                      <div
                        key={zone.zone_id}
                        className="card"
                        style={{
                          padding: '1.25rem',
                          background: '#ffffff',
                          display: 'flex',
                          flexDirection: 'column',
                          justifyContent: 'space-between',
                          gap: '0.75rem',
                          border: '1px solid #e2e8f0',
                        }}
                      >
                        <div>
                          <div
                            style={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'flex-start',
                              marginBottom: '0.25rem',
                            }}
                          >
                            <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#64748b' }}>
                              Floor {zone.floor} • {zone.zone_code}
                            </span>
                            <span
                              className="badge"
                              style={{
                                background: noiseBadgeColor.bg,
                                color: noiseBadgeColor.text,
                                border: `1px solid ${noiseBadgeColor.border}`,
                                fontSize: '0.7rem',
                                padding: '0.15rem 0.5rem',
                                textTransform: 'capitalize',
                              }}
                            >
                              {zone.noise_policy}
                            </span>
                          </div>
                          <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '1rem', color: '#1e293b' }}>
                            {zone.name}
                          </h4>
                        </div>

                        <div>
                          <div
                            style={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'baseline',
                              marginBottom: '0.35rem',
                            }}
                          >
                            <span style={{ fontSize: '0.85rem', color: '#64748b' }}>
                              <strong style={{ color: '#1e293b', fontSize: '1.1rem' }}>
                                {zone.occupied_seats}
                              </strong>{' '}
                              / {zone.total_capacity} seats
                            </span>
                            <span
                              style={{
                                fontSize: '0.85rem',
                                fontWeight: 700,
                                color: getProgressColor(zone.utilization_percentage),
                              }}
                            >
                              {zone.utilization_percentage}%
                            </span>
                          </div>

                          <div
                            style={{
                              background: '#f1f5f9',
                              borderRadius: '999px',
                              height: '8px',
                              overflow: 'hidden',
                            }}
                          >
                            <div
                              style={{
                                width: `${zone.utilization_percentage}%`,
                                background: getProgressColor(zone.utilization_percentage),
                                height: '100%',
                                transition: 'width 0.3s ease',
                              }}
                            />
                          </div>

                          <div
                            style={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              fontSize: '0.75rem',
                              color: '#64748b',
                              marginTop: '0.35rem',
                            }}
                          >
                            <span style={{ color: zone.available_seats > 0 ? '#059669' : '#dc2626' }}>
                              {zone.available_seats > 0 ? `${zone.available_seats} Available` : 'Full'}
                            </span>
                            <span>Noise: {zone.noise_policy}</span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Study Rooms Status */}
              <div>
                <h3 style={{ margin: '1.5rem 0 1rem 0', color: '#1e293b' }}>
                  Study Rooms Active Occupancy (10 Rooms)
                </h3>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
                    gap: '0.75rem',
                  }}
                >
                  {liveOccupancy.rooms.map((room) => (
                    <div
                      key={room.room_id}
                      style={{
                        padding: '0.85rem 1rem',
                        borderRadius: '6px',
                        border: '1px solid #e2e8f0',
                        background: room.is_occupied ? '#fffbeb' : '#ffffff',
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'space-between',
                        gap: '0.5rem',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontWeight: 700, fontSize: '0.85rem', color: '#1e293b' }}>
                          {room.room_code}
                        </span>
                        <span
                          className="badge"
                          style={{
                            fontSize: '0.7rem',
                            background: room.is_occupied ? '#fef3c7' : '#ecfdf5',
                            color: room.is_occupied ? '#92400e' : '#047857',
                            border: `1px solid ${room.is_occupied ? '#fde68a' : '#a7f3d0'}`,
                          }}
                        >
                          {room.is_occupied ? 'Occupied' : 'Vacant'}
                        </span>
                      </div>
                      <div style={{ fontSize: '0.8rem', color: '#475569' }}>{room.name}</div>
                      <div
                        style={{
                          fontSize: '0.75rem',
                          color: '#64748b',
                          display: 'flex',
                          justifyContent: 'space-between',
                          borderTop: '1px dashed #cbd5e1',
                          paddingTop: '0.35rem',
                        }}
                      >
                        <span>Capacity: {room.capacity}</span>
                        <span>
                          {room.is_occupied ? `Attendees: ${room.current_attendees}` : 'Available'}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : null}
        </div>
      )}

      {/* ── Historical Telemetry Trends Tab ───────────────────────────────── */}
      {activeTab === 'trends' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Controls Bar */}
          <div
            className="card"
            style={{
              padding: '1rem',
              background: '#f8fafc',
              border: '1px solid #e2e8f0',
              display: 'flex',
              flexWrap: 'wrap',
              gap: '1rem',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'center' }}>
              <div>
                <label style={{ fontSize: '0.75rem', fontWeight: 600, color: '#475569', display: 'block' }}>
                  Filter by Zone:
                </label>
                <select
                  value={selectedZoneId}
                  onChange={(e) =>
                    setSelectedZoneId(e.target.value === 'all' ? 'all' : Number(e.target.value))
                  }
                  style={{
                    padding: '0.35rem 0.75rem',
                    borderRadius: '6px',
                    border: '1px solid #cbd5e1',
                    fontSize: '0.85rem',
                  }}
                >
                  <option value="all">All Library Study Zones</option>
                  {liveOccupancy?.zones.map((z) => (
                    <option key={z.zone_id} value={z.zone_id}>
                      {z.name} ({z.zone_code})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ fontSize: '0.75rem', fontWeight: 600, color: '#475569', display: 'block' }}>
                  Aggregation Bucket:
                </label>
                <select
                  value={historyInterval}
                  onChange={(e) => setHistoryInterval(e.target.value as 'day' | 'hour')}
                  style={{
                    padding: '0.35rem 0.75rem',
                    borderRadius: '6px',
                    border: '1px solid #cbd5e1',
                    fontSize: '0.85rem',
                  }}
                >
                  <option value="day">Daily Aggregate</option>
                  <option value="hour">Hourly Aggregate</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: '0.75rem', fontWeight: 600, color: '#475569', display: 'block' }}>
                  Time Window:
                </label>
                <select
                  value={historyDaysBack}
                  onChange={(e) => setHistoryDaysBack(Number(e.target.value))}
                  style={{
                    padding: '0.35rem 0.75rem',
                    borderRadius: '6px',
                    border: '1px solid #cbd5e1',
                    fontSize: '0.85rem',
                  }}
                >
                  <option value={7}>Last 7 Days</option>
                  <option value={14}>Last 14 Days</option>
                  <option value={30}>Last 30 Days</option>
                  <option value={90}>Last 90 Days</option>
                  <option value={104}>Full Range (104 Days)</option>
                </select>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span
                className="badge"
                style={{
                  background: '#f1f5f9',
                  color: '#475569',
                  border: '1px solid #cbd5e1',
                  fontSize: '0.75rem',
                }}
              >
                Telemetry: Recorded Synthetic Sensors
              </span>
            </div>
          </div>

          {historyError && (
            <div className="alert alert-error">
              <span>{historyError}</span>
              <button type="button" className="btn btn-secondary btn-sm" onClick={fetchHistorical}>
                Retry
              </button>
            </div>
          )}

          {loadingHistory ? (
            <div className="card" style={{ padding: '2rem', textAlign: 'center', color: '#64748b' }}>
              Aggregating historical sensor telemetry observations in SQL...
            </div>
          ) : historicalData ? (
            <>
              {/* Summary Metrics */}
              <div className="stats-grid">
                <div className="stat-card">
                  <div className="stat-value">{historicalData.total_observations.toLocaleString()}</div>
                  <div className="stat-label">Observations Analyzed</div>
                </div>
                <div className="stat-card">
                  <div className="stat-value" style={{ color: '#0284c7' }}>
                    {historicalData.overall_avg_occupancy}
                  </div>
                  <div className="stat-label">Average Observed Headcount</div>
                </div>
                <div className="stat-card">
                  <div className="stat-value" style={{ color: '#d97706' }}>
                    {historicalData.overall_peak_occupancy}
                  </div>
                  <div className="stat-label">Peak Observed Headcount</div>
                </div>
                <div className="stat-card">
                  <div className="stat-value" style={{ color: '#059669' }}>
                    {(historicalData.overall_avg_utilization * 100).toFixed(1)}%
                  </div>
                  <div className="stat-label">Average Capacity Utilization</div>
                </div>
              </div>

              {/* Responsive SVG Histogram Chart */}
              <div className="card" style={{ padding: '1.25rem', background: '#ffffff', border: '1px solid #e2e8f0' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                  <h4 style={{ margin: 0, color: '#1e293b' }}>
                    Occupancy Over Time ({historicalData.data_points.length} {historyInterval} buckets)
                  </h4>
                  {hoveredDataPoint && (
                    <span style={{ fontSize: '0.85rem', color: '#0369a1', fontWeight: 600 }}>
                      Bucket: {hoveredDataPoint.time_bucket} | Avg: {hoveredDataPoint.avg_observed_count} | Peak: {hoveredDataPoint.max_observed_count} | Util: {(hoveredDataPoint.avg_capacity_utilization * 100).toFixed(1)}%
                    </span>
                  )}
                </div>

                {historicalData.data_points.length === 0 ? (
                  <div style={{ padding: '2rem', textAlign: 'center', color: '#94a3b8' }}>
                    No observations found for the selected filter parameters.
                  </div>
                ) : (
                  <div style={{ width: '100%', overflowX: 'auto' }}>
                    <svg
                      viewBox={`0 0 ${Math.max(600, historicalData.data_points.length * 28)} 200`}
                      style={{ width: '100%', height: '220px', display: 'block' }}
                    >
                      {/* Grid lines */}
                      <line x1="40" y1="20" x2="100%" y2="20" stroke="#f1f5f9" strokeWidth="1" />
                      <line x1="40" y1="80" x2="100%" y2="80" stroke="#f1f5f9" strokeWidth="1" />
                      <line x1="40" y1="140" x2="100%" y2="140" stroke="#f1f5f9" strokeWidth="1" />
                      <line x1="40" y1="170" x2="100%" y2="170" stroke="#cbd5e1" strokeWidth="1" />

                      {/* Y-axis labels */}
                      <text x="5" y="25" fontSize="10" fill="#94a3b8">
                        {Math.round(maxHistoricalVal)}
                      </text>
                      <text x="5" y="100" fontSize="10" fill="#94a3b8">
                        {Math.round(maxHistoricalVal / 2)}
                      </text>
                      <text x="15" y="170" fontSize="10" fill="#94a3b8">
                        0
                      </text>

                      {/* Bars */}
                      {historicalData.data_points.map((pt, idx) => {
                        const barWidth = 20;
                        const x = 50 + idx * 26;
                        const barHeight = Math.max(3, (pt.avg_observed_count / maxHistoricalVal) * 140);
                        const y = 170 - barHeight;
                        const isHovered = hoveredDataPoint === pt;

                        return (
                          <g
                            key={idx}
                            onMouseEnter={() => setHoveredDataPoint(pt)}
                            onMouseLeave={() => setHoveredDataPoint(null)}
                            style={{ cursor: 'pointer' }}
                          >
                            <rect
                              x={x}
                              y={y}
                              width={barWidth}
                              height={barHeight}
                              rx="3"
                              fill={isHovered ? '#0284c7' : '#38bdf8'}
                              style={{ transition: 'all 0.15s ease' }}
                            />
                            {/* X-axis label (every 5th or if few) */}
                            {(idx % Math.ceil(historicalData.data_points.length / 10) === 0 ||
                              historicalData.data_points.length <= 10) && (
                              <text
                                x={x + barWidth / 2}
                                y="186"
                                fontSize="9"
                                fill="#64748b"
                                textAnchor="middle"
                              >
                                {pt.time_bucket.length > 10
                                  ? pt.time_bucket.slice(5, 13)
                                  : pt.time_bucket.slice(5)}
                              </text>
                            )}
                          </g>
                        );
                      })}
                    </svg>
                  </div>
                )}
              </div>
            </>
          ) : null}
        </div>
      )}

      {/* ── 24-Hour Peak Usage Profile Tab ────────────────────────────────── */}
      {activeTab === 'peak' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {peakError && (
            <div className="alert alert-error">
              <span>{peakError}</span>
              <button type="button" className="btn btn-secondary btn-sm" onClick={fetchPeakHours}>
                Retry
              </button>
            </div>
          )}

          {loadingPeak ? (
            <div className="card" style={{ padding: '2rem', textAlign: 'center', color: '#64748b' }}>
              Analyzing 24-hour peak usage profiles from telemetry observations...
            </div>
          ) : peakData ? (
            <>
              {/* Peak Callout Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1rem' }}>
                <div
                  className="card"
                  style={{
                    padding: '1.25rem',
                    background: '#fffbeb',
                    border: '1px solid #fde68a',
                    borderLeft: '5px solid #d97706',
                  }}
                >
                  <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#b45309', textTransform: 'uppercase' }}>
                    ⭐ Busiest Peak Usage Period
                  </div>
                  <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#78350f', marginTop: '0.25rem' }}>
                    {String(peakData.peak_hour).padStart(2, '0')}:00 – {String(peakData.peak_hour + 1).padStart(2, '0')}:00
                  </div>
                  <div style={{ fontSize: '0.85rem', color: '#92400e', marginTop: '0.25rem' }}>
                    Average Occupancy: <strong>{peakData.peak_hour_avg_occupancy.toFixed(1)} people</strong>
                  </div>
                </div>

                <div
                  className="card"
                  style={{
                    padding: '1.25rem',
                    background: '#ecfdf5',
                    border: '1px solid #a7f3d0',
                    borderLeft: '5px solid #059669',
                  }}
                >
                  <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#047857', textTransform: 'uppercase' }}>
                    🌱 Best Time for Quiet Focus
                  </div>
                  <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#064e3b', marginTop: '0.25rem' }}>
                    {String(peakData.lowest_hour).padStart(2, '0')}:00 – {String(peakData.lowest_hour + 1).padStart(2, '0')}:00
                  </div>
                  <div style={{ fontSize: '0.85rem', color: '#065f46', marginTop: '0.25rem' }}>
                    Lowest historical traffic and maximum seat availability
                  </div>
                </div>
              </div>

              {/* 24-Hour Profile Bar Histogram */}
              <div className="card" style={{ padding: '1.25rem', background: '#ffffff', border: '1px solid #e2e8f0' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                  <h4 style={{ margin: 0, color: '#1e293b' }}>
                    24-Hour Diurnal Occupancy Distribution (Hourly Profile)
                  </h4>
                  {hoveredHour && (
                    <span style={{ fontSize: '0.85rem', color: '#0284c7', fontWeight: 600 }}>
                      {String(hoveredHour.hour_of_day).padStart(2, '0')}:00 | Avg:{' '}
                      {hoveredHour.avg_observed_count} | Peak: {hoveredHour.peak_observed_count} | Util:{' '}
                      {hoveredHour.avg_utilization_percentage}%
                    </span>
                  )}
                </div>

                <div style={{ width: '100%', overflowX: 'auto' }}>
                  <svg viewBox="0 0 680 180" style={{ width: '100%', height: '200px', display: 'block' }}>
                    {/* Grid lines */}
                    <line x1="40" y1="20" x2="660" y2="20" stroke="#f1f5f9" strokeWidth="1" />
                    <line x1="40" y1="75" x2="660" y2="75" stroke="#f1f5f9" strokeWidth="1" />
                    <line x1="40" y1="130" x2="660" y2="130" stroke="#f1f5f9" strokeWidth="1" />
                    <line x1="40" y1="150" x2="660" y2="150" stroke="#cbd5e1" strokeWidth="1" />

                    {/* Y-axis labels */}
                    <text x="5" y="25" fontSize="9" fill="#94a3b8">
                      {Math.round(maxPeakVal)}
                    </text>
                    <text x="5" y="80" fontSize="9" fill="#94a3b8">
                      {Math.round(maxPeakVal / 2)}
                    </text>
                    <text x="15" y="150" fontSize="9" fill="#94a3b8">
                      0
                    </text>

                    {/* Hourly Bars */}
                    {peakData.hourly_distribution.map((h) => {
                      const barWidth = 18;
                      const x = 50 + h.hour_of_day * 25;
                      const barHeight = Math.max(3, (h.avg_observed_count / maxPeakVal) * 125);
                      const y = 150 - barHeight;
                      const isHovered = hoveredHour === h;

                      // Peak hour in golden amber, others in blue
                      const fillColor = h.is_peak
                        ? isHovered
                          ? '#b45309'
                          : '#f59e0b'
                        : isHovered
                        ? '#0284c7'
                        : '#60a5fa';

                      return (
                        <g
                          key={h.hour_of_day}
                          onMouseEnter={() => setHoveredHour(h)}
                          onMouseLeave={() => setHoveredHour(null)}
                          style={{ cursor: 'pointer' }}
                        >
                          <rect
                            x={x}
                            y={y}
                            width={barWidth}
                            height={barHeight}
                            rx="3"
                            fill={fillColor}
                          />
                          {/* Hour Label */}
                          <text
                            x={x + barWidth / 2}
                            y="164"
                            fontSize="8"
                            fill={h.is_peak ? '#b45309' : '#64748b'}
                            fontWeight={h.is_peak ? 700 : 400}
                            textAnchor="middle"
                          >
                            {String(h.hour_of_day).padStart(2, '0')}
                          </text>
                          {h.is_peak && (
                            <text
                              x={x + barWidth / 2}
                              y={y - 4}
                              fontSize="8"
                              fill="#b45309"
                              fontWeight={800}
                              textAnchor="middle"
                            >
                              ★
                            </text>
                          )}
                        </g>
                      );
                    })}
                  </svg>
                </div>
              </div>
            </>
          ) : null}
        </div>
      )}

      {/* ── Telemetry Ingestion Tab (Staff / Librarian Only) ──────────────── */}
      {isStaff && activeTab === 'telemetry' && (
        <div className="card" style={{ padding: '1.5rem', background: '#ffffff', border: '1px solid #e2e8f0' }}>
          <h3 style={{ margin: '0 0 0.5rem 0', color: '#1e293b' }}>
            📡 Record New Occupancy Telemetry Observation
          </h3>
          <p style={{ margin: '0 0 1.25rem 0', color: '#64748b', fontSize: '0.85rem' }}>
            Simulate or ingest sensor telemetry from IoT gateways, turnstiles, or manual headcount audits.
            Observations are recorded idempotently within an atomic write transaction.
          </p>

          {ingestMessage && (
            <div
              className={`alert ${
                ingestMessage.type === 'success'
                  ? 'alert-success'
                  : ingestMessage.type === 'info'
                  ? 'alert-info'
                  : 'alert-error'
              }`}
              style={{ marginBottom: '1.25rem' }}
            >
              <span>{ingestMessage.text}</span>
            </div>
          )}

          <form onSubmit={handleIngestTelemetry} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', alignItems: 'end' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#475569', marginBottom: '0.25rem' }}>
                Study Zone:
              </label>
              <select
                value={ingestZoneId}
                onChange={(e) => setIngestZoneId(Number(e.target.value))}
                style={{ width: '100%', padding: '0.5rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}
              >
                {liveOccupancy?.zones.map((z) => (
                  <option key={z.zone_id} value={z.zone_id}>
                    Floor {z.floor} - {z.name} ({z.zone_code}) [Cap: {z.total_capacity}]
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#475569', marginBottom: '0.25rem' }}>
                Observed Headcount:
              </label>
              <input
                type="number"
                min="0"
                max="200"
                value={ingestCount}
                onChange={(e) => setIngestCount(Number(e.target.value))}
                style={{ width: '100%', padding: '0.5rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                required
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#475569', marginBottom: '0.25rem' }}>
                Source Sensor / Audit ID:
              </label>
              <input
                type="text"
                value={ingestSensorId}
                onChange={(e) => setIngestSensorId(e.target.value)}
                placeholder="e.g. SENSOR-G-SILENT-01"
                style={{ width: '100%', padding: '0.5rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}
              />
            </div>

            <div>
              <button
                type="submit"
                className="btn btn-primary"
                style={{ width: '100%' }}
                disabled={ingestSubmitting}
              >
                {ingestSubmitting ? 'Ingesting...' : 'Ingest Observation'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};
