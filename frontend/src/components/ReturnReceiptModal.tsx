import React, { useEffect, useState } from 'react';
import type { BookReturnReceipt } from '../types/library';

interface ReturnReceiptModalProps {
  loanId: number;
  onClose: () => void;
}

export const ReturnReceiptModal: React.FC<ReturnReceiptModalProps> = ({ loanId, onClose }) => {
  const [receipt, setReceipt] = useState<BookReturnReceipt | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchReceipt = async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await fetch(`/api/circulation/receipt/${loanId}`);
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || 'Failed to retrieve return receipt.');
        }
        const data: BookReturnReceipt = await res.json();
        setReceipt(data);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Error fetching receipt';
        setError(msg);
      } finally {
        setLoading(false);
      }
    };

    fetchReceipt();
  }, [loanId]);

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 1050, display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(8, 13, 26, 0.8)', backdropFilter: 'blur(4px)', padding: '1rem' }}>
      <div style={{ background: '#0e1626', border: '1px solid rgba(56, 189, 248, 0.35)', borderRadius: '16px', width: '100%', maxWidth: '480px', overflow: 'hidden', boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7)' }}>
        
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1rem 1.25rem', borderBottom: '1px solid rgba(255, 255, 255, 0.08)', background: '#080d1a' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '1.2rem' }}>📄</span>
            <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: '#f8fafc' }}>
              Official Return Clearance Slip
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
            <div style={{ padding: '2.5rem 1rem', textAlign: 'center', color: '#94a3b8' }}>
              <div className="loading-spinner" style={{ margin: '0 auto 0.75rem' }} />
              <p style={{ fontSize: '0.85rem' }}>Retrieving verified return clearance record...</p>
            </div>
          )}

          {error && (
            <div className="alert alert-error" style={{ fontSize: '0.85rem' }}>
              {error}
            </div>
          )}

          {receipt && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {/* Receipt Paper Card */}
              <div
                style={{
                  background: '#ffffff',
                  color: '#0f172a',
                  borderRadius: '12px',
                  padding: '1.25rem',
                  fontFamily: 'system-ui, sans-serif',
                  boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.2)',
                  border: '1px dashed #cbd5e1',
                }}
              >
                {/* Institution Branding */}
                <div style={{ textAlign: 'center', borderBottom: '1.5px solid #0f172a', paddingBottom: '0.75rem', marginBottom: '0.75rem' }}>
                  <div style={{ fontSize: '0.7rem', fontWeight: 800, letterSpacing: '0.12em', color: '#2563eb', textTransform: 'uppercase' }}>
                    ATHENAEUM ACADEMIC PLATFORM
                  </div>
                  <h4 style={{ margin: '0.15rem 0', fontSize: '1.1rem', fontWeight: 800, color: '#0f172a' }}>
                    Circulation Return Receipt
                  </h4>
                  <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
                    Official Discharge & Liability Clearance
                  </div>
                </div>

                {/* Receipt Code Banner */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#f1f5f9', padding: '0.5rem 0.75rem', borderRadius: '6px', marginBottom: '0.85rem' }}>
                  <div>
                    <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', color: '#64748b', fontWeight: 600 }}>Receipt ID</div>
                    <div style={{ fontFamily: 'monospace', fontWeight: 800, fontSize: '0.95rem', color: '#0f172a' }}>{receipt.receipt_code}</div>
                  </div>
                  <span style={{ background: '#dcfce7', color: '#15803d', fontWeight: 700, fontSize: '0.7rem', padding: '0.2rem 0.5rem', borderRadius: '4px', textTransform: 'uppercase' }}>
                    ✓ DISCHARGED
                  </span>
                </div>

                {/* Details Table */}
                <div style={{ fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: '0.4rem', borderBottom: '1px solid #e2e8f0', paddingBottom: '0.75rem', marginBottom: '0.75rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#64748b' }}>Patron Name:</span>
                    <span style={{ fontWeight: 600 }}>{receipt.patron_name}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#64748b' }}>Monograph Title:</span>
                    <span style={{ fontWeight: 600, textAlign: 'right', maxWidth: '240px' }}>{receipt.book_title}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#64748b' }}>Copy Barcode:</span>
                    <span style={{ fontFamily: 'monospace', fontWeight: 600 }}>{receipt.copy_code}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#64748b' }}>Issue Date:</span>
                    <span>{new Date(receipt.issued_at).toLocaleDateString()}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#64748b' }}>Return Discharge Time:</span>
                    <span style={{ fontWeight: 600, color: '#059669' }}>
                      {new Date(receipt.returned_at).toLocaleString()}
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#64748b' }}>Discharging Officer:</span>
                    <span>{receipt.discharged_by_name || 'Circulation Desk Staff'}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#64748b' }}>Physical Condition:</span>
                    <span style={{ fontWeight: 600, color: receipt.condition === 'good' ? '#15803d' : '#b45309' }}>
                      {receipt.condition === 'good' ? 'Intact / Normal Shelf Stock' : 'Flagged for Maintenance'}
                    </span>
                  </div>
                </div>

                <div style={{ fontSize: '0.68rem', color: '#64748b', textAlign: 'center', lineHeight: 1.4 }}>
                  This official electronic clearance confirms the physical return of this monograph to library holdings.
                  The patron holds zero outstanding liabilities for Loan #{receipt.loan_id}.
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
                  <span>Print Slip</span>
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
        </div>
      </div>
    </div>
  );
};

