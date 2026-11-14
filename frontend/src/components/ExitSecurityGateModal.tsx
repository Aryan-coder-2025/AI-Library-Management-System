import React, { useState, useEffect, useRef } from 'react';
import { BrowserMultiFormatReader, type IScannerControls } from '@zxing/browser';
import { apiFetch } from '../services/apiClient';

interface ExitSecurityGateModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface GateResult {
  allow_exit: boolean;
  alarm_triggered: boolean;
  status: 'AUTHORIZED_CHECKOUT' | 'UNAUTHORIZED_ALARM' | 'UNKNOWN_ITEM';
  message: string;
  copy_code: string;
  book_title?: string;
  borrower_name?: string;
  borrower_email?: string;
  loan_id?: number;
  due_date?: string;
  timestamp: string;
}

export const ExitSecurityGateModal: React.FC<ExitSecurityGateModalProps> = ({ isOpen, onClose }) => {
  const [barcodeInput, setBarcodeInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [gateResult, setGateResult] = useState<GateResult | null>(null);
  const [gateHistory, setGateHistory] = useState<GateResult[]>([]);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Camera
  const [isCameraActive, setIsCameraActive] = useState(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const controlsRef = useRef<IScannerControls | null>(null);

  // Synthesize Web Audio Sirens / Chimes
  const playSiren = () => {
    try {
      const ctx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sawtooth';
      osc.connect(gain);
      gain.connect(ctx.destination);

      const startTime = ctx.currentTime;
      osc.frequency.setValueAtTime(800, startTime);
      osc.frequency.linearRampToValueAtTime(1200, startTime + 0.2);
      osc.frequency.linearRampToValueAtTime(750, startTime + 0.4);
      osc.frequency.linearRampToValueAtTime(1200, startTime + 0.6);
      osc.frequency.linearRampToValueAtTime(750, startTime + 0.8);
      osc.frequency.linearRampToValueAtTime(1200, startTime + 1.0);

      gain.gain.setValueAtTime(0.25, startTime);
      gain.gain.exponentialRampToValueAtTime(0.001, startTime + 1.2);

      osc.start(startTime);
      osc.stop(startTime + 1.2);
    } catch {
      // AudioContext not supported
    }
  };

  const playAuthorizedChime = () => {
    try {
      const ctx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
      [523.25, 659.25, 783.99].forEach((freq, i) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.frequency.setValueAtTime(freq, ctx.currentTime + i * 0.12);
        gain.gain.setValueAtTime(0.12, ctx.currentTime + i * 0.12);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.12 + 0.25);
        osc.start(ctx.currentTime + i * 0.12);
        osc.stop(ctx.currentTime + i * 0.12 + 0.25);
      });
    } catch {
      // AudioContext not supported
    }
  };

  // Camera lifecycle
  useEffect(() => {
    if (!isOpen || !isCameraActive) {
      if (controlsRef.current) {
        controlsRef.current.stop();
        controlsRef.current = null;
      }
      return;
    }

    const reader = new BrowserMultiFormatReader();
    let isSubscribed = true;

    navigator.mediaDevices?.getUserMedia({ video: { facingMode: 'environment' } })
      .then((stream) => {
        if (!isSubscribed || !videoRef.current) return;
        videoRef.current.srcObject = stream;
        reader.decodeFromVideoElement(videoRef.current, (res) => {
          if (res && isSubscribed) {
            const code = res.getText();
            setBarcodeInput(code);
            handleGateVerification(code);
          }
        }).then((controls) => {
          if (isSubscribed) controlsRef.current = controls;
          else controls.stop();
        });
      })
      .catch((err) => {
        setErrorMsg('Camera access denied: ' + err.message);
        setIsCameraActive(false);
      });

    return () => {
      isSubscribed = false;
      if (controlsRef.current) {
        controlsRef.current.stop();
        controlsRef.current = null;
      }
    };
  }, [isOpen, isCameraActive]);

  if (!isOpen) return null;

  const handleGateVerification = async (codeToVerify?: string) => {
    const code = (codeToVerify || barcodeInput).trim();
    if (!code) return;
    setLoading(true);
    setErrorMsg(null);

    try {
      const data = await apiFetch<GateResult>('/api/circulation/verify-exit-gate', {
        method: 'POST',
        body: JSON.stringify({
          copy_code: code,
        }),
      });

      setGateResult(data);
      setGateHistory((prev) => [data, ...prev]);
      setBarcodeInput('');

      if (data.alarm_triggered) {
        playSiren();
      } else {
        playAuthorizedChime();
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Gate verification failed';
      setErrorMsg(msg);
      playSiren();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.82)',
        backdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1100,
        padding: '1rem',
      }}
    >
      <div
        style={{
          backgroundColor: '#121214',
          border: '1px solid #27272a',
          borderRadius: '16px',
          width: '100%',
          maxWidth: '840px',
          maxHeight: '92vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 25px 60px rgba(0,0,0,0.7)',
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
            background: 'linear-gradient(180deg, #1f1f23 0%, #121214 100%)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ fontSize: '1.6rem' }}>🚨</span>
            <div>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0, color: '#fafafa' }}>
                Library Exit Security & Anti-Theft Sensor Gate
              </h2>
              <p style={{ margin: '0.2rem 0 0', fontSize: '0.82rem', color: '#a1a1aa' }}>
                Simulates real-world RFID & EM exit pedestals: verifies checkout loan status before patrons depart the building.
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
          {/* Visual Security Gate Pedestal Simulation */}
          <div
            style={{
              background: '#09090b',
              border: `2px solid ${
                gateResult?.alarm_triggered
                  ? '#ef4444'
                  : gateResult?.allow_exit
                  ? '#10b981'
                  : '#3b82f6'
              }`,
              borderRadius: '14px',
              padding: '1.5rem',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              position: 'relative',
              overflow: 'hidden',
              boxShadow: gateResult?.alarm_triggered
                ? '0 0 35px rgba(239, 68, 68, 0.35)'
                : gateResult?.allow_exit
                ? '0 0 35px rgba(16, 185, 129, 0.35)'
                : '0 0 20px rgba(59, 130, 246, 0.2)',
              transition: 'all 0.3s ease',
            }}
          >
            {/* Top Status Banner */}
            <div
              style={{
                fontSize: '0.82rem',
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                padding: '0.3rem 0.9rem',
                borderRadius: '999px',
                marginBottom: '1rem',
                background: gateResult?.alarm_triggered
                  ? '#7f1d1d'
                  : gateResult?.allow_exit
                  ? '#064e3b'
                  : '#1e293b',
                color: gateResult?.alarm_triggered
                  ? '#fca5a5'
                  : gateResult?.allow_exit
                  ? '#6ee7b7'
                  : '#94a3b8',
              }}
            >
              {gateResult?.alarm_triggered
                ? '🚨 ALARM TRIPPED — SECURITY LOCK ENGAGED'
                : gateResult?.allow_exit
                ? '✓ CHECKOUT VERIFIED — EXIT UNLOCKED'
                : '• PEDESTAL SENSOR STANDBY •'}
            </div>

            {/* Pedestals Visualization */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '2.5rem',
                width: '100%',
                padding: '1rem 0',
              }}
            >
              {/* Left Pedestal */}
              <div
                style={{
                  width: '32px',
                  height: '140px',
                  background: 'linear-gradient(180deg, #27272a 0%, #18181b 100%)',
                  borderRadius: '6px',
                  border: '1px solid #52525b',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '8px 0',
                }}
              >
                <div
                  style={{
                    width: '14px',
                    height: '14px',
                    borderRadius: '50%',
                    background: gateResult?.alarm_triggered ? '#ef4444' : gateResult?.allow_exit ? '#10b981' : '#3b82f6',
                    boxShadow: `0 0 10px ${gateResult?.alarm_triggered ? '#ef4444' : gateResult?.allow_exit ? '#10b981' : '#3b82f6'}`,
                  }}
                />
                <div style={{ width: '4px', height: '60px', background: '#3f3f46', borderRadius: '2px' }} />
                <div style={{ fontSize: '0.55rem', color: '#71717a', fontWeight: 700 }}>GATE L</div>
              </div>

              {/* Walkway Sensor Field */}
              <div
                style={{
                  flex: 1,
                  maxWidth: '360px',
                  height: '120px',
                  border: `2px dashed ${gateResult?.alarm_triggered ? '#ef4444' : gateResult?.allow_exit ? '#10b981' : '#3f3f46'}`,
                  borderRadius: '10px',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: gateResult?.alarm_triggered
                    ? 'rgba(239, 68, 68, 0.08)'
                    : gateResult?.allow_exit
                    ? 'rgba(16, 185, 129, 0.08)'
                    : 'rgba(255, 255, 255, 0.02)',
                  position: 'relative',
                }}
              >
                <span style={{ fontSize: '2.4rem' }}>
                  {gateResult?.alarm_triggered ? '🚷' : gateResult?.allow_exit ? '🚶‍♂️' : '📡'}
                </span>
                <span style={{ fontSize: '0.75rem', color: '#a1a1aa', marginTop: '0.3rem', fontWeight: 600 }}>
                  {gateResult?.alarm_triggered
                    ? 'Theft Alarm Active'
                    : gateResult?.allow_exit
                    ? 'Turnstile Open'
                    : 'RFID Sensor Zone'}
                </span>
              </div>

              {/* Right Pedestal */}
              <div
                style={{
                  width: '32px',
                  height: '140px',
                  background: 'linear-gradient(180deg, #27272a 0%, #18181b 100%)',
                  borderRadius: '6px',
                  border: '1px solid #52525b',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '8px 0',
                }}
              >
                <div
                  style={{
                    width: '14px',
                    height: '14px',
                    borderRadius: '50%',
                    background: gateResult?.alarm_triggered ? '#ef4444' : gateResult?.allow_exit ? '#10b981' : '#3b82f6',
                    boxShadow: `0 0 10px ${gateResult?.alarm_triggered ? '#ef4444' : gateResult?.allow_exit ? '#10b981' : '#3b82f6'}`,
                  }}
                />
                <div style={{ width: '4px', height: '60px', background: '#3f3f46', borderRadius: '2px' }} />
                <div style={{ fontSize: '0.55rem', color: '#71717a', fontWeight: 700 }}>GATE R</div>
              </div>
            </div>

            {/* Result Message Banner */}
            {gateResult && (
              <div
                style={{
                  marginTop: '0.5rem',
                  padding: '0.6rem 1rem',
                  borderRadius: '8px',
                  fontSize: '0.85rem',
                  textAlign: 'center',
                  fontWeight: 600,
                  color: gateResult.alarm_triggered ? '#fca5a5' : '#6ee7b7',
                }}
              >
                {gateResult.message}
              </div>
            )}
          </div>

          {/* Scanner Input & Camera Controls */}
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            <div style={{ flex: 1, position: 'relative' }}>
              <input
                type="text"
                placeholder="Scan Accession Barcode passing sensor gate (BC-XXXX-XX)..."
                value={barcodeInput}
                onChange={(e) => setBarcodeInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleGateVerification();
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
                Enter ↵
              </span>
            </div>

            <button
              onClick={() => handleGateVerification()}
              disabled={loading || !barcodeInput.trim()}
              style={{
                background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                color: '#fff',
                border: 'none',
                borderRadius: '10px',
                padding: '0.8rem 1.4rem',
                fontWeight: 600,
                cursor: loading || !barcodeInput.trim() ? 'not-allowed' : 'pointer',
                opacity: loading || !barcodeInput.trim() ? 0.6 : 1,
              }}
            >
              {loading ? 'Checking...' : 'Check Sensor'}
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
              {isCameraActive ? '⏹ Stop' : '📷 Cam'}
            </button>
          </div>

          {/* Quick Preset Buttons for Live Demo */}
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ fontSize: '0.78rem', color: '#a1a1aa', fontWeight: 600 }}>Demo Presets:</span>
            <button
              onClick={() => handleGateVerification('BC-0001-01')}
              style={{
                background: '#450a0a',
                border: '1px solid #dc2626',
                color: '#f87171',
                padding: '0.35rem 0.75rem',
                borderRadius: '6px',
                fontSize: '0.78rem',
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              🚨 Simulate Theft (Unborrowed Book Alarm)
            </button>
            <button
              onClick={() => handleGateVerification('BC-0002-01')}
              style={{
                background: '#064e3b',
                border: '1px solid #10b981',
                color: '#34d399',
                padding: '0.35rem 0.75rem',
                borderRadius: '6px',
                fontSize: '0.78rem',
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              ✓ Test Borrower Gate Pass
            </button>
            <button
              onClick={() => handleGateVerification('TAG-RANDOM-999')}
              style={{
                background: '#27272a',
                border: '1px solid #52525b',
                color: '#e4e4e7',
                padding: '0.35rem 0.75rem',
                borderRadius: '6px',
                fontSize: '0.78rem',
                cursor: 'pointer',
              }}
            >
              ⚪ Unregistered RFID Tag
            </button>
          </div>

          {/* Camera Viewfinder */}
          {isCameraActive && (
            <div
              style={{
                position: 'relative',
                borderRadius: '12px',
                overflow: 'hidden',
                border: '2px dashed #3b82f6',
                background: '#000',
                maxHeight: '200px',
                display: 'flex',
                justifyContent: 'center',
              }}
            >
              <video ref={videoRef} autoPlay playsInline style={{ width: '100%', maxHeight: '200px', objectFit: 'cover' }} />
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

          {/* Gate Crossings History Log */}
          {gateHistory.length > 0 && (
            <div>
              <h4 style={{ fontSize: '0.92rem', fontWeight: 600, margin: '0 0 0.5rem', color: '#d4d4d8' }}>
                📋 Sensor Crossings Log ({gateHistory.length} events)
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
                      <th style={{ padding: '0.4rem 0.6rem' }}>Timestamp</th>
                      <th style={{ padding: '0.4rem 0.6rem' }}>Barcode</th>
                      <th style={{ padding: '0.4rem 0.6rem' }}>Monograph</th>
                      <th style={{ padding: '0.4rem 0.6rem' }}>Borrower / Status</th>
                      <th style={{ padding: '0.4rem 0.6rem' }}>Gate Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {gateHistory.map((h, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid #18181b' }}>
                        <td style={{ padding: '0.4rem 0.6rem', color: '#71717a' }}>{h.timestamp}</td>
                        <td style={{ padding: '0.4rem 0.6rem', fontFamily: 'monospace' }}>{h.copy_code}</td>
                        <td style={{ padding: '0.4rem 0.6rem', fontWeight: 600 }}>{h.book_title || '—'}</td>
                        <td style={{ padding: '0.4rem 0.6rem', color: '#a1a1aa' }}>
                          {h.borrower_name ? `${h.borrower_name} (Loan #${h.loan_id})` : 'Unborrowed Item'}
                        </td>
                        <td style={{ padding: '0.4rem 0.6rem' }}>
                          <span
                            style={{
                              padding: '0.15rem 0.4rem',
                              borderRadius: '4px',
                              fontSize: '0.72rem',
                              fontWeight: 700,
                              background: h.alarm_triggered ? '#7f1d1d' : '#064e3b',
                              color: h.alarm_triggered ? '#fca5a5' : '#6ee7b7',
                            }}
                          >
                            {h.alarm_triggered ? '🚨 ALARM TRIPPED' : '✓ UNLOCKED'}
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
            background: '#121214',
          }}
        >
          <div style={{ fontSize: '0.78rem', color: '#71717a' }}>
            Unchecked items log security alarm events in <code>inventory_events</code>.
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
            Close Simulator
          </button>
        </div>
      </div>
    </div>
  );
};
