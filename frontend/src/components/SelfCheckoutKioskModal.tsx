import React, { useState, useEffect, useRef } from 'react';
import { BrowserMultiFormatReader, type IScannerControls } from '@zxing/browser';
import { apiFetch } from '../services/apiClient';

interface SelfCheckoutKioskModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCheckoutComplete?: () => void;
}

interface SelfCheckoutResponse {
  success: boolean;
  status: 'LOAN_ISSUED' | 'SMART_SWAP_ISSUED' | 'WRONG_BOOK' | 'COPY_RESTRICTED' | 'COPY_UNAVAILABLE';
  message: string;
  loan_id?: number;
  copy_code: string;
  book_title: string;
  student_name: string;
  due_date?: string;
  swap_applied: boolean;
  original_copy_code?: string;
  guidance?: string;
}

export const SelfCheckoutKioskModal: React.FC<SelfCheckoutKioskModalProps> = ({
  isOpen,
  onClose,
  onCheckoutComplete,
}) => {
  const [studentIdInput, setStudentIdInput] = useState('aryan@library.edu');
  const [barcodeInput, setBarcodeInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SelfCheckoutResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Camera
  const [isCameraActive, setIsCameraActive] = useState(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const controlsRef = useRef<IScannerControls | null>(null);

  // Synthesize Web Audio feedback
  const playSound = (type: 'success' | 'swap' | 'error') => {
    try {
      const ctx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);

      if (type === 'success') {
        [523.25, 659.25, 783.99].forEach((f, i) => {
          const o = ctx.createOscillator();
          const g = ctx.createGain();
          o.connect(g);
          g.connect(ctx.destination);
          o.frequency.setValueAtTime(f, ctx.currentTime + i * 0.1);
          g.gain.setValueAtTime(0.12, ctx.currentTime + i * 0.1);
          g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.1 + 0.2);
          o.start(ctx.currentTime + i * 0.1);
          o.stop(ctx.currentTime + i * 0.1 + 0.2);
        });
      } else if (type === 'swap') {
        // Futuristic double-tone
        [440, 880].forEach((f, i) => {
          const o = ctx.createOscillator();
          const g = ctx.createGain();
          o.connect(g);
          g.connect(ctx.destination);
          o.frequency.setValueAtTime(f, ctx.currentTime + i * 0.12);
          g.gain.setValueAtTime(0.15, ctx.currentTime + i * 0.12);
          g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.12 + 0.25);
          o.start(ctx.currentTime + i * 0.12);
          o.stop(ctx.currentTime + i * 0.12 + 0.25);
        });
      } else {
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(260, ctx.currentTime);
        osc.frequency.setValueAtTime(180, ctx.currentTime + 0.15);
        gain.gain.setValueAtTime(0.2, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);
        osc.start();
        osc.stop(ctx.currentTime + 0.4);
      }
    } catch {
      // Audio not supported
    }
  };

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
            handleSelfCheckout(code);
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

  const handleSelfCheckout = async (barcodeToScan?: string) => {
    const code = (barcodeToScan || barcodeInput).trim();
    const student = studentIdInput.trim();

    if (!student) {
      setErrorMsg('Please provide a Student University ID or Email.');
      return;
    }
    if (!code) {
      setErrorMsg('Please scan or enter the book copy barcode.');
      return;
    }

    setLoading(true);
    setErrorMsg(null);

    try {
      const data = await apiFetch<SelfCheckoutResponse>('/api/circulation/self-checkout', {
        method: 'POST',
        body: JSON.stringify({
          student_id_or_email: student,
          copy_code: code,
        }),
      });

      setResult(data);
      setBarcodeInput('');

      if (data.success) {
        if (data.swap_applied) playSound('swap');
        else playSound('success');
        if (onCheckoutComplete) onCheckoutComplete();
      } else {
        playSound('error');
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Self-checkout request failed.';
      setErrorMsg(msg);
      playSound('error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
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
          backgroundColor: '#18181b',
          border: '1px solid #3f3f46',
          borderRadius: '16px',
          width: '100%',
          maxWidth: '820px',
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
            background: 'linear-gradient(180deg, #27272a 0%, #18181b 100%)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ fontSize: '1.6rem' }}>⚡</span>
            <div>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0, color: '#fafafa' }}>
                Express Self-Checkout Kiosk
              </h2>
              <p style={{ margin: '0.2rem 0 0', fontSize: '0.82rem', color: '#a1a1aa' }}>
                Automated circulation with Smart Copy Swapping and Mismatch Guard (Zero Staff Bottleneck).
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
          {/* Step 1: Student Identity Input */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            <label style={{ fontSize: '0.85rem', fontWeight: 600, color: '#d4d4d8' }}>
              👤 Student Identification (University ID or Email):
            </label>
            <input
              type="text"
              placeholder="e.g. aryan@library.edu or Student ID #1"
              value={studentIdInput}
              onChange={(e) => setStudentIdInput(e.target.value)}
              style={{
                background: '#09090b',
                color: '#fafafa',
                border: '1px solid #52525b',
                borderRadius: '8px',
                padding: '0.65rem 0.9rem',
                fontSize: '0.92rem',
              }}
            />
          </div>

          {/* Step 2: Book Barcode Scan Input */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            <label style={{ fontSize: '0.85rem', fontWeight: 600, color: '#d4d4d8' }}>
              📖 Physical Book Barcode in Hand:
            </label>
            <div style={{ display: 'flex', gap: '0.75rem' }}>
              <input
                type="text"
                placeholder="Scan Accession Barcode (BC-XXXX-XX) with USB Gun or Camera..."
                value={barcodeInput}
                onChange={(e) => setBarcodeInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleSelfCheckout();
                  }
                }}
                style={{
                  flex: 1,
                  background: '#09090b',
                  color: '#fafafa',
                  border: '1px solid #52525b',
                  borderRadius: '8px',
                  padding: '0.75rem 0.9rem',
                  fontSize: '0.95rem',
                  fontFamily: 'monospace',
                }}
              />
              <button
                onClick={() => handleSelfCheckout()}
                disabled={loading || !barcodeInput.trim()}
                style={{
                  background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '8px',
                  padding: '0.75rem 1.4rem',
                  fontWeight: 600,
                  cursor: loading || !barcodeInput.trim() ? 'not-allowed' : 'pointer',
                  opacity: loading || !barcodeInput.trim() ? 0.6 : 1,
                }}
              >
                {loading ? 'Checking...' : 'Borrow Book'}
              </button>
              <button
                onClick={() => setIsCameraActive(!isCameraActive)}
                style={{
                  background: isCameraActive ? '#ef4444' : '#27272a',
                  color: '#fafafa',
                  border: '1px solid #52525b',
                  borderRadius: '8px',
                  padding: '0.75rem 1rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                {isCameraActive ? '⏹ Stop' : '📷 Cam'}
              </button>
            </div>
          </div>

          {/* Quick Preset Buttons for Live Demo */}
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ fontSize: '0.78rem', color: '#a1a1aa', fontWeight: 600 }}>Demo Presets:</span>
            <button
              onClick={() => handleSelfCheckout('BC-0001-01')}
              style={{
                background: '#064e3b',
                border: '1px solid #059669',
                color: '#34d399',
                padding: '0.35rem 0.75rem',
                borderRadius: '6px',
                fontSize: '0.78rem',
                cursor: 'pointer',
              }}
            >
              ✓ Standard Self-Checkout (BC-0001-01)
            </button>
            <button
              onClick={() => handleSelfCheckout('BC-0001-02')}
              style={{
                background: '#451a03',
                border: '1px solid #d97706',
                color: '#fbbf24',
                padding: '0.35rem 0.75rem',
                borderRadius: '6px',
                fontSize: '0.78rem',
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              ⚡ Test Smart Copy Swapping (BC-0001-02)
            </button>
            <button
              onClick={() => handleSelfCheckout('BC-0004-01')}
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
              ❌ Test Wrong Title Mismatch
            </button>
          </div>

          {/* Camera Viewfinder */}
          {isCameraActive && (
            <div
              style={{
                position: 'relative',
                borderRadius: '12px',
                overflow: 'hidden',
                border: '2px dashed #10b981',
                background: '#000',
                maxHeight: '200px',
                display: 'flex',
                justifyContent: 'center',
              }}
            >
              <video ref={videoRef} autoPlay playsInline style={{ width: '100%', maxHeight: '200px', objectFit: 'cover' }} />
            </div>
          )}

          {/* Error Notice */}
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

          {/* Result Card */}
          {result && (
            <div
              style={{
                background: result.success
                  ? result.swap_applied
                    ? 'rgba(217, 119, 6, 0.15)'
                    : 'rgba(16, 185, 129, 0.15)'
                  : 'rgba(239, 68, 68, 0.15)',
                border: `2px solid ${
                  result.success ? (result.swap_applied ? '#f59e0b' : '#10b981') : '#ef4444'
                }`,
                borderRadius: '12px',
                padding: '1.25rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.75rem',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span
                  style={{
                    padding: '0.2rem 0.6rem',
                    borderRadius: '999px',
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    background: result.success ? (result.swap_applied ? '#d97706' : '#059669') : '#dc2626',
                    color: '#fff',
                  }}
                >
                  {result.status === 'SMART_SWAP_ISSUED'
                    ? '⚡ Smart Copy Swap Applied'
                    : result.status === 'LOAN_ISSUED'
                    ? '✓ Checkout Complete'
                    : result.status === 'WRONG_BOOK'
                    ? '❌ Wrong Title Detected'
                    : '⚠️ Restricted Copy'}
                </span>
                <span style={{ fontSize: '0.82rem', fontFamily: 'monospace', color: '#d4d4d8' }}>
                  {result.copy_code}
                </span>
              </div>

              <div>
                <h3 style={{ fontSize: '1.15rem', fontWeight: 700, margin: '0.2rem 0 0.1rem', color: '#fafafa' }}>
                  {result.book_title}
                </h3>
                <div style={{ fontSize: '0.82rem', color: '#a1a1aa' }}>
                  Borrower: <strong style={{ color: '#fafafa' }}>{result.student_name}</strong>
                  {result.due_date && (
                    <>
                      {' '}• Due Date: <strong style={{ color: '#38bdf8' }}>{result.due_date}</strong> (14 Days)
                    </>
                  )}
                </div>
              </div>

              <div
                style={{
                  background: 'rgba(0, 0, 0, 0.3)',
                  padding: '0.75rem 1rem',
                  borderRadius: '8px',
                  fontSize: '0.85rem',
                  color: result.success ? '#e4e4e7' : '#fca5a5',
                }}
              >
                {result.message}
              </div>

              {result.guidance && (
                <div
                  style={{
                    background: 'rgba(59, 130, 246, 0.15)',
                    border: '1px solid #1d4ed8',
                    padding: '0.75rem 1rem',
                    borderRadius: '8px',
                    fontSize: '0.82rem',
                    color: '#93c5fd',
                  }}
                >
                  📍 <strong>Return Guidance:</strong> {result.guidance}
                </div>
              )}
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
            Instant atomic checkout • Deactivates RFID exit sensor flag automatically.
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
            Close Kiosk
          </button>
        </div>
      </div>
    </div>
  );
};
