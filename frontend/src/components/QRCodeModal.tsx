import React, { useEffect, useState } from 'react';
import QRCode from 'qrcode';
import type { ReservationQRResponse } from '../types/library';

interface QRCodeModalProps {
  qrData: ReservationQRResponse;
  onClose: () => void;
}

export const QRCodeModal: React.FC<QRCodeModalProps> = ({ qrData, onClose }) => {
  const [qrDataUrl, setQrDataUrl] = useState<string | null>(null);
  const [copySuccess, setCopySuccess] = useState(false);
  const [renderError, setRenderError] = useState<string | null>(null);

  useEffect(() => {
    QRCode.toDataURL(qrData.qr_token, {
      width: 240,
      margin: 2,
      color: {
        dark: '#1e293b',
        light: '#ffffff',
      },
    })
      .then((url) => {
        setQrDataUrl(url);
      })
      .catch((err) => {
        setRenderError(err instanceof Error ? err.message : 'Failed to generate QR image');
      });
  }, [qrData.qr_token]);

  const handleCopy = () => {
    navigator.clipboard.writeText(qrData.qr_token).then(() => {
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 2500);
    });
  };

  const formatDate = (isoStr: string) => {
    try {
      const d = new Date(isoStr);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ', ' + d.toLocaleDateString([], { month: 'short', day: 'numeric' });
    } catch {
      return isoStr;
    }
  };

  // Determine window status
  const now = new Date();
  const winStart = new Date(qrData.checkin_window_start);
  const winEnd = new Date(qrData.checkin_window_end);
  let statusBadge = { text: 'Upcoming Window', color: 'badge-secondary' };
  if (now >= winStart && now <= winEnd) {
    statusBadge = { text: 'Check-In Window Open Now', color: 'badge-success' };
  } else if (now > winEnd) {
    statusBadge = { text: 'Grace Window Closed', color: 'badge-danger' };
  }

  return (
    <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div
        className="modal-card"
        style={{ maxWidth: '440px', textAlign: 'center' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header" style={{ justifyContent: 'space-between', display: 'flex', alignItems: 'center' }}>
          <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 600 }}>Study Space QR Pass</h3>
          <button type="button" className="btn-close" onClick={onClose} aria-label="Close modal">
            ✕
          </button>
        </div>

        <div style={{ marginTop: '1rem', marginBottom: '0.75rem' }}>
          <span className={`badge ${statusBadge.color}`} style={{ fontSize: '0.85rem', padding: '0.35rem 0.75rem' }}>
            {statusBadge.text}
          </span>
        </div>

        <div style={{ fontWeight: 600, fontSize: '1.1rem', color: 'var(--text-primary)', marginBottom: '0.25rem' }}>
          {qrData.resource_name}
        </div>
        <div style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1.25rem' }}>
          {formatDate(qrData.start_time)} – {formatDate(qrData.end_time)}
        </div>

        {/* QR Code Container */}
        <div
          style={{
            background: '#ffffff',
            padding: '1rem',
            borderRadius: '12px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
            display: 'inline-block',
            marginBottom: '1rem',
          }}
        >
          {qrDataUrl ? (
            <img
              src={qrDataUrl}
              alt={`QR Check-in Pass for Reservation #${qrData.reservation_id}`}
              style={{ width: '220px', height: '220px', display: 'block' }}
            />
          ) : renderError ? (
            <div style={{ color: 'var(--danger-color)', padding: '2rem' }}>{renderError}</div>
          ) : (
            <div style={{ padding: '2rem', color: 'var(--text-muted)' }}>Generating QR pass...</div>
          )}
        </div>

        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '1rem', lineHeight: '1.4' }}>
          <div>
            <strong>Check-in Window:</strong> {formatDate(qrData.checkin_window_start)} to {formatDate(qrData.checkin_window_end)}
          </div>
          <div>Present this code at the kiosk scanner or library staff desk.</div>
        </div>

        {/* Manual Token String */}
        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'center', marginBottom: '1rem' }}>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={handleCopy}
            title="Copy cryptographic token for desk check-in"
          >
            {copySuccess ? '✓ Copied Token' : 'Copy Check-In Token'}
          </button>
        </div>

        <div className="modal-footer" style={{ justifyContent: 'center' }}>
          <button type="button" className="btn btn-primary" onClick={onClose} style={{ width: '100%' }}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
};

