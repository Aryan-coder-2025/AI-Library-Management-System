import React, { useState, useEffect, useRef } from 'react';
import { BrowserMultiFormatReader, type IScannerControls } from '@zxing/browser';
import { apiFetch } from '../services/apiClient';

interface ShelfReadingAuditModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface AuditRecord {
  id: string;
  time: string;
  copy_code: string;
  book_title: string;
  category: string;
  dewey_call_number: string;
  audited_aisle: string;
  expected_floor: number;
  expected_aisle: string;
  expected_bay: string;
  expected_tier: string;
  expected_slot: number;
  status: 'verified_in_place' | 'misplaced' | 'recovered' | 'not_found';
  message: string;
  reshelved?: boolean;
}

const AISLE_OPTIONS = [
  { code: 'Aisle 1A', name: 'Aisle 1A — Mathematics (Floor 1)', dewey: '510.0' },
  { code: 'Aisle 1B', name: 'Aisle 1B — Physics (Floor 1)', dewey: '530.0' },
  { code: 'Aisle 1C', name: 'Aisle 1C — Philosophy of Technology (Floor 1)', dewey: '601.0' },
  { code: 'Aisle 2A', name: 'Aisle 2A — Computer Science (Floor 2)', dewey: '004.0' },
  { code: 'Aisle 2B', name: 'Aisle 2B — Software Engineering (Floor 2)', dewey: '005.1' },
  { code: 'Aisle 2C', name: 'Aisle 2C — Algorithms & Complexity (Floor 2)', dewey: '005.11' },
  { code: 'Aisle 2D', name: 'Aisle 2D — Artificial Intelligence (Floor 2)', dewey: '006.3' },
  { code: 'Aisle 3A', name: 'Aisle 3A — Distributed Systems (Floor 3)', dewey: '004.36' },
  { code: 'Aisle 3B', name: 'Aisle 3B — Cybersecurity & Cryptography (Floor 3)', dewey: '005.8' },
];

