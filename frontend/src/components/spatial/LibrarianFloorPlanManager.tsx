import React, { useState, useEffect, useCallback } from 'react';
import type {
  LibraryFloor,
  FloorPlanDetailResponse,
  SpatialResourceAvailability,
  SpatialCompletenessReport,
} from '../../types/spatial';
import {
  getFloors,
  getFloorDetail,
  getSpatialCompleteness,
  createFloorLayout,
  validateLayout,
  publishLayout,
  createLayoutElement,
  deleteLayoutElement,
} from '../../services/spatialApi';
import { FloorPlanCanvas } from './FloorPlanCanvas';

export const LibrarianFloorPlanManager: React.FC = () => {
  const [floors, setFloors] = useState<LibraryFloor[]>([]);
  const [selectedFloorId, setSelectedFloorId] = useState<number | null>(null);
  const [floorDetail, setFloorDetail] = useState<FloorPlanDetailResponse | null>(null);
  const [completeness, setCompleteness] = useState<SpatialCompletenessReport | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Layout validation state
  const [validationReport, setValidationReport] = useState<{
    is_valid: boolean;
    errors: string[];
    warnings: string[];
  } | null>(null);
  const [isPublishing, setIsPublishing] = useState<boolean>(false);

  // Selected resource on canvas
  const [selectedResource, setSelectedResource] = useState<SpatialResourceAvailability | null>(null);

  // Element Creation Modal / Form State
  const [showElementForm, setShowElementForm] = useState<boolean>(false);
  const [newElementType, setNewElementType] = useState<string>('label');
  const [newElementLabel, setNewElementLabel] = useState<string>('');
  const [newElementX, setNewElementX] = useState<number>(0.5);
  const [newElementY, setNewElementY] = useState<number>(0.5);
  const [newElementW, setNewElementW] = useState<number>(0.1);
  const [newElementH, setNewElementH] = useState<number>(0.05);

  // 1. Initial data fetch
  const fetchOverview = useCallback(async () => {
    try {
      const [floorsData, compData] = await Promise.all([
        getFloors(true),
        getSpatialCompleteness(),
      ]);
      setFloors(floorsData);
      setCompleteness(compData);
      if (floorsData.length > 0 && selectedFloorId === null) {
        setSelectedFloorId(floorsData[0].id);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load spatial overview.');
    }
  }, [selectedFloorId]);

  useEffect(() => {
    fetchOverview();
  }, [fetchOverview]);

  // 2. Fetch specific floor layout
  const fetchFloor = useCallback(async () => {
    if (!selectedFloorId) return;
    setLoading(true);
    setError(null);
    setValidationReport(null);
    try {
      const detail = await getFloorDetail(selectedFloorId);
      setFloorDetail(detail);
    } catch (err: any) {
      setError(err.message || 'Failed to load floor detail.');
    } finally {
      setLoading(false);
    }
  }, [selectedFloorId]);

  useEffect(() => {
    fetchFloor();
  }, [fetchFloor]);

  // 3. Create Draft Layout
  const handleCreateDraft = async () => {
    if (!selectedFloorId) return;
    setActionSuccess(null);
    setError(null);
    try {
      await createFloorLayout(selectedFloorId, {
        title: `${floorDetail?.floor.name} Draft Revision`,
        description: 'New layout draft created from librarian spatial management console.',
      });
      setActionSuccess('New draft layout revision created.');
      fetchFloor();
      fetchOverview();
    } catch (err: any) {
      setError(err.message || 'Failed to create layout draft.');
    }
  };

  // 4. Validate Layout
  const handleValidateLayout = async () => {
    if (!floorDetail?.layout?.id) {
      setError('No active layout revision to validate.');
      return;
    }
    setError(null);
    try {
      const report = await validateLayout(floorDetail.layout.id);
      setValidationReport(report);
    } catch (err: any) {
      setError(err.message || 'Failed to validate layout.');
    }
  };

  // 5. Publish Layout
  const handlePublishLayout = async () => {
    if (!floorDetail?.layout?.id) return;
    setIsPublishing(true);
    setError(null);
    setActionSuccess(null);
    try {
      await publishLayout(floorDetail.layout.id);
      setActionSuccess('Layout successfully validated and published as authoritative!');
      setValidationReport(null);
      fetchFloor();
      fetchOverview();
    } catch (err: any) {
      setError(err.message || 'Failed to publish layout.');
    } finally {
      setIsPublishing(false);
    }
  };

  // 6. Add Structural Element
  const handleAddElement = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFloorId) return;
    try {
      await createLayoutElement(selectedFloorId, {
        layout_id: floorDetail?.layout?.id,
        element_type: newElementType,
        label: newElementLabel,
        geometry_type: newElementType === 'label' ? 'text' : 'rect',
        geometry_data: {
          x: newElementX,
          y: newElementY,
          width: newElementW,
          height: newElementH,
        },
      });
      setShowElementForm(false);
      setNewElementLabel('');
      setActionSuccess(`Added structural element '${newElementLabel || newElementType}'.`);
      fetchFloor();
    } catch (err: any) {
      setError(err.message || 'Failed to create element.');
    }
  };

  // 7. Delete Element
  const handleDeleteElement = async (elemId: number) => {
    if (!window.confirm('Delete this structural element?')) return;
    try {
      await deleteLayoutElement(elemId);
      setActionSuccess('Element deleted.');
      fetchFloor();
    } catch (err: any) {
      setError(err.message || 'Failed to delete element.');
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {/* Completeness Summary Banner */}
      {completeness && (
        <div
          style={{
            background: '#ffffff',
            borderRadius: '10px',
            padding: '1rem 1.25rem',
            border: '1px solid #e2e8f0',
            boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '1rem',
          }}
        >
          <div>
            <h4 style={{ margin: '0 0 4px 0', color: '#1e293b' }}>
              Spatial Mapping Completeness
            </h4>
            <div style={{ fontSize: '0.825rem', color: '#64748b' }}>
              Referential alignment across library study zones, seats, and rooms.
            </div>
          </div>

          <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 600 }}>ZONES</div>
              <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#1e293b' }}>
                {completeness.mapped_zones} / {completeness.total_zones}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 600 }}>SEATS</div>
              <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#1e293b' }}>
                {completeness.mapped_seats} / {completeness.total_seats}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 600 }}>ROOMS</div>
              <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#1e293b' }}>
                {completeness.mapped_rooms} / {completeness.total_rooms}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 600 }}>TOTAL COMPLETENESS</div>
              <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#16a34a' }}>
                {completeness.mapping_completeness_percentage}%
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Notifications */}
      {actionSuccess && (
        <div className="alert alert-success" style={{ margin: '0' }}>
          ✓ {actionSuccess}
        </div>
      )}
      {error && (
        <div className="alert alert-danger" style={{ margin: '0' }}>
          ✕ {error}
        </div>
      )}

      {/* Floor & Layout Controls Toolbar */}
      <div
        style={{
          background: '#ffffff',
          borderRadius: '8px',
          padding: '0.75rem 1rem',
          border: '1px solid #e2e8f0',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '0.75rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#475569' }}>Select Floor:</span>
          {floors.map((fl) => (
            <button
              key={fl.id}
              type="button"
              onClick={() => setSelectedFloorId(fl.id)}
              className={`btn btn-sm ${selectedFloorId === fl.id ? 'btn-primary' : 'btn-secondary'}`}
            >
              {fl.name}
            </button>
          ))}
        </div>

        {/* Layout Revision Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <button
            type="button"
            onClick={handleCreateDraft}
            className="btn btn-secondary btn-sm"
          >
            + New Revision Draft
          </button>
          <button
            type="button"
            onClick={() => setShowElementForm(true)}
            className="btn btn-secondary btn-sm"
          >
            + Add Structural Element
          </button>
          <button
            type="button"
            onClick={handleValidateLayout}
            className="btn btn-secondary btn-sm"
          >
            🔍 Validate Layout
          </button>
          <button
            type="button"
            onClick={handlePublishLayout}
            disabled={isPublishing}
            className="btn btn-primary btn-sm"
            style={{ fontWeight: 700 }}
          >
            {isPublishing ? 'Publishing...' : '🚀 Publish Layout'}
          </button>
        </div>
      </div>

      {/* Validation Results Drawer */}
      {validationReport && (
        <div
          style={{
            background: validationReport.is_valid ? '#f0fdf4' : '#fee2e2',
            border: `1px solid ${validationReport.is_valid ? '#86efac' : '#fca5a5'}`,
            borderRadius: '8px',
            padding: '1rem',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <strong style={{ color: validationReport.is_valid ? '#166534' : '#991b1b' }}>
              {validationReport.is_valid
                ? '✓ Layout Validation Passed — Ready for Publication'
                : '✕ Layout Validation Failed — Publication Blocked'}
            </strong>
            <button
              type="button"
              onClick={() => setValidationReport(null)}
              className="btn btn-secondary btn-sm"
              style={{ padding: '0.15rem 0.5rem' }}
            >
              ✕
            </button>
          </div>

          {validationReport.errors.length > 0 && (
            <ul style={{ margin: '0.5rem 0 0 1.25rem', color: '#b91c1c', fontSize: '0.85rem' }}>
              {validationReport.errors.map((err, i) => (
                <li key={i}>{err}</li>
              ))}
            </ul>
          )}

          {validationReport.warnings.length > 0 && (
            <ul style={{ margin: '0.5rem 0 0 1.25rem', color: '#854d0e', fontSize: '0.85rem' }}>
              {validationReport.warnings.map((warn, i) => (
                <li key={i}>{warn}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Main Canvas Viewport */}
      {loading ? (
        <div style={{ padding: '3rem', textAlign: 'center', color: '#64748b' }}>
          Loading floor plan layout...
        </div>
      ) : floorDetail ? (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: '1rem' }}>
          <div>
            <FloorPlanCanvas
              floorDetail={floorDetail}
              selectedResource={selectedResource}
              onSelectResource={(res) => setSelectedResource(res)}
            />
          </div>

          {/* Elements List Panel */}
          <div
            style={{
              background: '#ffffff',
              borderRadius: '8px',
              padding: '1rem',
              border: '1px solid #e2e8f0',
              maxHeight: '620px',
              overflowY: 'auto',
            }}
          >
            <h5 style={{ margin: '0 0 0.75rem 0', color: '#1e293b' }}>
              Structural Elements ({floorDetail.elements.length})
            </h5>
            {floorDetail.elements.length === 0 ? (
              <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
                No structural elements configured.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {floorDetail.elements.map((el) => (
                  <div
                    key={el.id}
                    style={{
                      padding: '0.5rem 0.75rem',
                      background: '#f8fafc',
                      borderRadius: '6px',
                      border: '1px solid #e2e8f0',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      fontSize: '0.8rem',
                    }}
                  >
                    <div>
                      <strong style={{ color: '#334155' }}>{el.label || el.element_type}</strong>
                      <div style={{ color: '#94a3b8', fontSize: '0.725rem' }}>
                        Type: {el.element_type} ({el.geometry_type})
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleDeleteElement(el.id)}
                      className="btn btn-secondary btn-sm"
                      style={{ padding: '0.15rem 0.4rem', color: '#ef4444' }}
                      title="Delete element"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      ) : null}

      {/* Add Element Modal / Form */}
      {showElementForm && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.5)',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <div
            style={{
              background: '#ffffff',
              borderRadius: '10px',
              padding: '1.5rem',
              width: '420px',
              boxShadow: '0 10px 25px rgba(0,0,0,0.2)',
            }}
          >
            <h4 style={{ margin: '0 0 1rem 0' }}>Add Structural Element</h4>
            <form onSubmit={handleAddElement} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div>
                <label style={{ fontSize: '0.8rem', fontWeight: 600 }}>Element Type:</label>
                <select
                  value={newElementType}
                  onChange={(e) => setNewElementType(e.target.value)}
                  className="form-control"
                  style={{ width: '100%', padding: '0.4rem' }}
                >
                  <option value="wall">Perimeter Wall</option>
                  <option value="door">Door</option>
                  <option value="entrance">Entrance</option>
                  <option value="stairs">Stairs</option>
                  <option value="elevator">Elevator</option>
                  <option value="restroom">Restroom</option>
                  <option value="service_desk">Service Desk</option>
                  <option value="label">Text Label</option>
                  <option value="facility">Facility / Landmark</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: '0.8rem', fontWeight: 600 }}>Label / Title:</label>
                <input
                  type="text"
                  value={newElementLabel}
                  onChange={(e) => setNewElementLabel(e.target.value)}
                  placeholder="e.g. North Exit, Elevator Bay"
                  className="form-control"
                  style={{ width: '100%', padding: '0.4rem' }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                <div>
                  <label style={{ fontSize: '0.8rem', fontWeight: 600 }}>X (0.0 - 1.0):</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    value={newElementX}
                    onChange={(e) => setNewElementX(parseFloat(e.target.value))}
                    className="form-control"
                    style={{ width: '100%', padding: '0.4rem' }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.8rem', fontWeight: 600 }}>Y (0.0 - 1.0):</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    value={newElementY}
                    onChange={(e) => setNewElementY(parseFloat(e.target.value))}
                    className="form-control"
                    style={{ width: '100%', padding: '0.4rem' }}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                <div>
                  <label style={{ fontSize: '0.8rem', fontWeight: 600 }}>Width (0.0 - 1.0):</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    max="1"
                    value={newElementW}
                    onChange={(e) => setNewElementW(parseFloat(e.target.value))}
                    className="form-control"
                    style={{ width: '100%', padding: '0.4rem' }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.8rem', fontWeight: 600 }}>Height (0.0 - 1.0):</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    max="1"
                    value={newElementH}
                    onChange={(e) => setNewElementH(parseFloat(e.target.value))}
                    className="form-control"
                    style={{ width: '100%', padding: '0.4rem' }}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1rem' }}>
                <button
                  type="button"
                  onClick={() => setShowElementForm(false)}
                  className="btn btn-secondary btn-sm"
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary btn-sm">
                  Save Element
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
