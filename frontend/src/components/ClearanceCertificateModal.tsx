import React, { useEffect, useState } from 'react';
import type { CirculationClearanceStatus } from '../types/library';

interface ClearanceCertificateModalProps {
  onClose: () => void;
  onInitiateReturn?: (loanId: number, bookTitle: string, copyCode: string) => void;
}

export const ClearanceCertificateModal: React.FC<ClearanceCertificateModalProps> = ({
  onClose,
  onInitiateReturn,
}) => {
  const [clearance, setClearance] = useState<CirculationClearanceStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchClearance = async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await fetch('/api/circulation/clearance/my-status');
        if (!res.ok) {
          throw new Error('Failed to retrieve circulation clearance status.');
        }
        const data: CirculationClearanceStatus = await res.json();
        setClearance(data);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Error fetching clearance';
        setError(msg);
      } finally {
        setLoading(false);
      }
    };

    fetchClearance();
  }, []);

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 1050, display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(8, 13, 26, 0.8)', backdropFilter: 'blur(4px)', padding: '1rem' }}>
      <div style={{ background: '#0e1626', border: '1px solid rgba(56, 189, 248, 0.35)', borderRadius: '16px', width: '100%', maxWidth: '540px', overflow: 'hidden', boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7)' }}>
        
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1rem 1.25rem', borderBottom: '1px solid rgba(255, 255, 255, 0.08)', background: '#080d1a' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '1.25rem' }}>{clearance?.is_fully_cleared ? '🎓' : 'ℹ️'}</span>
            <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: '#f8fafc' }}>
              {clearance?.is_fully_cleared ? 'Library No-Dues Clearance Certificate' : 'Academic Circulation Status Advisory'}
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: '#94a3b8', fontSize: '1.25rem', cursor: 'pointer', padding: '0.25rem', lineHeight: 1 }}
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: '1.25rem' }}>
          {loading && (
            <div style={{ padding: '3rem 1rem', textAlign: 'center', color: '#94a3b8' }}>
              <div className="loading-spinner" style={{ margin: '0 auto 0.75rem' }} />
              <p style={{ fontSize: '0.85rem' }}>Verifying institutional loan status...</p>
            </div>
          )}

          {error && (
            <div className="alert alert-error" style={{ fontSize: '0.85rem' }}>
              {error}
            </div>
          )}

          {clearance && clearance.is_fully_cleared && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {/* Certificate Paper */}
              <div
                style={{
                  background: '#ffffff',
                  color: '#0f172a',
                  borderRadius: '12px',
                  padding: '1.5rem',
                  fontFamily: 'system-ui, sans-serif',
                  border: '3px double #cbd5e1',
                  boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.2)',
                  position: 'relative',
                }}
              >
                {/* Institutional Crest */}
                <div style={{ textAlign: 'center', borderBottom: '2px solid #0f172a', paddingBottom: '0.75rem', marginBottom: '1rem' }}>
                  <div style={{ fontSize: '1.75rem', marginBottom: '0.2rem' }}>🏛️</div>
                  <div style={{ fontSize: '0.75rem', fontWeight: 800, letterSpacing: '0.12em', color: '#1e3a8a', textTransform: 'uppercase' }}>
                    ATHENAEUM UNIVERSITY ACADEMIC LIBRARY
                  </div>
                  <h3 style={{ margin: '0.25rem 0', fontSize: '1.2rem', fontWeight: 800, color: '#0f172a' }}>
                    Certificate of Library Clearance
                  </h3>
                  <div style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 500 }}>
                    Official Institutional "No Dues" Statement
                  </div>
                </div>

                {/* Certificate Body */}
                <div style={{ fontSize: '0.85rem', lineHeight: 1.6, color: '#334155', marginBottom: '1.25rem' }}>
                  This certifies that <strong>{clearance.patron_name}</strong> (Role: <span style={{ textTransform: 'capitalize' }}>{clearance.patron_role}</span>, ID #{clearance.patron_id}) has successfully returned all borrowed monographs and currently holds <strong>zero outstanding liabilities</strong> with the library circulation division.
                </div>

                {/* Status Badges Grid */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem', background: '#f8fafc', padding: '0.75rem', borderRadius: '8px', border: '1px solid #e2e8f0', marginBottom: '1rem', textAlign: 'center' }}>
                  <div>
                    <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', color: '#64748b', fontWeight: 600 }}>Active Loans</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#059669' }}>0</div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', color: '#64748b', fontWeight: 600 }}>Overdue Items</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#059669' }}>0</div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', color: '#64748b', fontWeight: 600 }}>Account Status</div>
                    <div style={{ fontSize: '0.85rem', fontWeight: 800, color: '#059669', marginTop: '0.15rem' }}>CLEAR ✓</div>
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', borderTop: '1px dashed #cbd5e1', paddingTop: '0.75rem', fontSize: '0.72rem', color: '#64748b' }}>
                  <div>
                    <div>Verification Date: {new Date(clearance.generated_at).toLocaleDateString()}</div>
                    <div>Digital Signature: Verified by Athenaeum ILS</div>
                  </div>
                  <div style={{ textAlign: 'right', fontWeight: 700, color: '#1e3a8a' }}>
                    ACADEMIC AFFAIRS COMPLIANT
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => window.print()}
                  style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.8rem' }}
                >
                  <span>🖨️</span>
                  <span>Print Certificate</span>
                </button>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={onClose}
                  style={{ fontSize: '0.8rem' }}
                >
                  Close
                </button>
              </div>
            </div>
          )}

          {clearance && !clearance.is_fully_cleared && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {/* Non-punitive Advisory Box */}
              <div
                style={{
                  background: 'rgba(37, 99, 235, 0.08)',
                  border: '1px solid rgba(56, 189, 248, 0.4)',
                  borderRadius: '12px',
                  padding: '1.25rem',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                  <span style={{ fontSize: '1.25rem' }}>ℹ️</span>
                  <strong style={{ fontSize: '0.95rem', color: '#f8fafc' }}>
                    {clearance.status_headline}
                  </strong>
                </div>
                <p style={{ margin: 0, fontSize: '0.825rem', color: '#cbd5e1', lineHeight: 1.5 }}>
                  {clearance.advisory_message}
                </p>

                <div style={{ marginTop: '0.75rem', padding: '0.5rem 0.75rem', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: '6px', fontSize: '0.75rem', color: '#34d399' }}>
                  ✓ <strong>Institutional Guarantee:</strong> Library borrowings never block exam eligibility, coursework submission, or lecture attendance.
                </div>
              </div>

              {/* Outstanding Items List */}
              <div>
                <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.9rem', color: '#f8fafc' }}>
                  Active Borrowed Monographs ({clearance.active_items.length})
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {clearance.active_items.map((item) => (
                    <div
                      key={item.loan_id}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '0.65rem 0.85rem',
                        background: '#080d1a',
                        border: '1px solid rgba(255, 255, 255, 0.08)',
                        borderRadius: '8px',
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: 600, fontSize: '0.85rem', color: '#f8fafc' }}>
                          {item.book_title}
                        </div>
                        <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                          Barcode: <span style={{ fontFamily: 'monospace' }}>{item.copy_code}</span> | Due: {new Date(item.due_date).toLocaleDateString()}
                        </div>
                      </div>
                      {onInitiateReturn && (
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => {
                            onClose();
                            onInitiateReturn(item.loan_id, item.book_title, item.copy_code);
                          }}
                          style={{ fontSize: '0.75rem', whiteSpace: 'nowrap' }}
                        >
                          ↩ Initiate Return
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={onClose}
                  style={{ fontSize: '0.8rem' }}
                >
                  Dismiss Advisory
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

