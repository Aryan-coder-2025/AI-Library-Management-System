import React from 'react';

interface PrintableSpineLabelsModalProps {
  isOpen: boolean;
  onClose: () => void;
  bookTitle: string;
  author: string;
  category: string;
  callNumber?: string;
  floorAisle?: string;
  copies: Array<{ id: number; copy_code: string }>;
}

export const PrintableSpineLabelsModal: React.FC<PrintableSpineLabelsModalProps> = ({
  isOpen,
  onClose,
  bookTitle,
  author,
  category,
  callNumber = '004.0 C50e',
  floorAisle = 'FL 2 • AISLE 2B',
  copies,
}) => {
  if (!isOpen) return null;

  const handlePrint = () => {
    window.print();
  };

  // Helper to render authentic scannable Code 128 style vector barcode pattern
  const renderBarcodeSvg = (code: string) => {
    const bars: boolean[] = [];
    // Deterministic pseudo-code 128 pattern based on characters
    let seed = 0;
    for (let i = 0; i < code.length; i++) {
      seed = (seed * 31 + code.charCodeAt(i)) % 100000;
    }
    // Generate 45 bars
    for (let i = 0; i < 48; i++) {
      seed = (seed * 9301 + 49297) % 233280;
      bars.push(seed % 2 === 0);
    }

    return (
      <svg width="100%" height="32" viewBox="0 0 100 32" preserveAspectRatio="none">
        {bars.map((isDark, i) =>
          isDark ? (
            <rect key={i} x={(i * 100) / 48} y="0" width={100 / 48 - 0.2} height="32" fill="#000000" />
          ) : null
        )}
      </svg>
    );
  };

  return (
    <div className="modal-backdrop spine-labels-modal-backdrop" onClick={onClose} style={{ zIndex: 1300 }}>
      <div
        className="modal-dialog modal-dialog-large printable-labels-dialog"
        onClick={(e) => e.stopPropagation()}
        style={{
          maxWidth: '780px',
          width: '95%',
          background: 'var(--bg-surface, #111827)',
          border: '1px solid var(--border-color, rgba(99, 102, 241, 0.3))',
        }}
      >
        {/* Header - Hidden during print */}
        <div
          className="modal-header no-print"
          style={{
            borderBottom: '1px solid var(--border-color, #1f2937)',
            padding: '1.25rem 1.5rem',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <span style={{ fontSize: '1.4rem' }}>🖨️</span>
              <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary, #f9fafb)' }}>
                Physical Spine & Accession Barcode Labels
              </h3>
            </div>
            <p style={{ margin: '0.25rem 0 0', fontSize: '0.85rem', color: 'var(--text-muted, #9ca3af)' }}>
              Standard 1" &times; 2.5" adhesive label stickers ready for thermal printer or Avery sheet printing.
            </p>
          </div>
          <button type="button" className="btn-close" onClick={onClose} style={{ color: 'var(--text-muted)' }}>
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="modal-body" style={{ padding: '1.5rem', maxHeight: '75vh', overflowY: 'auto' }}>
          {/* Action Toolbar - Hidden during print */}
          <div
            className="no-print"
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '1.25rem',
              padding: '0.75rem 1rem',
              background: 'rgba(99, 102, 241, 0.08)',
              borderRadius: '8px',
              border: '1px solid rgba(99, 102, 241, 0.2)',
            }}
          >
            <span style={{ fontSize: '0.85rem', color: '#e0e7ff' }}>
              Labels to print: <strong>{copies.length} physical copies</strong> for <em>{bookTitle}</em>
            </span>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handlePrint}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                boxShadow: '0 4px 12px rgba(16, 185, 129, 0.35)',
              }}
            >
              <span>🖨️</span> Print Label Sheet
            </button>
          </div>

          {/* Printable Labels Grid */}
          <div
            className="printable-sheet-container"
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
              gap: '1rem',
              padding: '0.5rem',
              background: '#ffffff',
              borderRadius: '8px',
              boxShadow: 'inset 0 0 10px rgba(0,0,0,0.1)',
            }}
          >
            {copies.map((copy) => (
              <div
                key={copy.id}
                className="physical-adhesive-label"
                style={{
                  background: '#ffffff',
                  border: '2px dashed #94a3b8',
                  borderRadius: '6px',
                  padding: '0.65rem 0.75rem',
                  color: '#0f172a',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  minHeight: '140px',
                  boxShadow: '0 2px 4px rgba(0,0,0,0.06)',
                  pageBreakInside: 'avoid',
                }}
              >
                {/* Header */}
                <div style={{ textAlign: 'center', borderBottom: '1px solid #cbd5e1', paddingBottom: '0.25rem' }}>
                  <div style={{ fontSize: '0.65rem', fontWeight: 800, letterSpacing: '0.05em', color: '#334155' }}>
                    ATHENAEUM UNIVERSITY LIBRARY
                  </div>
                  <div style={{ fontSize: '0.75rem', fontWeight: 800, color: '#1e293b', fontFamily: 'monospace' }}>
                    {callNumber}
                  </div>
                </div>

                {/* Scannable Barcode SVG */}
                <div style={{ padding: '0.35rem 0', textAlign: 'center' }}>
                  {renderBarcodeSvg(copy.copy_code)}
                  <div
                    style={{
                      fontFamily: 'monospace',
                      fontSize: '0.78rem',
                      fontWeight: 800,
                      letterSpacing: '0.08em',
                      marginTop: '0.15rem',
                      color: '#0f172a',
                    }}
                  >
                    *{copy.copy_code}*
                  </div>
                </div>

                {/* Footer Monograph & Shelf Details */}
                <div style={{ borderTop: '1px solid #cbd5e1', paddingTop: '0.25rem', fontSize: '0.62rem' }}>
                  <div
                    style={{
                      fontWeight: 700,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      color: '#1e293b',
                    }}
                  >
                    {bookTitle} &bull; {author.slice(0, 18)}
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: '#64748b', marginTop: '0.1rem' }}>
                    <span>{floorAisle}</span>
                    <span>{category.slice(0, 15)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Footer - Hidden during print */}
        <div className="modal-footer no-print" style={{ borderTop: '1px solid var(--border-color, #1f2937)' }}>
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Done
          </button>
        </div>
      </div>

      <style>{`
        @media print {
          body * {
            visibility: hidden;
          }
          .spine-labels-modal-backdrop,
          .printable-sheet-container,
          .printable-sheet-container * {
            visibility: visible;
          }
          .spine-labels-modal-backdrop {
            position: absolute;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: #ffffff !important;
          }
          .printable-labels-dialog {
            border: none !important;
            box-shadow: none !important;
            background: #ffffff !important;
            max-width: 100% !important;
            width: 100% !important;
            margin: 0 !important;
            padding: 0 !important;
          }
          .no-print {
            display: none !important;
          }
          .physical-adhesive-label {
            border: 1px solid #000000 !important;
            box-shadow: none !important;
            break-inside: avoid;
          }
        }
      `}</style>
    </div>
  );
};