export const ShelfReadingAuditModal: React.FC<ShelfReadingAuditModalProps> = ({ isOpen, onClose }) => {
  const [selectedAisle, setSelectedAisle] = useState('Aisle 1A');
  const [barcodeInput, setBarcodeInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [activeResult, setActiveResult] = useState<AuditRecord | null>(null);
  const [auditLog, setAuditLog] = useState<AuditRecord[]>([]);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Camera scanner
  const [isCameraActive, setIsCameraActive] = useState(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const controlsRef = useRef<IScannerControls | null>(null);

  // Synthesize Web Audio beeps
  const playAudioTone = (type: 'success' | 'alert' | 'celebrate') => {
    try {
      const ctx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);

      if (type === 'success') {
        osc.frequency.setValueAtTime(880, ctx.currentTime);
        gain.gain.setValueAtTime(0.12, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.15);
        osc.start();
        osc.stop(ctx.currentTime + 0.15);
      } else if (type === 'alert') {
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(320, ctx.currentTime);
        osc.frequency.setValueAtTime(220, ctx.currentTime + 0.12);
        gain.gain.setValueAtTime(0.2, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
        osc.start();
        osc.stop(ctx.currentTime + 0.35);
      } else {
        // Celebrate
        [523.25, 659.25, 783.99, 1046.5].forEach((freq, idx) => {
          const subOsc = ctx.createOscillator();
          const subGain = ctx.createGain();
          subOsc.connect(subGain);
          subGain.connect(ctx.destination);
          subOsc.frequency.setValueAtTime(freq, ctx.currentTime + idx * 0.08);
          subGain.gain.setValueAtTime(0.1, ctx.currentTime + idx * 0.08);
          subGain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + idx * 0.08 + 0.12);
          subOsc.start(ctx.currentTime + idx * 0.08);
          subOsc.stop(ctx.currentTime + idx * 0.08 + 0.12);
        });
      }
    } catch {
      // AudioContext not permitted or supported
    }
  };

  // Start / stop camera
  useEffect(() => {
    if (!isOpen || !isCameraActive) {
      if (controlsRef.current) {
        controlsRef.current.stop();
        controlsRef.current = null;
      }
      return;
    }

    const codeReader = new BrowserMultiFormatReader();
    let isSubscribed = true;

    navigator.mediaDevices?.getUserMedia({ video: { facingMode: 'environment' } })
      .then((stream) => {
        if (!isSubscribed || !videoRef.current) return;
        videoRef.current.srcObject = stream;
        codeReader.decodeFromVideoElement(videoRef.current, (result) => {
          if (result && isSubscribed) {
            const text = result.getText();
            setBarcodeInput(text);
            handleAuditScan(text);
          }
        }).then((controls) => {
          if (isSubscribed) controlsRef.current = controls;
          else controls.stop();
        });
      })
      .catch((err) => {
        setErrorMsg('Camera access denied or unavailable: ' + err.message);
        setIsCameraActive(false);
      });

    return () => {
      isSubscribed = false;
      if (controlsRef.current) {
        controlsRef.current.stop();
        controlsRef.current = null;
      }
    };
  }, [isOpen, isCameraActive, selectedAisle]);

  if (!isOpen) return null;

  const handleAuditScan = async (codeToScan?: string) => {
    const targetCode = (codeToScan || barcodeInput).trim();
    if (!targetCode) return;
    setLoading(true);
    setErrorMsg(null);

    try {
      const data = await apiFetch<AuditRecord>('/api/books/shelf-audit', {
        method: 'POST',
        body: JSON.stringify({
          audited_aisle: selectedAisle,
          barcode: targetCode,
        }),
      });

      const record: AuditRecord = {
        ...data,
        id: Math.random().toString(36).substring(2, 9),
        time: new Date().toLocaleTimeString(),
      };

      setActiveResult(record);
      setAuditLog((prev) => [record, ...prev]);
      setBarcodeInput('');

      if (record.status === 'verified_in_place') playAudioTone('success');
      else if (record.status === 'recovered') playAudioTone('celebrate');
      else playAudioTone('alert');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Scan failed or book not found in inventory.';
      setErrorMsg(msg);
      playAudioTone('alert');
    } finally {
      setLoading(false);
    }
  };

  const handleRouteToReshelvingCart = async (copyCode: string) => {
    try {
      await apiFetch('/api/books/reshelve-action', {
        method: 'POST',
        body: JSON.stringify({
          copy_code: copyCode,
          action: 'route_to_cart',
        }),
      });
      playAudioTone('success');
      if (activeResult && activeResult.copy_code === copyCode) {
        setActiveResult({ ...activeResult, reshelved: true });
      }
      setAuditLog((prev) =>
        prev.map((item) => (item.copy_code === copyCode ? { ...item, reshelved: true } : item))
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to route to cart';
      setErrorMsg(msg);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.78)',
        backdropFilter: 'blur(6px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1100,
        padding: '1rem',
      }}
    >
      <div
        style={{
          backgroundColor: '#18181b',
          border: '1px solid #3f3f46',
          borderRadius: '16px',
          width: '100%',
          maxWidth: '860px',
          maxHeight: '92vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 25px 60px rgba(0,0,0,0.6)',
          color: '#f4f4f5',
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '1.25rem 1.5rem',
            borderBottom: '1px solid #27272a',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'linear-gradient(180deg, #27272a 0%, #18181b 100%)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ fontSize: '1.6rem' }}>🔍</span>
            <div>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0, color: '#fafafa' }}>
                Shelf-Reading & Misplaced Monograph Audit
              </h2>
              <p style={{ margin: '0.2rem 0 0', fontSize: '0.82rem', color: '#a1a1aa' }}>
                Simulate physical stacks inventory verification: scans verify placement, detect misplaced monographs, and route items to reshelving carts.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#a1a1aa',
              fontSize: '1.4rem',
              cursor: 'pointer',
              padding: '0.3rem',
            }}
          >
            ✕
          </button>
        </div>

        {/* Content Body */}
        <div style={{ padding: '1.5rem', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Step 1: Active Aisle Selector */}
          <div
            style={{
              background: '#27272a',
              borderRadius: '12px',
              padding: '1rem 1.25rem',
              border: '1px solid #3f3f46',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.5rem',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <label style={{ fontSize: '0.88rem', fontWeight: 600, color: '#e4e4e7' }}>
                📍 Currently Audited Stacks Aisle:
              </label>
              <span style={{ fontSize: '0.75rem', color: '#10b981', fontWeight: 600, background: '#064e3b', padding: '0.2rem 0.6rem', borderRadius: '999px' }}>
                Active Shelf Inspection Mode
              </span>
            </div>
            <select
              value={selectedAisle}
              onChange={(e) => setSelectedAisle(e.target.value)}
              style={{
                background: '#18181b',
                color: '#fafafa',
                border: '1px solid #52525b',
                borderRadius: '8px',
                padding: '0.65rem 0.9rem',
                fontSize: '0.95rem',
                fontWeight: 600,
              }}
            >
              {AISLE_OPTIONS.map((a) => (
                <option key={a.code} value={a.code}>
                  {a.name} (Dewey {a.dewey})
                </option>
              ))}
            </select>
          </div>

          {/* Step 2: Scanner Input (Barcode Wedge / Camera) */}
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            <div style={{ flex: 1, position: 'relative' }}>
              <input
                type="text"
                placeholder="Scan Accession Barcode (BC-XXXX-XX) or ISBN with USB Gun / Camera..."
                value={barcodeInput}
                onChange={(e) => setBarcodeInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleAuditScan();
                  }
                }}
                style={{
                  width: '100%',
                  background: '#09090b',
                  color: '#fafafa',
                  border: '1px solid #52525b',
                  borderRadius: '10px',
                  padding: '0.8rem 1rem',
                  fontSize: '0.95rem',
                  fontFamily: 'monospace',
                }}
              />
              <span
                style={{
                  position: 'absolute',
                  right: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  fontSize: '0.75rem',
                  color: '#71717a',
                  background: '#27272a',
                  padding: '0.2rem 0.5rem',
                  borderRadius: '4px',
                }}
              >
                Press Enter ↵
              </span>
            </div>

            <button
              onClick={() => handleAuditScan()}
              disabled={loading || !barcodeInput.trim()}
              style={{
                background: 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)',
                color: '#fff',
                border: 'none',
                borderRadius: '10px',
                padding: '0.8rem 1.4rem',
                fontWeight: 600,
                cursor: loading || !barcodeInput.trim() ? 'not-allowed' : 'pointer',
                opacity: loading || !barcodeInput.trim() ? 0.6 : 1,
              }}
            >
              {loading ? 'Auditing...' : 'Audit Scan'}
            </button>

            <button
              onClick={() => setIsCameraActive(!isCameraActive)}
              style={{
                background: isCameraActive ? '#ef4444' : '#27272a',
                color: '#fafafa',
                border: '1px solid #52525b',
                borderRadius: '10px',
                padding: '0.8rem 1.1rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              {isCameraActive ? '⏹ Stop Cam' : '📷 Camera'}
            </button>
          </div>

          {/* Quick Preset Buttons for Live Viva Demo */}
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ fontSize: '0.78rem', color: '#a1a1aa', fontWeight: 600 }}>Demo Presets:</span>
            <button
              onClick={() => {
                setSelectedAisle('Aisle 1A');
                handleAuditScan('BC-0001-01');
              }}
              style={{
                background: '#1c1917',
                border: '1px solid #44403c',
                color: '#f59e0b',
                padding: '0.35rem 0.7rem',
                borderRadius: '6px',
                fontSize: '0.78rem',
                cursor: 'pointer',
              }}
            >
              ⚡ Test In-Place Match
            </button>
            <button
              onClick={() => {
                // Set aisle to Mathematics, but scan a CS book
                setSelectedAisle('Aisle 1A');
                handleAuditScan('BC-0002-01');
              }}
              style={{
                background: '#450a0a',
                border: '1px solid #991b1b',
                color: '#f87171',
                padding: '0.35rem 0.7rem',
                borderRadius: '6px',
                fontSize: '0.78rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              🚨 Simulate Misplaced Monograph
            </button>
            <button
              onClick={() => {
                setSelectedAisle('Aisle 2B');
                handleAuditScan('9780134685991'); // Effective Java
              }}
              style={{
                background: '#064e3b',
                border: '1px solid #059669',
                color: '#34d399',
                padding: '0.35rem 0.7rem',
                borderRadius: '6px',
                fontSize: '0.78rem',
                cursor: 'pointer',
              }}
            >
              ⚡ Scan ISBN (Effective Java)
            </button>
          </div>

          {/* Live Camera Viewfinder */}
          {isCameraActive && (
            <div
              style={{
                position: 'relative',
                borderRadius: '12px',
                overflow: 'hidden',
                border: '2px dashed #10b981',
                background: '#000',
                maxHeight: '220px',
                display: 'flex',
                justifyContent: 'center',
              }}
            >
              <video ref={videoRef} autoPlay playsInline style={{ width: '100%', maxHeight: '220px', objectFit: 'cover' }} />
              <div
                style={{
                  position: 'absolute',
                  inset: '25% 15%',
                  border: '2px solid rgba(16, 185, 129, 0.8)',
                  borderRadius: '8px',
                  boxShadow: '0 0 15px rgba(16, 185, 129, 0.4)',
                  pointerEvents: 'none',
                }}
              />
            </div>
          )}

          {/* Error Message */}
          {errorMsg && (
            <div
              style={{
                background: '#450a0a',
                border: '1px solid #7f1d1d',
                color: '#fca5a5',
                borderRadius: '8px',
                padding: '0.75rem 1rem',
                fontSize: '0.85rem',
              }}
            >
              ⚠️ {errorMsg}
            </div>
          )}

          {/* Active Result Card */}
          {activeResult && (
            <div
              style={{
                background:
                  activeResult.status === 'verified_in_place'
                    ? 'rgba(6, 78, 59, 0.4)'
                    : activeResult.status === 'recovered'
                    ? 'rgba(76, 29, 149, 0.4)'
                    : 'rgba(127, 29, 29, 0.4)',
                border: `2px solid ${
                  activeResult.status === 'verified_in_place'
                    ? '#10b981'
                    : activeResult.status === 'recovered'
                    ? '#a855f7'
                    : '#ef4444'
                }`,
                borderRadius: '14px',
                padding: '1.25rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.75rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span
                      style={{
                        padding: '0.2rem 0.6rem',
                        borderRadius: '999px',
                        fontSize: '0.75rem',
                        fontWeight: 700,
                        textTransform: 'uppercase',
                        background:
                          activeResult.status === 'verified_in_place'
                            ? '#10b981'
                            : activeResult.status === 'recovered'
                            ? '#a855f7'
                            : '#ef4444',
                        color: '#fff',
                      }}
                    >
                      {activeResult.status === 'verified_in_place'
                        ? '✓ Verified In Place'
                        : activeResult.status === 'recovered'
                        ? '🎉 Missing Item Recovered'
                        : '🚨 Misplaced Monograph'}
                    </span>
                    <span style={{ fontSize: '0.82rem', fontFamily: 'monospace', color: '#d4d4d8' }}>
                      {activeResult.copy_code}
                    </span>
                  </div>
                  <h3 style={{ fontSize: '1.15rem', fontWeight: 700, margin: '0.4rem 0 0.1rem', color: '#fafafa' }}>
                    {activeResult.book_title}
                  </h3>
                  <div style={{ fontSize: '0.82rem', color: '#a1a1aa' }}>
                    Call Mark: <strong style={{ color: '#fbbf24' }}>{activeResult.dewey_call_number}</strong> • Category: {activeResult.category}
                  </div>
                </div>

                {activeResult.status === 'misplaced' && !activeResult.reshelved && (
                  <button
                    onClick={() => handleRouteToReshelvingCart(activeResult.copy_code)}
                    style={{
                      background: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
                      color: '#000',
                      border: 'none',
                      borderRadius: '8px',
                      padding: '0.6rem 1rem',
                      fontWeight: 700,
                      fontSize: '0.85rem',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.4rem',
                    }}
                  >
                    <span>📦</span> Route to Reshelving Cart
                  </button>
                )}

                {activeResult.reshelved && (
                  <span
                    style={{
                      background: '#064e3b',
                      color: '#34d399',
                      padding: '0.4rem 0.8rem',
                      borderRadius: '8px',
                      fontSize: '0.82rem',
                      fontWeight: 600,
                    }}
                  >
                    ✓ Loaded on Cart #1
                  </span>
                )}
              </div>

              <div
                style={{
                  background: 'rgba(0, 0, 0, 0.3)',
                  padding: '0.75rem 1rem',
                  borderRadius: '8px',
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                  gap: '0.5rem',
                  fontSize: '0.82rem',
                }}
              >
                <div>
                  <span style={{ color: '#a1a1aa' }}>Audited Location: </span>
                  <strong style={{ color: activeResult.status === 'misplaced' ? '#f87171' : '#34d399' }}>
                    {activeResult.audited_aisle}
                  </strong>
                </div>
                <div>
                  <span style={{ color: '#a1a1aa' }}>Home Location: </span>
                  <strong style={{ color: '#38bdf8' }}>{activeResult.expected_aisle} (Floor {activeResult.expected_floor})</strong>
                </div>
                <div>
                  <span style={{ color: '#a1a1aa' }}>Shelf Micro-Slot: </span>
                  <strong style={{ color: '#fbbf24' }}>
                    {activeResult.expected_bay} • {activeResult.expected_tier} • Slot #{activeResult.expected_slot}
                  </strong>
                </div>
              </div>

              <p style={{ margin: 0, fontSize: '0.85rem', color: '#e4e4e7' }}>{activeResult.message}</p>
            </div>
          )}

          {/* Audit Session History Table */}
          {auditLog.length > 0 && (
            <div>
              <h4 style={{ fontSize: '0.92rem', fontWeight: 600, margin: '0 0 0.5rem', color: '#d4d4d8' }}>
                📋 Session Shelf-Reading Log ({auditLog.length} items scanned)
              </h4>
              <div
                style={{
                  maxHeight: '160px',
                  overflowY: 'auto',
                  border: '1px solid #3f3f46',
                  borderRadius: '8px',
                  background: '#09090b',
                }}
              >
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid #27272a', color: '#a1a1aa', textAlign: 'left' }}>
                      <th style={{ padding: '0.4rem 0.6rem' }}>Time</th>
                      <th style={{ padding: '0.4rem 0.6rem' }}>Copy Code</th>
                      <th style={{ padding: '0.4rem 0.6rem' }}>Title</th>
                      <th style={{ padding: '0.4rem 0.6rem' }}>Scanned In</th>
                      <th style={{ padding: '0.4rem 0.6rem' }}>Belongs In</th>
                      <th style={{ padding: '0.4rem 0.6rem' }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditLog.map((log) => (
                      <tr key={log.id} style={{ borderBottom: '1px solid #18181b' }}>
                        <td style={{ padding: '0.4rem 0.6rem', color: '#71717a' }}>{log.time}</td>
                        <td style={{ padding: '0.4rem 0.6rem', fontFamily: 'monospace' }}>{log.copy_code}</td>
                        <td style={{ padding: '0.4rem 0.6rem', fontWeight: 600 }}>{log.book_title}</td>
                        <td style={{ padding: '0.4rem 0.6rem', color: '#a1a1aa' }}>{log.audited_aisle}</td>
                        <td style={{ padding: '0.4rem 0.6rem', color: '#38bdf8' }}>{log.expected_aisle}</td>
                        <td style={{ padding: '0.4rem 0.6rem' }}>
                          <span
                            style={{
                              padding: '0.15rem 0.4rem',
                              borderRadius: '4px',
                              fontSize: '0.72rem',
                              fontWeight: 600,
                              background:
                                log.status === 'verified_in_place'
                                  ? '#064e3b'
                                  : log.status === 'recovered'
                                  ? '#4c1d95'
                                  : '#450a0a',
                              color:
                                log.status === 'verified_in_place'
                                  ? '#34d399'
                                  : log.status === 'recovered'
                                  ? '#c084fc'
                                  : '#f87171',
                            }}
                          >
                            {log.reshelved ? 'Cart Routed' : log.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: '1rem 1.5rem',
            borderTop: '1px solid #27272a',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: '#18181b',
          }}
        >
          <div style={{ fontSize: '0.78rem', color: '#71717a' }}>
            Audits update <code>inventory_events</code> and reconcile physical stacks layout drift.
          </div>
          <button
            onClick={onClose}
            style={{
              background: '#27272a',
              color: '#f4f4f5',
              border: '1px solid #3f3f46',
              borderRadius: '8px',
              padding: '0.6rem 1.2rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Close Audit Session
          </button>
        </div>
      </div>
    </div>
  );
};
