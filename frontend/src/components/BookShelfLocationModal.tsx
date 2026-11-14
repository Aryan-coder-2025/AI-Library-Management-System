import React, { useState, useEffect } from 'react';
import { apiFetch } from '../services/apiClient';
import type { BookShelfLocation } from '../types/library';
import { PrintableSpineLabelsModal } from './PrintableSpineLabelsModal';

interface BookShelfLocationModalProps {
  bookId: number;
  isOpen: boolean;
  onClose: () => void;
}

export const BookShelfLocationModal: React.FC<BookShelfLocationModalProps> = ({
  bookId,
  isOpen,
  onClose,
}) => {
  const [location, setLocation] = useState<BookShelfLocation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [directionMode, setDirectionMode] = useState<'left' | 'right'>('left');
  const [reportingMissing, setReportingMissing] = useState(false);
  const [missingReportNotice, setMissingReportNotice] = useState<string | null>(null);
  const [showPrintModal, setShowPrintModal] = useState(false);

  useEffect(() => {
    if (!isOpen || !bookId) return;
    setLoading(true);
    setError(null);
    setMissingReportNotice(null);

    apiFetch<BookShelfLocation>(`/api/books/${bookId}/shelf-location`)
      .then((data) => {
        setLocation(data);
      })
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : 'Failed to retrieve shelf coordinates';
        setError(msg.replace(/^\d+:\s*/, ''));
      })
      .finally(() => {
        setLoading(false);
      });
  }, [bookId, isOpen]);

  const handleReportMissing = async () => {
    if (!bookId || !location) return;
    setReportingMissing(true);
    setMissingReportNotice(null);
    try {
      const res = await apiFetch<{ message: string }>(`/api/books/${bookId}/report-missing`, {
        method: 'POST',
      });
      setMissingReportNotice(res.message);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to log shelf report';
      alert(`Error: ${msg}`);
    } finally {
      setReportingMissing(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop" onClick={onClose} style={{ zIndex: 1200 }}>
      <div
        className="modal-dialog modal-dialog-large"
        onClick={(e) => e.stopPropagation()}
        style={{
          maxWidth: '860px',
          width: '95%',
          background: 'var(--bg-surface, #111827)',
          border: '1px solid var(--border-color, rgba(99, 102, 241, 0.3))',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.8), 0 0 35px rgba(99, 102, 241, 0.2)',
        }}
      >
        {/* Header */}
        <div
          className="modal-header"
          style={{
            borderBottom: '1px solid var(--border-color, #1f2937)',
            padding: '1.25rem 1.5rem',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <span style={{ fontSize: '1.4rem' }}>📍</span>
              <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary, #f9fafb)' }}>
                Physical Shelf Micro-Location Navigator
              </h3>
            </div>
            <p style={{ margin: '0.25rem 0 0', fontSize: '0.85rem', color: 'var(--text-muted, #9ca3af)' }}>
              Deterministic shelf slot pin-pointing, Dewey Decimal Classification, and aisle coordinates.
            </p>
          </div>
          <button type="button" className="btn-close" onClick={onClose} style={{ color: 'var(--text-muted)' }}>
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="modal-body" style={{ padding: '1.5rem', maxHeight: '80vh', overflowY: 'auto' }}>
          {loading && (
            <div style={{ textAlign: 'center', padding: '3rem 0', color: 'var(--text-muted)' }}>
              <div className="spinner" style={{ margin: '0 auto 1rem' }} />
              <div>Calculating physical stack coordinates & shelf slot...</div>
            </div>
          )}

          {error && (
            <div className="alert alert-error">
              <span>{error}</span>
            </div>
          )}

          {location && (
            <div>
              {/* Monograph Overview Banner */}
              <div
                style={{
                  padding: '1rem 1.25rem',
                  background: 'rgba(99, 102, 241, 0.08)',
                  border: '1px solid rgba(99, 102, 241, 0.25)',
                  borderRadius: '10px',
                  marginBottom: '1.25rem',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '0.75rem',
                }}
              >
                <div>
                  <h4 style={{ margin: 0, fontSize: '1.15rem', color: '#e0e7ff', fontWeight: 600 }}>
                    {location.title}
                  </h4>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                    by {location.author} &bull; <span style={{ color: '#818cf8' }}>{location.category}</span>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                  <span
                    style={{
                      background: 'rgba(245, 158, 11, 0.15)',
                      color: '#f59e0b',
                      border: '1px solid rgba(245, 158, 11, 0.3)',
                      padding: '0.35rem 0.75rem',
                      borderRadius: '6px',
                      fontFamily: 'monospace',
                      fontSize: '0.9rem',
                      fontWeight: 600,
                    }}
                  >
                    🏷️ Call #: {location.call_number}
                  </span>
                </div>
              </div>

              {/* Exact Stack Micro-Coordinates Badges */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                  gap: '0.75rem',
                  marginBottom: '1.5rem',
                }}
              >
                <div
                  style={{
                    background: 'rgba(255, 255, 255, 0.02)',
                    border: '1px solid var(--border-color, #374151)',
                    borderRadius: '8px',
                    padding: '0.75rem',
                    textAlign: 'center',
                  }}
                >
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                    Floor Level
                  </div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#60a5fa', marginTop: '0.2rem' }}>
                    Floor {location.floor_number}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{location.aisle}</div>
                </div>

                <div
                  style={{
                    background: 'rgba(255, 255, 255, 0.02)',
                    border: '1px solid var(--border-color, #374151)',
                    borderRadius: '8px',
                    padding: '0.75rem',
                    textAlign: 'center',
                  }}
                >
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                    Bookcase Bay
                  </div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#a78bfa', marginTop: '0.2rem' }}>
                    {location.bay}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Range Unit</div>
                </div>

                <div
                  style={{
                    background: 'rgba(255, 255, 255, 0.02)',
                    border: '1px solid var(--border-color, #374151)',
                    borderRadius: '8px',
                    padding: '0.75rem',
                    textAlign: 'center',
                  }}
                >
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                    Shelf Tier
                  </div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#34d399', marginTop: '0.2rem' }}>
                    Tier {location.shelf_tier} of 5
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    {location.shelf_tier === 4 ? 'Eye Level (~140cm)' : `Shelf #${location.shelf_tier}`}
                  </div>
                </div>

                <div
                  style={{
                    background: 'rgba(245, 158, 11, 0.1)',
                    border: '2px solid rgba(245, 158, 11, 0.5)',
                    borderRadius: '8px',
                    padding: '0.75rem',
                    textAlign: 'center',
                    boxShadow: '0 0 15px rgba(245, 158, 11, 0.15)',
                  }}
                >
                  <div style={{ fontSize: '0.75rem', color: '#f59e0b', textTransform: 'uppercase', fontWeight: 700 }}>
                    Exact Book Number
                  </div>
                  <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#fbbf24', marginTop: '0.2rem' }}>
                    {directionMode === 'left'
                      ? `Book #${location.position_from_left} from Left`
                      : `Book #${location.position_from_right} from Right`}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#fcd34d' }}>
                    (Slot {location.slot_number} of {location.shelf_capacity})
                  </div>
                </div>
              </div>

              {/* DIRECTION TOGGLE */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '0.75rem',
                }}
              >
                <div style={{ fontSize: '0.9rem', fontWeight: 600, color: '#e0e7ff' }}>
                  📚 Virtual Shelf Rack Simulation (Tier {location.shelf_tier}):
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Count from:</span>
                  <button
                    type="button"
                    className={`btn ${directionMode === 'left' ? 'btn-primary' : 'btn-secondary'}`}
                    style={{ padding: '0.2rem 0.55rem', fontSize: '0.75rem' }}
                    onClick={() => setDirectionMode('left')}
                  >
                    ◀ Left Edge (Recommended)
                  </button>
                  <button
                    type="button"
                    className={`btn ${directionMode === 'right' ? 'btn-primary' : 'btn-secondary'}`}
                    style={{ padding: '0.2rem 0.55rem', fontSize: '0.75rem' }}
                    onClick={() => setDirectionMode('right')}
                  >
                    Right Edge ▶
                  </button>
                </div>
              </div>

              {/* INTERACTIVE VIRTUAL SHELF DISPLAY */}
              <div
                style={{
                  background: 'linear-gradient(180deg, #1f2937 0%, #111827 100%)',
                  border: '3px solid #374151',
                  borderRadius: '12px',
                  padding: '1.5rem 1rem 0.75rem',
                  position: 'relative',
                  marginBottom: '1.5rem',
                  boxShadow: 'inset 0 10px 20px rgba(0,0,0,0.5)',
                }}
              >
                {/* Pointer Arrow on Target Book */}
                <div style={{ textAlign: 'center', marginBottom: '0.5rem' }}>
                  <span
                    style={{
                      background: 'rgba(245, 158, 11, 0.2)',
                      border: '1px solid #f59e0b',
                      color: '#fbbf24',
                      padding: '0.3rem 0.8rem',
                      borderRadius: '999px',
                      fontSize: '0.8rem',
                      fontWeight: 700,
                      animation: 'pulseGlow 2s infinite',
                    }}
                  >
                    👇 TARGET BOOK (#{location.position_from_left} from Left)
                  </span>
                </div>

                {/* Shelf Spine Row */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'flex-end',
                    justifyContent: 'center',
                    gap: '6px',
                    minHeight: '180px',
                    paddingBottom: '8px',
                    overflowX: 'auto',
                  }}
                >
                  {/* Left edge indicator */}
                  <div
                    style={{
                      writingMode: 'vertical-rl',
                      fontSize: '0.7rem',
                      color: 'var(--text-muted)',
                      padding: '0 4px',
                      height: '100px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      borderRight: '2px solid rgba(255,255,255,0.1)',
                      marginRight: '8px',
                    }}
                  >
                    ◀ LEFT EDGE (Slot 1)
                  </div>

                  {/* Adjacent Book Spines on Shelf */}
                  {location.shelf_neighbors.map((neighbor) => {
                    const isTarget = neighbor.is_target;
                    return (
                      <div
                        key={neighbor.slot}
                        style={{
                          width: isTarget ? '72px' : '52px',
                          height: isTarget ? '165px' : '145px',
                          background: isTarget
                            ? 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)'
                            : 'linear-gradient(135deg, #374151 0%, #1f2937 100%)',
                          border: isTarget
                            ? '2px solid #fef08a'
                            : '1px solid rgba(255, 255, 255, 0.1)',
                          borderRadius: '4px 4px 0 0',
                          boxShadow: isTarget
                            ? '0 0 25px rgba(245, 158, 11, 0.5), inset 0 0 10px rgba(255, 255, 255, 0.3)'
                            : 'inset 0 0 5px rgba(0, 0, 0, 0.5)',
                          display: 'flex',
                          flexDirection: 'column',
                          justifyContent: 'space-between',
                          padding: '0.4rem 0.25rem',
                          color: isTarget ? '#1f2937' : 'var(--text-muted)',
                          cursor: 'default',
                          transition: 'all 0.2s ease',
                          transform: isTarget ? 'scale(1.05)' : 'none',
                          zIndex: isTarget ? 2 : 1,
                        }}
                      >
                        <div
                          style={{
                            fontSize: '0.65rem',
                            fontWeight: 800,
                            textAlign: 'center',
                            background: isTarget ? 'rgba(0,0,0,0.15)' : 'rgba(255,255,255,0.05)',
                            padding: '2px 0',
                            borderRadius: '2px',
                          }}
                        >
                          #{neighbor.slot}
                        </div>

                        <div
                          style={{
                            fontSize: isTarget ? '0.68rem' : '0.6rem',
                            fontWeight: isTarget ? 800 : 500,
                            writingMode: 'vertical-rl',
                            textOrientation: 'mixed',
                            transform: 'rotate(180deg)',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                            maxHeight: isTarget ? '95px' : '75px',
                            textAlign: 'center',
                            margin: 'auto',
                            color: isTarget ? '#0f172a' : '#d1d5db',
                          }}
                        >
                          {neighbor.title}
                        </div>

                        <div
                          style={{
                            fontSize: '0.55rem',
                            fontFamily: 'monospace',
                            textAlign: 'center',
                            borderTop: isTarget ? '1px solid rgba(0,0,0,0.2)' : '1px solid rgba(255,255,255,0.1)',
                            paddingTop: '2px',
                            fontWeight: 700,
                          }}
                        >
                          {neighbor.call_number.split(' ')[1] || neighbor.call_number}
                        </div>
                      </div>
                    );
                  })}

                  {/* Right edge indicator */}
                  <div
                    style={{
                      writingMode: 'vertical-rl',
                      fontSize: '0.7rem',
                      color: 'var(--text-muted)',
                      padding: '0 4px',
                      height: '100px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      borderLeft: '2px solid rgba(255,255,255,0.1)',
                      marginLeft: '8px',
                    }}
                  >
                    RIGHT EDGE (Slot 25) ▶
                  </div>
                </div>

                {/* Wooden Shelf Base Beam */}
                <div
                  style={{
                    height: '14px',
                    background: 'linear-gradient(180deg, #78350f 0%, #451a03 100%)',
                    borderRadius: '0 0 6px 6px',
                    borderTop: '2px solid #b45309',
                    boxShadow: '0 4px 6px rgba(0,0,0,0.4)',
                  }}
                />
              </div>

              {/* BOOKCASE ELEVATION & MINI FLOOR MAP */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                  gap: '1rem',
                  marginBottom: '1.25rem',
                }}
              >
                {/* Bookcase Elevation Graphic */}
                <div
                  style={{
                    background: 'rgba(255, 255, 255, 0.02)',
                    border: '1px solid var(--border-color, #374151)',
                    borderRadius: '8px',
                    padding: '1rem',
                  }}
                >
                  <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#e0e7ff', marginBottom: '0.75rem' }}>
                    🏢 {location.bay} Shelf Stack Elevation:
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {[5, 4, 3, 2, 1].map((tierNum) => {
                      const isCurrentTier = tierNum === location.shelf_tier;
                      return (
                        <div
                          key={tierNum}
                          style={{
                            padding: '0.5rem 0.75rem',
                            borderRadius: '6px',
                            background: isCurrentTier
                              ? 'rgba(16, 185, 129, 0.15)'
                              : 'rgba(255, 255, 255, 0.03)',
                            border: isCurrentTier
                              ? '2px solid #10b981'
                              : '1px solid rgba(255, 255, 255, 0.08)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            fontSize: '0.8rem',
                          }}
                        >
                          <span style={{ fontWeight: isCurrentTier ? 700 : 400, color: isCurrentTier ? '#34d399' : 'var(--text-muted)' }}>
                            Tier {tierNum} {tierNum === 4 ? '(Eye Level)' : tierNum === 1 ? '(Bottom)' : ''}
                          </span>
                          {isCurrentTier ? (
                            <span style={{ fontSize: '0.75rem', color: '#34d399', fontWeight: 700 }}>
                              🎯 ACTIVE SHELF (Book #{location.position_from_left})
                            </span>
                          ) : (
                            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>25 books capacity</span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Turn-by-Turn Guidance Steps */}
                <div
                  style={{
                    background: 'rgba(255, 255, 255, 0.02)',
                    border: '1px solid var(--border-color, #374151)',
                    borderRadius: '8px',
                    padding: '1rem',
                  }}
                >
                  <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#e0e7ff', marginBottom: '0.75rem' }}>
                    🚶 Turn-by-Turn Wayfinding Guidance:
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {location.turn_by_turn_directions.map((step, idx) => (
                      <div
                        key={idx}
                        style={{
                          fontSize: '0.8rem',
                          color: idx === location.turn_by_turn_directions.length - 1 ? '#fbbf24' : 'var(--text-muted)',
                          lineHeight: '1.4',
                          fontWeight: idx === location.turn_by_turn_directions.length - 1 ? 600 : 400,
                        }}
                      >
                        {step}
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {missingReportNotice && (
                <div
                  className="alert alert-warning"
                  style={{
                    marginBottom: '1rem',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    fontSize: '0.85rem',
                  }}
                >
                  <span>⚠️</span>
                  <span>{missingReportNotice}</span>
                </div>
              )}

              {/* Footer Actions */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '0.75rem',
                  marginTop: '1.25rem',
                  borderTop: '1px solid var(--border-color, #1f2937)',
                  paddingTop: '1rem',
                }}
              >
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={handleReportMissing}
                  disabled={reportingMissing || !!missingReportNotice}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.4rem',
                    color: '#f59e0b',
                    borderColor: 'rgba(245, 158, 11, 0.4)',
                    fontSize: '0.825rem',
                  }}
                  title="Flag if monograph is physically absent from Tier/Slot to eliminate ghost availability"
                >
                  <span>⚠️</span>
                  <span>
                    {reportingMissing
                      ? 'Logging Notice...'
                      : missingReportNotice
                      ? 'Report Logged ✓'
                      : 'Report Missing from Shelf'}
                  </span>
                </button>

                <div style={{ display: 'flex', gap: '0.75rem' }}>
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => setShowPrintModal(true)}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.4rem',
                      background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                      fontSize: '0.825rem',
                    }}
                  >
                    <span>🖨️</span> Print Spine Labels
                  </button>
                  <button type="button" className="btn btn-secondary" onClick={onClose} style={{ fontSize: '0.825rem' }}>
                    Close Navigator
                  </button>
                </div>
              </div>

              {showPrintModal && (
                <PrintableSpineLabelsModal
                  isOpen={showPrintModal}
                  onClose={() => setShowPrintModal(false)}
                  bookTitle={location.title}
                  author={location.author}
                  category={location.category}
                  callNumber={location.call_number}
                  floorAisle={`FL ${location.floor_number} • ${location.aisle}`}
                  copies={[{ id: location.book_id, copy_code: `BC-${String(location.book_id).padStart(4, '0')}-01` }]}
                />
              )}
            </div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes pulseGlow {
          0% { box-shadow: 0 0 5px rgba(245, 158, 11, 0.3); }
          50% { box-shadow: 0 0 20px rgba(245, 158, 11, 0.8); }
          100% { box-shadow: 0 0 5px rgba(245, 158, 11, 0.3); }
        }
      `}</style>
    </div>
  );
};
