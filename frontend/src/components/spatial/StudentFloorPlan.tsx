import React, { useState, useEffect, useCallback, useMemo } from 'react';
import type {
  LibraryFloor,
  FloorPlanDetailResponse,
  SpatialResourceAvailability,
  WayfindingRouteResponse,
} from '../../types/spatial';
import { getFloors, getFloorDetail, getWayfindingRoute } from '../../services/spatialApi';
import { FloorPlanCanvas } from './FloorPlanCanvas';

interface StudentFloorPlanProps {
  onInitiateBooking?: (resourceType: 'seat' | 'room', resourceId: number) => void;
}

export const StudentFloorPlan: React.FC<StudentFloorPlanProps> = ({ onInitiateBooking }) => {
  const [floors, setFloors] = useState<LibraryFloor[]>([]);
  const [selectedFloorId, setSelectedFloorId] = useState<number | null>(null);
  const [floorDetail, setFloorDetail] = useState<FloorPlanDetailResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // View mode
  const [viewMode, setViewMode] = useState<'map' | 'list'>('map');

  // Search & Filter
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedZoneFilter, setSelectedZoneFilter] = useState<string>('all');
  const [selectedTypeFilter, setSelectedTypeFilter] = useState<string>('all');
  const [availabilityFilter, setAvailabilityFilter] = useState<string>('all');

  // Selection & Wayfinding
  const [selectedResource, setSelectedResource] = useState<SpatialResourceAvailability | null>(null);
  const [wayfindingRoute, setWayfindingRoute] = useState<WayfindingRouteResponse | null>(null);
  const [loadingRoute, setLoadingRoute] = useState<boolean>(false);
  const [routeError, setRouteError] = useState<string | null>(null);

  // 1. Fetch available floors
  useEffect(() => {
    let isMounted = true;
    async function loadFloors() {
      try {
        const data = await getFloors(false);
        if (isMounted) {
          setFloors(data);
          if (data.length > 0 && selectedFloorId === null) {
            setSelectedFloorId(data[0].id);
          }
        }
      } catch (err: any) {
        if (isMounted) setError(err.message || 'Failed to load library floors.');
      }
    }
    loadFloors();
    return () => {
      isMounted = false;
    };
  }, []);

  // 2. Fetch floor details & real-time resource availability
  const fetchFloorDetail = useCallback(async () => {
    if (!selectedFloorId) return;
    setLoading(true);
    setError(null);
    try {
      const detail = await getFloorDetail(selectedFloorId);
      setFloorDetail(detail);
      // Reset selected resource if switching floors
      setSelectedResource(null);
      setWayfindingRoute(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load floor plan layout.');
    } finally {
      setLoading(false);
    }
  }, [selectedFloorId]);

  useEffect(() => {
    fetchFloorDetail();
  }, [fetchFloorDetail]);

  // 3. Wayfinding Route Fetcher
  const handleGetDirections = async () => {
    if (!selectedResource) return;
    setLoadingRoute(true);
    setRouteError(null);
    try {
      const route = await getWayfindingRoute(
        selectedResource.resource_type,
        selectedResource.resource_id
      );
      setWayfindingRoute(route);
    } catch (err: any) {
      setRouteError(err.message || 'Failed to calculate wayfinding path.');
    } finally {
      setLoadingRoute(false);
    }
  };

  // Availability counts
  const counts = useMemo(() => {
    if (!floorDetail) return { available: 0, reserved: 0, occupied: 0, unavailable: 0 };
    return floorDetail.resources.reduce(
      (acc, r) => {
        if (r.availability_status === 'available') acc.available++;
        else if (r.availability_status === 'reserved') acc.reserved++;
        else if (r.availability_status === 'occupied') acc.occupied++;
        else acc.unavailable++;
        return acc;
      },
      { available: 0, reserved: 0, occupied: 0, unavailable: 0 }
    );
  }, [floorDetail]);

  // Filtered resources for List View & Search
  const filteredResources = useMemo(() => {
    if (!floorDetail) return [];
    return floorDetail.resources.filter((r) => {
      if (selectedTypeFilter !== 'all' && r.resource_type !== selectedTypeFilter) return false;
      if (selectedZoneFilter !== 'all' && String(r.zone_id) !== selectedZoneFilter) return false;
      if (availabilityFilter !== 'all' && r.availability_status !== availabilityFilter) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const label = (r.label || '').toLowerCase();
        const code = (r.details?.seat_code || r.details?.room_code || '').toLowerCase();
        const zone = (r.zone_name || '').toLowerCase();
        if (!label.includes(q) && !code.includes(q) && !zone.includes(q)) return false;
      }
      return true;
    });
  }, [floorDetail, selectedTypeFilter, selectedZoneFilter, availabilityFilter, searchQuery]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {/* Disclosure Banner */}
      <div
        style={{
          background: '#f8fafc',
          borderLeft: '4px solid #3b82f6',
          padding: '0.75rem 1rem',
          borderRadius: '6px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: '0.825rem',
          color: '#475569',
        }}
      >
        <div>
          <strong style={{ color: '#1e293b' }}>
            ℹ️ ILLUSTRATIVE DEMONSTRATION LAYOUT — NOT A SURVEYED BUILDING PLAN
          </strong>
          <div style={{ marginTop: '2px' }}>
            Interactive spatial representation with real-time study space availability and wayfinding.
          </div>
        </div>
        <button
          type="button"
          onClick={fetchFloorDetail}
          className="btn btn-secondary btn-sm"
          title="Refresh floor state"
        >
          🔄 Refresh
        </button>
      </div>

      {/* Floor Switcher Navigation Tabs */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '0.75rem',
          background: '#0e1626',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          padding: '0.85rem 1.25rem',
          borderRadius: '12px',
          boxShadow: '0 4px 20px rgba(0, 0, 0, 0.25)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.875rem', fontWeight: 600, color: '#94a3b8' }}>Floor:</span>
          {floors.map((fl) => (
            <button
              key={fl.id}
              type="button"
              onClick={() => setSelectedFloorId(fl.id)}
              className={`btn btn-sm ${
                selectedFloorId === fl.id ? 'btn-primary' : 'btn-secondary'
              }`}
              style={{
                fontWeight: selectedFloorId === fl.id ? 700 : 500,
                boxShadow: selectedFloorId === fl.id ? '0 0 12px rgba(37, 99, 235, 0.4)' : 'none',
              }}
            >
              {fl.name}
            </button>
          ))}
        </div>

        {/* View Switcher: Map vs List */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <button
            type="button"
            onClick={() => setViewMode('map')}
            className={`btn btn-sm ${viewMode === 'map' ? 'btn-primary' : 'btn-secondary'}`}
          >
            🗺️ Interactive Map
          </button>
          <button
            type="button"
            onClick={() => setViewMode('list')}
            className={`btn btn-sm ${viewMode === 'list' ? 'btn-primary' : 'btn-secondary'}`}
          >
            📋 Accessible List
          </button>
        </div>
      </div>

      {/* Availability Status Legend & Metric Badges */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '1.25rem',
          flexWrap: 'wrap',
          fontSize: '0.85rem',
          padding: '0.65rem 1.25rem',
          background: '#0e1626',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '12px',
        }}
      >
        <span style={{ fontWeight: 600, color: '#f8fafc' }}>Live Availability:</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#4ade80' }}>
          <span style={{ width: '9px', height: '9px', borderRadius: '50%', background: '#22c55e', boxShadow: '0 0 8px #22c55e' }} />
          <strong>{counts.available}</strong> Available
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#fbbf24' }}>
          <span style={{ width: '9px', height: '9px', borderRadius: '50%', background: '#f59e0b', boxShadow: '0 0 8px #f59e0b' }} />
          <strong>{counts.reserved}</strong> Reserved
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#f87171' }}>
          <span style={{ width: '9px', height: '9px', borderRadius: '50%', background: '#ef4444', boxShadow: '0 0 8px #ef4444' }} />
          <strong>{counts.occupied}</strong> Occupied
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#94a3b8' }}>
          <span style={{ width: '9px', height: '9px', borderRadius: '50%', background: '#64748b' }} />
          <strong>{counts.unavailable}</strong> Unavailable
        </span>
      </div>

      {/* Main Layout Area: Canvas / List + Inspector Side Panel */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: selectedResource ? '1fr 340px' : '1fr',
          gap: '1rem',
          alignItems: 'start',
        }}
      >
        {/* Left Side: Map or List */}
        <div>
          {loading && (
            <div
              style={{
                height: '420px',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.75rem',
                alignItems: 'center',
                justifyContent: 'center',
                background: '#0e1626',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                borderRadius: '12px',
                color: '#94a3b8',
              }}
            >
              <div style={{ fontSize: '2.2rem' }}>🏛️</div>
              <div style={{ fontWeight: 600, color: '#38bdf8', fontSize: '0.95rem' }}>
                Loading floor plan layout and real-time resource availability...
              </div>
            </div>
          )}

          {error && (
            <div className="alert alert-danger" style={{ margin: '1rem 0' }}>
              {error}
            </div>
          )}

          {!loading && floorDetail && viewMode === 'map' && (
            <FloorPlanCanvas
              floorDetail={floorDetail}
              selectedResource={selectedResource}
              onSelectResource={(res) => setSelectedResource(res)}
              wayfindingRoute={wayfindingRoute}
            />
          )}

          {!loading && floorDetail && viewMode === 'list' && (
            <div
              style={{
                background: '#0e1626',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                borderRadius: '12px',
                padding: '1.25rem',
                boxShadow: '0 4px 20px rgba(0, 0, 0, 0.25)',
                color: '#f8fafc',
              }}
            >
              <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
                <input
                  type="text"
                  placeholder="Filter resources (e.g. S-01, Ada, Collaborative)..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  style={{
                    flex: 1,
                    minWidth: '220px',
                    padding: '0.4rem 0.75rem',
                    borderRadius: '6px',
                    border: '1px solid #cbd5e1',
                    fontSize: '0.85rem',
                  }}
                />
                <select
                  value={selectedTypeFilter}
                  onChange={(e) => setSelectedTypeFilter(e.target.value)}
                  style={{
                    padding: '0.4rem 0.75rem',
                    borderRadius: '6px',
                    border: '1px solid #cbd5e1',
                    fontSize: '0.85rem',
                  }}
                >
                  <option value="all">All Types</option>
                  <option value="seat">Seats</option>
                  <option value="room">Study Rooms</option>
                  <option value="zone">Zones</option>
                </select>
                <select
                  value={selectedZoneFilter}
                  onChange={(e) => setSelectedZoneFilter(e.target.value)}
                  style={{
                    padding: '0.4rem 0.75rem',
                    borderRadius: '6px',
                    border: '1px solid #cbd5e1',
                    fontSize: '0.85rem',
                  }}
                >
                  <option value="all">All Zones</option>
                  {Array.from(new Set(floorDetail.resources.map((r) => r.zone_name).filter(Boolean))).map((zName) => {
                    const sample = floorDetail.resources.find((r) => r.zone_name === zName);
                    return (
                      <option key={String(sample?.zone_id)} value={String(sample?.zone_id)}>
                        {zName}
                      </option>
                    );
                  })}
                </select>
                <select
                  value={availabilityFilter}
                  onChange={(e) => setAvailabilityFilter(e.target.value)}
                  style={{
                    padding: '0.4rem 0.75rem',
                    borderRadius: '6px',
                    border: '1px solid #cbd5e1',
                    fontSize: '0.85rem',
                  }}
                >
                  <option value="all">All Statuses</option>
                  <option value="available">Available</option>
                  <option value="reserved">Reserved</option>
                  <option value="occupied">Occupied</option>
                </select>
              </div>

              {filteredResources.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '2rem', color: '#94a3b8' }}>
                  No resources match the selected criteria.
                </div>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: '0.75rem' }}>
                  {filteredResources.map((res) => {
                    const isSel =
                      selectedResource?.resource_type === res.resource_type &&
                      selectedResource?.resource_id === res.resource_id;
                    return (
                      <div
                        key={`${res.resource_type}-${res.resource_id}`}
                        onClick={() => setSelectedResource(res)}
                        style={{
                          padding: '0.75rem',
                          borderRadius: '8px',
                          border: `1.5px solid ${isSel ? '#3b82f6' : '#e2e8f0'}`,
                          background: isSel ? '#eff6ff' : '#ffffff',
                          cursor: 'pointer',
                          transition: 'all 0.15s ease',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <strong style={{ fontSize: '0.9rem', color: '#1e293b' }}>
                            {res.label}
                          </strong>
                          <span
                            className="badge"
                            style={{
                              fontSize: '0.7rem',
                              textTransform: 'uppercase',
                              backgroundColor:
                                res.availability_status === 'available'
                                  ? '#dcfce7'
                                  : res.availability_status === 'reserved'
                                  ? '#fef3c7'
                                  : res.availability_status === 'occupied'
                                  ? '#fee2e2'
                                  : '#f1f5f9',
                              color:
                                res.availability_status === 'available'
                                  ? '#15803d'
                                  : res.availability_status === 'reserved'
                                  ? '#b45309'
                                  : res.availability_status === 'occupied'
                                  ? '#b91c1c'
                                  : '#475569',
                            }}
                          >
                            {res.availability_status}
                          </span>
                        </div>
                        <div style={{ fontSize: '0.78rem', color: '#64748b', marginTop: '4px' }}>
                          {res.resource_type.toUpperCase()} • {res.zone_name || 'Main Area'}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right Side: Selected Resource Inspector Panel */}
        {selectedResource && (
          <div
            style={{
              background: '#ffffff',
              borderRadius: '10px',
              border: '1px solid #e2e8f0',
              padding: '1.25rem',
              boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <span
                  style={{
                    fontSize: '0.7rem',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    fontWeight: 700,
                    color: '#64748b',
                  }}
                >
                  {selectedResource.resource_type.toUpperCase()}
                </span>
                <h3 style={{ margin: '4px 0 0 0', fontSize: '1.2rem', color: '#1e293b' }}>
                  {selectedResource.label}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => {
                  setSelectedResource(null);
                  setWayfindingRoute(null);
                }}
                className="btn btn-secondary btn-sm"
                style={{ padding: '0.2rem 0.5rem', minWidth: 'auto' }}
              >
                ✕
              </button>
            </div>

            <div style={{ marginTop: '0.75rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  background:
                    selectedResource.availability_status === 'available'
                      ? '#22c55e'
                      : selectedResource.availability_status === 'reserved'
                      ? '#f59e0b'
                      : selectedResource.availability_status === 'occupied'
                      ? '#ef4444'
                      : '#94a3b8',
                }}
              />
              <span
                style={{
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  textTransform: 'capitalize',
                  color:
                    selectedResource.availability_status === 'available'
                      ? '#16a34a'
                      : selectedResource.availability_status === 'reserved'
                      ? '#d97706'
                      : selectedResource.availability_status === 'occupied'
                      ? '#dc2626'
                      : '#475569',
                }}
              >
                {selectedResource.availability_status}
              </span>
              <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                (Live reservation status)
              </span>
            </div>

            {/* Context details */}
            <div style={{ marginTop: '1rem', borderTop: '1px solid #f1f5f9', paddingTop: '0.75rem' }}>
              <div style={{ fontSize: '0.825rem', color: '#475569', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <div>
                  <strong>Floor:</strong> {floorDetail?.floor.name} (Level {floorDetail?.floor.floor_number})
                </div>
                {selectedResource.zone_name && (
                  <div>
                    <strong>Zone:</strong> {selectedResource.zone_name}
                  </div>
                )}
                {selectedResource.capacity && (
                  <div>
                    <strong>Capacity:</strong> {selectedResource.capacity} Person(s)
                  </div>
                )}
              </div>

              {/* Amenity Badges */}
              {selectedResource.details && (
                <div style={{ marginTop: '0.75rem', display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                  {selectedResource.details.has_power_outlet && (
                    <span className="badge" style={{ background: '#e0f2fe', color: '#0369a1', fontSize: '0.725rem' }}>
                      ⚡ Power Outlet
                    </span>
                  )}
                  {selectedResource.details.has_monitor && (
                    <span className="badge" style={{ background: '#f3e8ff', color: '#7e22ce', fontSize: '0.725rem' }}>
                      🖥️ External Monitor
                    </span>
                  )}
                  {selectedResource.details.is_accessible && (
                    <span className="badge" style={{ background: '#dcfce7', color: '#15803d', fontSize: '0.725rem' }}>
                      ♿ Accessible Carrel
                    </span>
                  )}
                  {selectedResource.details.has_whiteboard && (
                    <span className="badge" style={{ background: '#fef3c7', color: '#b45309', fontSize: '0.725rem' }}>
                      📋 Whiteboard
                    </span>
                  )}
                </div>
              )}
            </div>

            {/* Wayfinding Action */}
            <div style={{ marginTop: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <button
                type="button"
                onClick={handleGetDirections}
                disabled={loadingRoute}
                className="btn btn-secondary btn-sm"
                style={{ width: '100%', fontWeight: 600 }}
              >
                {loadingRoute ? 'Calculating Route...' : '🧭 Show Wayfinding Route'}
              </button>

              {/* Direct Booking Action */}
              {selectedResource.availability_status === 'available' && onInitiateBooking && (
                <button
                  type="button"
                  onClick={() =>
                    onInitiateBooking(
                      selectedResource.resource_type as 'seat' | 'room',
                      selectedResource.resource_id
                    )
                  }
                  className="btn btn-primary btn-sm"
                  style={{ width: '100%', fontWeight: 600 }}
                >
                  📅 Book {selectedResource.label}
                </button>
              )}
            </div>

            {/* Wayfinding Step-by-Step Directions */}
            {routeError && (
              <div className="alert alert-danger" style={{ marginTop: '0.75rem', fontSize: '0.75rem' }}>
                {routeError}
              </div>
            )}

            {wayfindingRoute && (
              <div
                style={{
                  marginTop: '1rem',
                  borderTop: '1px solid #f1f5f9',
                  paddingTop: '0.75rem',
                  fontSize: '0.8rem',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <strong style={{ color: '#0f172a' }}>Step-by-Step Guidance:</strong>
                  <span style={{ fontSize: '0.7rem', color: '#64748b' }}>
                    Dist: ~{wayfindingRoute.total_distance}m
                  </span>
                </div>
                <ol style={{ paddingLeft: '1.25rem', margin: '0.5rem 0 0 0', color: '#334155' }}>
                  {wayfindingRoute.steps.map((st) => (
                    <li key={st.step_number} style={{ marginBottom: '4px' }}>
                      {st.instruction}
                    </li>
                  ))}
                </ol>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: '6px' }}>
                  ℹ️ Visual guidance on interactive floor canvas above.
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
