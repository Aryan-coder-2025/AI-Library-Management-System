import React, { useState, useEffect, useRef, useCallback } from 'react';
import { BrowserMultiFormatReader, type IScannerControls } from '@zxing/browser';
import { apiFetch } from '../services/apiClient';
import type { BookDetail, ISBNLookupResult, BookAutoCatalogPayload } from '../types/library';

interface PhysicalBookScannerModalProps {
  isOpen: boolean;
  onClose: () => void;
  onBookAdded: (book: BookDetail) => void;
}

export const PhysicalBookScannerModal: React.FC<PhysicalBookScannerModalProps> = ({
  isOpen,
  onClose,
  onBookAdded,
}) => {
  const [activeTab, setActiveTab] = useState<'camera' | 'manual'>('camera');
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [availableDevices, setAvailableDevices] = useState<MediaDeviceInfo[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>('');

  // Scanning State
  const [scannedBarcode, setScannedBarcode] = useState<string>('');
  const [manualIsbnInput, setManualIsbnInput] = useState<string>('');
  const [isLookingUp, setIsLookingUp] = useState(false);
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [lookupResult, setLookupResult] = useState<ISBNLookupResult | null>(null);

  // Ingestion Form State
  const [title, setTitle] = useState('');
  const [author, setAuthor] = useState('');
  const [category, setCategory] = useState('');
  const [description, setDescription] = useState('');
  const [initialCopies, setInitialCopies] = useState<number>(3);
  const [copyCodePrefix, setCopyCodePrefix] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [catalogSuccess, setCatalogSuccess] = useState<BookDetail | null>(null);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const codeReaderRef = useRef<BrowserMultiFormatReader | null>(null);
  const controlsRef = useRef<IScannerControls | null>(null);

  // Synthesize instant barcode reader audio beep
  const playScannerBeep = useCallback(() => {
    try {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.type = 'sine';
      osc.frequency.setValueAtTime(880, ctx.currentTime);
      gain.gain.setValueAtTime(0.2, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.16);
      osc.start();
      osc.stop(ctx.currentTime + 0.16);
    } catch {
      // Audio context might be restricted before user gesture
    }
  }, []);

  // Initialize camera list
  useEffect(() => {
    if (!isOpen) return;
    navigator.mediaDevices?.enumerateDevices().then((devices) => {
      const videoInputs = devices.filter((d) => d.kind === 'videoinput');
      setAvailableDevices(videoInputs);
      if (videoInputs.length > 0 && !selectedDeviceId) {
        // Prefer environment (back) camera on mobile phones
        const backCam = videoInputs.find((d) => d.label.toLowerCase().includes('back') || d.label.toLowerCase().includes('environment'));
        setSelectedDeviceId(backCam ? backCam.deviceId : videoInputs[0].deviceId);
      }
    }).catch(() => {
      // Ignored
    });
  }, [isOpen, selectedDeviceId]);

  // Start ZXing Camera Stream
  const startCamera = useCallback(async (deviceId?: string) => {
    setCameraError(null);
    setCameraActive(false);

    try {
      if (!codeReaderRef.current) {
        codeReaderRef.current = new BrowserMultiFormatReader();
      }

      if (controlsRef.current) {
        controlsRef.current.stop();
        controlsRef.current = null;
      }

      if (!videoRef.current) return;

      const targetDeviceId = deviceId || selectedDeviceId;
      const constraints: MediaStreamConstraints = {
        video: targetDeviceId
          ? { deviceId: { exact: targetDeviceId } }
          : { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
      };

      const controls = await codeReaderRef.current.decodeFromConstraints(
        constraints,
        videoRef.current,
        (result, err) => {
          if (result) {
            const text = result.getText().trim();
            // Valid barcode detected!
            playScannerBeep();
            setScannedBarcode(text);
            handleLookup(text);
            // Temporarily pause camera once barcode is grabbed
            controls.stop();
            setCameraActive(false);
          }
          if (err && !(err.name === 'NotFoundException')) {
            // normal frame without barcode
          }
        }
      );

      controlsRef.current = controls;
      setCameraActive(true);
    } catch (err: unknown) {
      console.error('Camera initialization failed', err);
      const msg = err instanceof Error ? err.message : 'Could not access camera';
      setCameraError(`Camera Error: ${msg}. You can switch to direct ISBN entry.`);
      setCameraActive(false);
    }
  }, [playScannerBeep, selectedDeviceId]);

  const stopCamera = useCallback(() => {
    if (controlsRef.current) {
      controlsRef.current.stop();
      controlsRef.current = null;
    }
    setCameraActive(false);
  }, []);

  // Manage Camera on tab change or modal open/close
  useEffect(() => {
    if (isOpen && activeTab === 'camera' && !catalogSuccess) {
      startCamera();
    } else {
      stopCamera();
    }
    return () => {
      stopCamera();
    };
  }, [isOpen, activeTab, catalogSuccess, startCamera, stopCamera]);

  // Perform Bibliographic Metadata Lookup
  const handleLookup = async (isbn: string) => {
    const cleaned = isbn.replace(/[\s\-]/g, '');
    if (!cleaned || (cleaned.length !== 10 && cleaned.length !== 13)) {
      setLookupError(`Invalid ISBN '${isbn}'. Expected 10 or 13 digits.`);
      return;
    }

    setIsLookingUp(true);
    setLookupError(null);
    setLookupResult(null);
    setCatalogSuccess(null);

    try {
      const res = await apiFetch<ISBNLookupResult>(`/api/books/lookup-isbn/${cleaned}`);
      setLookupResult(res);
      setTitle(res.title || '');
      setAuthor(res.author || '');
      setCategory(res.category || 'Computer Science');
      setDescription(res.description || '');
      setCopyCodePrefix(res.exists_locally && res.local_book_id ? `BC-${String(res.local_book_id).padStart(4, '0')}` : '');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to query bibliographic records';
      setLookupError(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setIsLookingUp(false);
    }
  };

  // Perform One-Click Auto-Catalog
  const handleAutoCatalog = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!lookupResult) return;

    setIsSubmitting(true);
    setLookupError(null);

    const payload: BookAutoCatalogPayload = {
      isbn: lookupResult.isbn,
      title: title.trim() || lookupResult.title || 'Untitled Monograph',
      author: author.trim() || lookupResult.author || 'Unknown Author',
      category: category.trim() || lookupResult.category || 'Computer Science',
      description: description.trim() || lookupResult.description,
      initial_copies: initialCopies,
      copy_code_prefix: copyCodePrefix.trim() || undefined,
    };

    try {
      const createdBook = await apiFetch<BookDetail>('/api/books/auto-catalog', {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      setCatalogSuccess(createdBook);
      onBookAdded(createdBook);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Auto-cataloging failed';
      setLookupError(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReset = () => {
    setScannedBarcode('');
    setManualIsbnInput('');
    setLookupResult(null);
    setCatalogSuccess(null);
    setLookupError(null);
    if (activeTab === 'camera') {
      startCamera();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop" onClick={onClose} style={{ zIndex: 1100 }}>
      <div
        className="modal-dialog modal-dialog-large"
        onClick={(e) => e.stopPropagation()}
        style={{
          maxWidth: '820px',
          width: '95%',
          background: 'var(--bg-surface, #111827)',
          border: '1px solid var(--border-color, rgba(99, 102, 241, 0.25))',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 35px rgba(99, 102, 241, 0.15)',
        }}
      >
        {/* Header */}
        <div className="modal-header" style={{ borderBottom: '1px solid var(--border-color, #1f2937)', padding: '1.25rem 1.5rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <span style={{ fontSize: '1.4rem' }}>📷</span>
              <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary, #f9fafb)' }}>
                Physical Book Ingestion & Barcode Scanner
              </h3>
            </div>
            <p style={{ margin: '0.25rem 0 0', fontSize: '0.85rem', color: 'var(--text-muted, #9ca3af)' }}>
              Scan ISBN barcodes from physical book covers or enter ISBNs to copy-catalog directly into inventory.
            </p>
          </div>
          <button type="button" className="btn-close" onClick={onClose} style={{ color: 'var(--text-muted)' }}>
            ✕
          </button>
        </div>

        {/* Modal Body */}
        <div className="modal-body" style={{ padding: '1.5rem', maxHeight: '78vh', overflowY: 'auto' }}>
          {/* Tab Selector */}
          {!catalogSuccess && (
            <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.5rem' }}>
              <button
                type="button"
                className={`btn ${activeTab === 'camera' ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => {
                  setActiveTab('camera');
                  setLookupError(null);
                }}
                style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}
              >
                <span>📹</span> Live Camera Barcode Scanner
              </button>
              <button
                type="button"
                className={`btn ${activeTab === 'manual' ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => {
                  setActiveTab('manual');
                  setLookupError(null);
                  stopCamera();
                }}
                style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}
              >
                <span>⌨️</span> Direct ISBN / USB Gun Scanner
              </button>
            </div>
          )}

          {/* Success Screen */}
          {catalogSuccess ? (
            <div style={{ textAlign: 'center', padding: '1.5rem 0' }}>
              <div
                style={{
                  width: '64px',
                  height: '64px',
                  borderRadius: '50%',
                  background: 'rgba(16, 185, 129, 0.15)',
                  color: '#10b981',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '2rem',
                  margin: '0 auto 1.25rem',
                  border: '1px solid rgba(16, 185, 129, 0.3)',
                }}
              >
                ✓
              </div>
              <h3 style={{ fontSize: '1.35rem', margin: '0 0 0.5rem', color: '#10b981' }}>
                Monograph Successfully Accessioned!
              </h3>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem', maxWidth: '560px', margin: '0 auto 1.5rem' }}>
                <strong>{catalogSuccess.title}</strong> by {catalogSuccess.author} is now officially registered in the
                catalogue with <strong>{catalogSuccess.copies?.length || 0} active physical copies</strong>.
              </p>

              {/* Generated Barcodes Table */}
              <div
                style={{
                  background: 'rgba(255, 255, 255, 0.03)',
                  border: '1px solid var(--border-color, #374151)',
                  borderRadius: '8px',
                  padding: '1rem',
                  maxWidth: '560px',
                  margin: '0 auto 1.5rem',
                  textAlign: 'left',
                }}
              >
                <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.6rem' }}>
                  GENERATED ACCESSION BARCODES / ASSET TAGS:
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: '0.5rem' }}>
                  {catalogSuccess.copies?.map((c) => (
                    <div
                      key={c.id}
                      style={{
                        padding: '0.45rem 0.6rem',
                        background: 'rgba(99, 102, 241, 0.1)',
                        border: '1px solid rgba(99, 102, 241, 0.25)',
                        borderRadius: '6px',
                        fontFamily: 'monospace',
                        fontSize: '0.85rem',
                        color: '#a5b4fc',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                      }}
                    >
                      <span>🏷️ {c.copy_code}</span>
                      <span style={{ fontSize: '0.75rem', color: '#10b981' }}>READY</span>
                    </div>
                  ))}
                </div>
              </div>

              <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
                <button type="button" className="btn btn-secondary" onClick={onClose}>
                  Done & Close
                </button>
                <button type="button" className="btn btn-primary" onClick={handleReset}>
                  + Scan Another Physical Book
                </button>
              </div>
            </div>
          ) : (
            <>
              {/* TAB 1: CAMERA SCANNER */}
              {activeTab === 'camera' && (
                <div>
                  <div
                    style={{
                      position: 'relative',
                      width: '100%',
                      height: '320px',
                      background: '#030712',
                      borderRadius: '12px',
                      overflow: 'hidden',
                      border: '2px solid rgba(99, 102, 241, 0.3)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <video
                      ref={videoRef}
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                      muted
                      playsInline
                    />

                    {/* Viewfinder Overlay with Reticle & Animated Laser Line */}
                    <div
                      style={{
                        position: 'absolute',
                        inset: 0,
                        pointerEvents: 'none',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      {/* Barcode Targeting Reticle */}
                      <div
                        style={{
                          width: '260px',
                          height: '140px',
                          border: '2px dashed rgba(99, 102, 241, 0.8)',
                          borderRadius: '8px',
                          position: 'relative',
                          boxShadow: '0 0 20px rgba(99, 102, 241, 0.25)',
                        }}
                      >
                        {/* Red/Cyan Animated Laser Sweep Line */}
                        <div
                          style={{
                            position: 'absolute',
                            left: 0,
                            right: 0,
                            height: '2px',
                            background: '#ef4444',
                            boxShadow: '0 0 10px #ef4444, 0 0 20px #ef4444',
                            animation: 'scannerLaser 2s infinite ease-in-out',
                          }}
                        />
                      </div>
                      <span
                        style={{
                          marginTop: '0.75rem',
                          fontSize: '0.8rem',
                          background: 'rgba(0, 0, 0, 0.75)',
                          padding: '0.3rem 0.75rem',
                          borderRadius: '999px',
                          color: '#e0e7ff',
                          letterSpacing: '0.02em',
                        }}
                      >
                        Align book barcode inside target reticle
                      </span>
                    </div>

                    {/* Camera status badge */}
                    <div
                      style={{
                        position: 'absolute',
                        top: '12px',
                        left: '12px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.4rem',
                        background: 'rgba(0,0,0,0.65)',
                        padding: '0.25rem 0.6rem',
                        borderRadius: '6px',
                        fontSize: '0.75rem',
                      }}
                    >
                      <span
                        style={{
                          width: '8px',
                          height: '8px',
                          borderRadius: '50%',
                          background: cameraActive ? '#10b981' : '#f59e0b',
                        }}
                      />
                      <span>{cameraActive ? 'Camera Active (ZXing Engine)' : 'Starting Camera...'}</span>
                    </div>
                  </div>

                  {/* Camera Controls */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      marginTop: '0.75rem',
                      fontSize: '0.85rem',
                    }}
                  >
                    {availableDevices.length > 1 ? (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <label htmlFor="cam-select" style={{ color: 'var(--text-muted)' }}>
                          Lens:
                        </label>
                        <select
                          id="cam-select"
                          value={selectedDeviceId}
                          onChange={(e) => {
                            setSelectedDeviceId(e.target.value);
                            startCamera(e.target.value);
                          }}
                          className="form-input"
                          style={{ padding: '0.2rem 0.5rem', fontSize: '0.8rem', width: 'auto' }}
                        >
                          {availableDevices.map((d, i) => (
                            <option key={d.deviceId} value={d.deviceId}>
                              {d.label || `Camera ${i + 1}`}
                            </option>
                          ))}
                        </select>
                      </div>
                    ) : (
                      <span style={{ color: 'var(--text-muted)' }}>Hold book back cover ~15-20cm from lens</span>
                    )}

                    {cameraActive && (
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={stopCamera}
                        style={{ padding: '0.25rem 0.65rem', fontSize: '0.8rem' }}
                      >
                        Pause Camera
                      </button>
                    )}
                    {!cameraActive && (
                      <button
                        type="button"
                        className="btn btn-primary"
                        onClick={() => startCamera()}
                        style={{ padding: '0.25rem 0.65rem', fontSize: '0.8rem' }}
                      >
                        Resume Camera
                      </button>
                    )}
                  </div>

                  {cameraError && (
                    <div className="alert alert-error" style={{ marginTop: '0.75rem' }}>
                      <span>{cameraError}</span>
                    </div>
                  )}

                  {scannedBarcode && (
                    <div
                      style={{
                        marginTop: '0.75rem',
                        padding: '0.6rem 0.9rem',
                        background: 'rgba(16, 185, 129, 0.1)',
                        border: '1px solid rgba(16, 185, 129, 0.3)',
                        borderRadius: '6px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                      }}
                    >
                      <span style={{ fontSize: '0.85rem', color: '#10b981' }}>
                        ✓ Barcode Detected: <strong>{scannedBarcode}</strong>
                      </span>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={handleReset}
                        style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem' }}
                      >
                        Rescan
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 2: MANUAL ISBN INPUT */}
              {activeTab === 'manual' && (
                <div>
                  <div className="form-group">
                    <label className="form-label" htmlFor="manual-isbn">
                      Enter Physical Book ISBN-10 or ISBN-13
                    </label>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <input
                        id="manual-isbn"
                        type="text"
                        className="form-input"
                        placeholder="e.g. 9780134685991 (or scan with USB barcode scanner gun)"
                        value={manualIsbnInput}
                        onChange={(e) => setManualIsbnInput(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            handleLookup(manualIsbnInput);
                          }
                        }}
                        autoFocus
                      />
                      <button
                        type="button"
                        className="btn btn-primary"
                        disabled={isLookingUp || !manualIsbnInput.trim()}
                        onClick={() => handleLookup(manualIsbnInput)}
                        style={{ whiteSpace: 'nowrap' }}
                      >
                        {isLookingUp ? 'Searching...' : '🔍 Fetch Metadata'}
                      </button>
                    </div>
                  </div>

                  {/* Sample Books for instant one-click demonstration */}
                  <div style={{ marginTop: '0.75rem' }}>
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                      Quick Demonstration Books (Click to auto-fill):
                    </span>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginTop: '0.4rem' }}>
                      {[
                        { title: 'Effective Java', isbn: '9780134685991' },
                        { title: 'CLRS Algorithms', isbn: '9780262033848' },
                        { title: 'Clean Code', isbn: '9780132350884' },
                        { title: 'Design Patterns', isbn: '9780201633610' },
                        { title: 'The C Programming Language', isbn: '9780131103627' },
                      ].map((preset) => (
                        <button
                          key={preset.isbn}
                          type="button"
                          className="badge badge-neutral"
                          onClick={() => {
                            setManualIsbnInput(preset.isbn);
                            handleLookup(preset.isbn);
                          }}
                          style={{ cursor: 'pointer', border: '1px solid var(--border-color)', padding: '0.3rem 0.6rem' }}
                        >
                          📖 {preset.title}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Status / Errors */}
              {isLookingUp && (
                <div style={{ textAlign: 'center', padding: '1.5rem 0', color: 'var(--text-muted)' }}>
                  <div className="spinner" style={{ margin: '0 auto 0.75rem' }} />
                  <div>Querying Open Library and global bibliographic registries...</div>
                </div>
              )}

              {lookupError && (
                <div className="alert alert-error" style={{ marginTop: '1rem' }}>
                  <span>{lookupError}</span>
                </div>
              )}

              {/* METADATA PREVIEW & AUTO-CATALOG FORM */}
              {lookupResult && (
                <div
                  style={{
                    marginTop: '1.5rem',
                    background: 'rgba(255, 255, 255, 0.02)',
                    border: '1px solid var(--border-color, #374151)',
                    borderRadius: '10px',
                    padding: '1.25rem',
                  }}
                >
                  {lookupResult.exists_locally && (
                    <div
                      className="alert alert-warning"
                      style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}
                    >
                      <span>ℹ️</span>
                      <span>
                        This title already exists in your local library inventory (
                        <strong>
                          {lookupResult.local_available_copies} of {lookupResult.local_total_copies} copies available
                        </strong>
                        ). Accessioning will generate additional physical copy barcodes for this title.
                      </span>
                    </div>
                  )}

                  <div style={{ display: 'flex', gap: '1.25rem', alignItems: 'flex-start', flexWrap: 'wrap' }}>
                    {/* Cover Image Thumbnail */}
                    {lookupResult.cover_url && (
                      <div
                        style={{
                          width: '90px',
                          height: '130px',
                          borderRadius: '6px',
                          overflow: 'hidden',
                          flexShrink: 0,
                          background: '#1f2937',
                          border: '1px solid rgba(255,255,255,0.1)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        <img
                          src={lookupResult.cover_url}
                          alt="Book Cover"
                          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                          onError={(e) => {
                            (e.target as HTMLElement).style.display = 'none';
                          }}
                        />
                      </div>
                    )}

                    {/* Book Metadata Form */}
                    <form onSubmit={handleAutoCatalog} style={{ flex: 1, minWidth: '260px' }}>
                      <div className="form-group" style={{ marginBottom: '0.75rem' }}>
                        <label className="form-label" style={{ fontSize: '0.85rem' }}>
                          Title *
                        </label>
                        <input
                          type="text"
                          className="form-input"
                          value={title}
                          onChange={(e) => setTitle(e.target.value)}
                          required
                        />
                      </div>

                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
                        <div className="form-group" style={{ margin: 0 }}>
                          <label className="form-label" style={{ fontSize: '0.85rem' }}>
                            Author *
                          </label>
                          <input
                            type="text"
                            className="form-input"
                            value={author}
                            onChange={(e) => setAuthor(e.target.value)}
                            required
                          />
                        </div>
                        <div className="form-group" style={{ margin: 0 }}>
                          <label className="form-label" style={{ fontSize: '0.85rem' }}>
                            Discipline / Category *
                          </label>
                          <input
                            type="text"
                            className="form-input"
                            value={category}
                            onChange={(e) => setCategory(e.target.value)}
                            required
                          />
                        </div>
                      </div>

                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
                        <div className="form-group" style={{ margin: 0 }}>
                          <label className="form-label" style={{ fontSize: '0.85rem' }}>
                            ISBN-13
                          </label>
                          <input
                            type="text"
                            className="form-input"
                            value={lookupResult.isbn}
                            readOnly
                            style={{ background: 'rgba(255,255,255,0.05)', color: 'var(--text-muted)' }}
                          />
                        </div>
                        <div className="form-group" style={{ margin: 0 }}>
                          <label className="form-label" style={{ fontSize: '0.85rem' }}>
                            Publisher / Year
                          </label>
                          <input
                            type="text"
                            className="form-input"
                            value={`${lookupResult.publisher || 'Academic Press'} (${lookupResult.publish_year || '2020'})`}
                            readOnly
                            style={{ background: 'rgba(255,255,255,0.05)', color: 'var(--text-muted)' }}
                          />
                        </div>
                      </div>

                      {/* Physical Copies Accession Controls */}
                      <div
                        style={{
                          background: 'rgba(99, 102, 241, 0.08)',
                          border: '1px solid rgba(99, 102, 241, 0.25)',
                          borderRadius: '8px',
                          padding: '0.9rem',
                          marginTop: '1rem',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                          <label style={{ fontSize: '0.9rem', fontWeight: 600, color: '#e0e7ff' }}>
                            Physical Copies to Register:
                          </label>
                          <div style={{ display: 'flex', gap: '0.4rem' }}>
                            {[1, 2, 3, 5].map((num) => (
                              <button
                                key={num}
                                type="button"
                                className={`btn ${initialCopies === num ? 'btn-primary' : 'btn-secondary'}`}
                                onClick={() => setInitialCopies(num)}
                                style={{ padding: '0.2rem 0.55rem', fontSize: '0.8rem' }}
                              >
                                {num}
                              </button>
                            ))}
                          </div>
                        </div>
                        <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                          Each physical copy will be assigned a unique accession barcode and registered in the active shelf database.
                        </span>
                      </div>

                      {/* Action Buttons */}
                      <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end', marginTop: '1.25rem' }}>
                        <button type="button" className="btn btn-secondary" onClick={handleReset}>
                          Cancel
                        </button>
                        <button
                          type="submit"
                          className="btn btn-primary"
                          disabled={isSubmitting || !title.trim() || !author.trim()}
                          style={{
                            background: 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
                            boxShadow: '0 4px 14px rgba(79, 70, 229, 0.4)',
                          }}
                        >
                          {isSubmitting ? 'Accessioning...' : `✓ Ingest & Add ${initialCopies} Copies to Inventory`}
                        </button>
                      </div>
                    </form>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <style>{`
        @keyframes scannerLaser {
          0% { top: 0%; opacity: 0.8; }
          50% { top: 96%; opacity: 1; }
          100% { top: 0%; opacity: 0.8; }
        }
      `}</style>
    </div>
  );
};
