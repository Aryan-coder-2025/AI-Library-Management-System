import React, { useEffect, useState } from 'react';
import QRCode from 'qrcode';
import type { BookReturnPass } from '../types/library';

interface QRReturnModalProps {
  loanId: number;
  bookTitle: string;
  copyCode?: string;
  onClose: () => void;
  onCancelled?: () => void;
}

export const QRReturnModal: React.FC<QRReturnModalProps> = ({
  loanId,
  bookTitle,
  copyCode,
  onClose,
  onCancelled,
}) => {
  const [pass, setPass] = useState<BookReturnPass | null>(null);
  const [qrDataUrl, setQrDataUrl] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<boolean>(false);
  const [cancelling, setCancelling] = useState<boolean>(false);

  useEffect(() => {
    const fetchPass = async () => {
      try {
        setLoading(true);
        setError(null);
        const csrfToken = document.cookie
          .split('; ')
          .find((row) => row.startsWith('csrf_token='))
          ?.split('=')[1] || '';

        const res = await fetch(`/api/circulation/qr-return/pass/${loanId}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': csrfToken,
          },
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || 'Failed to generate return clearance pass.');
        }

        const data: BookReturnPass = await res.json();
        setPass(data);

        // Generate QR code
        const url = await QRCode.toDataURL(data.qr_payload, {
          width: 240,
          margin: 2,
          color: {
            dark: '#0f172a',
            light: '#ffffff',
          },
        });
        setQrDataUrl(url);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Error creating return pass';
        setError(msg);
      } finally {
        setLoading(false);
      }
    };

    fetchPass();
  }, [loanId]);

  const handleCancelPass = async () => {
    try {
      setCancelling(true);
      const csrfToken = document.cookie
        .split('; ')
        .find((row) => row.startsWith('csrf_token='))
        ?.split('=')[1] || '';

      await fetch(`/api/circulation/qr-return/cancel/${loanId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken,
        },
      });

      if (onCancelled) onCancelled();
      onClose();
    } catch {
      onClose();
    } finally {
      setCancelling(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 animate-in fade-in duration-200" style={{ position: 'fixed', inset: 0, zIndex: 1050, display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(8, 13, 26, 0.8)', backdropFilter: 'blur(4px)' }}>
      <div style={{ background: '#0e1626', border: '1px solid rgba(56, 189, 248, 0.35)', borderRadius: '16px', width: '100%', maxWidth: '440px', overflow: 'hidden', boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7)' }}>
        
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1rem 1.25rem', borderBottom: '1px solid rgba(255, 255, 255, 0.08)', background: '#080d1a' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '1.25rem' }}>↩</span>
            <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: '#f8fafc' }}>
              Book Return Clearance Pass
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
        <div style={{ padding: '1.25rem', textAlign: 'center' }}>
          {loading && (
            <div style={{ padding: '3rem 1rem', color: '#94a3b8' }}>
              <div className="loading-spinner" style={{ margin: '0 auto 1rem' }} />
              <p style={{ fontSize: '0.85rem' }}>Generating secure return clearance pass...</p>
            </div>
          )}

          {error && (
            <div className="alert alert-error" style={{ margin: '1rem 0', textAlign: 'left', fontSize: '0.85rem' }}>
              <strong>Could not generate pass:</strong>
              <div>{error}</div>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={onClose}
                style={{ marginTop: '0.75rem', width: '100%' }}
              >
                Close
              </button>
            </div>
          )}

          {pass && qrDataUrl && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <span style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#38bdf8', fontWeight: 700 }}>
                  Return at Circulation Desk
                </span>
                <h4 style={{ margin: '0.25rem 0', fontSize: '1rem', fontWeight: 700, color: '#f8fafc' }}>
                  {bookTitle}
                </h4>
                <p style={{ margin: 0, fontSize: '0.8rem', color: '#94a3b8' }}>
                  Copy Barcode: <span style={{ fontFamily: 'monospace', color: '#38bdf8', fontWeight: 600 }}>{pass.copy_code || copyCode}</span>
                </p>
              </div>

              {/* Unique Return Token Box */}
              <div
                style={{
                  background: 'rgba(37, 99, 235, 0.12)',
                  border: '1.5px solid rgba(56, 189, 248, 0.45)',
                  borderRadius: '12px',
                  padding: '0.85rem 1rem',
                  textAlign: 'center',
                }}
              >
                <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#94a3b8', fontWeight: 600 }}>
                  Unique Return Token for Librarian
                </div>
                <div
                  style={{
                    fontSize: '1.6rem',
                    fontFamily: 'monospace',
                    fontWeight: 800,
                    letterSpacing: '0.1em',
                    color: '#38bdf8',
                    margin: '0.35rem 0',
                  }}
                >
                  {pass.raw_code}
                </div>
                <button
                  type="button"
                  onClick={() => {
                    navigator.clipboard.writeText(pass.raw_code);
                    setCopied(true);
                    setTimeout(() => setCopied(false), 2000);
                  }}
                  style={{
                    padding: '0.35rem 0.85rem',
                    fontSize: '0.75rem',
                    borderRadius: '6px',
                    background: copied ? '#059669' : '#17233d',
                    color: '#f8fafc',
                    border: '1px solid #334155',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                  }}
                >
                  {copied ? '✓ Token Copied!' : '📋 Copy Return Token'}
                </button>
              </div>

              {/* QR Code */}
              <div style={{ padding: '0.75rem', background: '#ffffff', borderRadius: '14px', display: 'inline-block', margin: '0 auto' }}>
                <img src={qrDataUrl} alt="Return QR Code" style={{ width: '180px', height: '180px', display: 'block' }} />
              </div>

              <div style={{ background: '#080d1a', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '10px', padding: '0.75rem 1rem', textAlign: 'left', fontSize: '0.78rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                  <span style={{ color: '#94a3b8' }}>Borrower:</span>
                  <span style={{ color: '#f8fafc', fontWeight: 600 }}>{pass.patron_name}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                  <span style={{ color: '#94a3b8' }}>Pass Valid Until:</span>
                  <span style={{ color: '#10b981', fontWeight: 600 }}>
                    {new Date(pass.expires_at).toLocaleDateString()}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#94a3b8' }}>Discharge Action:</span>
                  <span style={{ color: '#38bdf8' }}>Check-in & Immediate Clearance</span>
                </div>
              </div>

              <p style={{ margin: 0, fontSize: '0.76rem', color: '#94a3b8', lineHeight: 1.4 }}>
                Present this pass or read out your token code <strong>{pass.raw_code}</strong> at the circulation desk. Once the librarian receives the book, your loan will be discharged and your receipt issued.
              </p>

              <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.25rem' }}>
                <button
                  type="button"
                  onClick={handleCancelPass}
                  disabled={cancelling}
                  className="btn btn-secondary btn-sm"
                  style={{ flex: 1, fontSize: '0.78rem' }}
                >
                  {cancelling ? 'Cancelling...' : 'Cancel Pass (Keep Book)'}
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  className="btn btn-primary btn-sm"
                  style={{ flex: 1, fontSize: '0.78rem' }}
                >
                  Done
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

