import React, { useState, useEffect, useRef } from 'react';
import type { VisionResearchResponse } from '../types/library';

interface VisionSearchModalProps {
  onClose: () => void;
  onSelectBook?: (bookId: number) => void;
}

export const VisionSearchModal: React.FC<VisionSearchModalProps> = ({
  onClose,
  onSelectBook,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [fileCategory, setFileCategory] = useState<'image' | 'audio' | 'document'>('image');
  const [userQuery, setUserQuery] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<VisionResearchResponse | null>(null);
  const [isDragging, setIsDragging] = useState<boolean>(false);

  // Audio Recording State
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [recordingSeconds, setRecordingSeconds] = useState<number>(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const recordTimerRef = useRef<NodeJS.Timeout | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const triggerFilePicker = (acceptType?: string) => {
    if (fileInputRef.current) {
      if (acceptType) {
        fileInputRef.current.accept = acceptType;
      } else {
        fileInputRef.current.accept = 'image/png,image/jpeg,image/webp,audio/*,application/pdf,.docx,.pptx';
      }
      fileInputRef.current.click();
    }
  };

  useEffect(() => {
    return () => {
      if (recordTimerRef.current) clearInterval(recordTimerRef.current);
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  // Clipboard Paste Support (Ctrl+V) for screenshots
  useEffect(() => {
    const handlePaste = (e: ClipboardEvent) => {
      const items = e.clipboardData?.items;
      if (!items) return;
      for (let i = 0; i < items.length; i++) {
        if (items[i].type.indexOf('image') !== -1) {
          const file = items[i].getAsFile();
          if (file) {
            handleFileSelect(file);
            break;
          }
        }
      }
    };

    window.addEventListener('paste', handlePaste);
    return () => window.removeEventListener('paste', handlePaste);
  }, []);

  const handleFileSelect = (file: File) => {
    const fn = file.name.toLowerCase();
    const mime = (file.type || '').toLowerCase();

    let cat: 'image' | 'audio' | 'document' = 'image';
    if (mime.startsWith('audio/') || fn.endsWith('.mp3') || fn.endsWith('.wav') || fn.endsWith('.m4a') || fn.endsWith('.webm') || fn.endsWith('.ogg')) {
      cat = 'audio';
    } else if (mime === 'application/pdf' || fn.endsWith('.pdf') || fn.endsWith('.docx') || fn.endsWith('.pptx')) {
      cat = 'document';
    } else if (mime.startsWith('image/') || fn.endsWith('.png') || fn.endsWith('.jpg') || fn.endsWith('.jpeg') || fn.endsWith('.webp')) {
      cat = 'image';
    } else {
      setError('Please upload an Image (PNG, JPG, WEBP), Audio (MP3, WAV, WEBM, M4A), PDF, Word (.docx), or PowerPoint (.pptx).');
      return;
    }

    if (file.size > 25 * 1024 * 1024) {
      setError('File size must be under 25MB.');
      return;
    }

    setError(null);
    setSelectedFile(file);
    setFileCategory(cat);

    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    setResults(null);
  };

  const startVoiceRecording = async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          audioChunksRef.current.push(e.data);
        }
      };

      mediaRecorder.onstop = () => {
        const mime = mediaRecorder.mimeType || 'audio/webm';
        const blob = new Blob(audioChunksRef.current, { type: mime });
        const ext = mime.includes('mp4') ? 'm4a' : 'webm';
        const audioFile = new File([blob], `lecture-recording-${Date.now()}.${ext}`, { type: mime });
        handleFileSelect(audioFile);
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.start(250);
      setIsRecording(true);
      setRecordingSeconds(0);
      recordTimerRef.current = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
      }, 1000);
    } catch (err: any) {
      setError(`Microphone access error: ${err.message || 'Microphone unavailable'}. Please check browser permissions.`);
    }
  };

  const stopVoiceRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (recordTimerRef.current) {
        clearInterval(recordTimerRef.current);
        recordTimerRef.current = null;
      }
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setError('Please select, drop, paste, or record media to analyze.');
      return;
    }

    setLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', selectedFile);
    if (userQuery.trim()) {
      formData.append('query', userQuery.trim());
    }

    try {
      const csrfToken = document.cookie
        .split('; ')
        .find((row) => row.startsWith('csrf_token='))
        ?.split('=')[1] || '';

      const customKey = typeof window !== 'undefined' ? localStorage.getItem('patron_custom_gemini_key') : null;
      const headers: Record<string, string> = {};
      if (csrfToken) headers['X-CSRF-Token'] = csrfToken;
      if (customKey) headers['X-Gemini-API-Key'] = customKey.trim();

      const res = await fetch('/api/research/vision-search', {
        method: 'POST',
        headers,
        credentials: 'include',
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Multimodal analysis request failed.');
      }

      const data: VisionResearchResponse = await res.json();
      setResults(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error processing media.';
      setError(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setLoading(false);
    }
  };

  const clearSelection = () => {
    setSelectedFile(null);
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      setPreviewUrl(null);
    }
    setResults(null);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const formatTimer = (totalSecs: number) => {
    const mins = Math.floor(totalSecs / 60);
    const secs = totalSecs % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1050,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'rgba(8, 13, 26, 0.88)',
        backdropFilter: 'blur(8px)',
        padding: '1.25rem',
      }}
    >
      <div
        style={{
          background: '#0e1626',
          border: '1px solid rgba(56, 189, 248, 0.35)',
          borderRadius: '16px',
          width: '100%',
          maxWidth: '860px',
          maxHeight: '94vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.75)',
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '1.15rem 1.5rem',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            background: '#080d1a',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <span style={{ fontSize: '1.5rem' }}>⚡</span>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.18rem', fontWeight: 700, color: '#f8fafc' }}>
                Multimodal Omnichannel AI Research Discovery
              </h3>
              <p style={{ margin: '2px 0 0 0', fontSize: '0.78rem', color: '#94a3b8' }}>
                Images & Screenshots (<kbd style={{ background: '#1e293b', padding: '1px 4px', borderRadius: '4px' }}>Ctrl+V</kbd>), Audio Lecture Recordings, Research PDFs, Word (.docx) & Slides (.pptx)
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="btn btn-secondary btn-sm"
            style={{ padding: '0.25rem 0.6rem', color: '#94a3b8' }}
          >
            ✕
          </button>
        </div>

        {/* Scrollable Content */}
        <div style={{ padding: '1.5rem', overflowY: 'auto', flex: 1 }}>
          {error && (
            <div className="alert alert-error" style={{ marginBottom: '1.25rem' }}>
              <span>{error}</span>
            </div>
          )}

          {!results ? (
            <form onSubmit={handleAnalyze} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              {/* Media Selection Zone */}
              <div
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onClick={() => !selectedFile && !isRecording && fileInputRef.current?.click()}
                style={{
                  border: isDragging ? '2px dashed #38bdf8' : '2px dashed rgba(56, 189, 248, 0.3)',
                  borderRadius: '12px',
                  padding: '1.5rem',
                  textAlign: 'center',
                  background: isDragging ? 'rgba(56, 189, 248, 0.08)' : 'rgba(15, 23, 42, 0.6)',
                  cursor: selectedFile || isRecording ? 'default' : 'pointer',
                  transition: 'all 0.2s ease',
                  position: 'relative',
                }}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/png,image/jpeg,image/webp,audio/*,application/pdf,.docx,.pptx"
                  style={{ display: 'none' }}
                  onChange={(e) => e.target.files?.[0] && handleFileSelect(e.target.files[0])}
                />

                {isRecording ? (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.75rem', padding: '1rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ display: 'inline-block', width: '12px', height: '12px', borderRadius: '50%', background: '#ef4444', animation: 'pulse 1s infinite' }} />
                      <span style={{ color: '#ef4444', fontWeight: 700, fontSize: '1.1rem' }}>RECORDING AUDIO... {formatTimer(recordingSeconds)}</span>
                    </div>
                    <p style={{ color: '#94a3b8', fontSize: '0.85rem', margin: 0 }}>
                      Speak your question or play the lecture audio clip clearly into your microphone
                    </p>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        stopVoiceRecording();
                      }}
                      className="btn btn-primary"
                      style={{ background: '#ef4444', borderColor: '#dc2626', marginTop: '0.5rem' }}
                    >
                      ⏹️ Stop & Prepare Audio
                    </button>
                  </div>
                ) : selectedFile ? (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.75rem' }}>
                    {fileCategory === 'image' && previewUrl && (
                      <img
                        src={previewUrl}
                        alt="Preview"
                        style={{
                          maxHeight: '220px',
                          maxWidth: '100%',
                          borderRadius: '8px',
                          border: '1px solid rgba(255, 255, 255, 0.1)',
                          objectFit: 'contain',
                        }}
                      />
                    )}
                    {fileCategory === 'audio' && previewUrl && (
                      <div style={{ width: '100%', maxWidth: '400px', margin: '0.5rem 0' }}>
                        <div style={{ fontSize: '0.85rem', color: '#38bdf8', marginBottom: '0.25rem', fontWeight: 600 }}>
                          🎙️ Audio Clip Preview ({selectedFile.name}):
                        </div>
                        <audio controls src={previewUrl} style={{ width: '100%' }} />
                      </div>
                    )}
                    {fileCategory === 'document' && (
                      <div style={{ padding: '1.5rem', background: '#080d1a', borderRadius: '8px', border: '1px solid #1e293b' }}>
                        <span style={{ fontSize: '2.5rem' }}>📄</span>
                        <div style={{ color: '#f8fafc', fontWeight: 600, marginTop: '0.5rem' }}>{selectedFile.name}</div>
                        <div style={{ color: '#64748b', fontSize: '0.75rem' }}>{(selectedFile.size / 1024).toFixed(1)} KB</div>
                      </div>
                    )}

                    <div style={{ display: 'flex', gap: '0.65rem', alignItems: 'center', marginTop: '0.25rem', flexWrap: 'wrap', justifyContent: 'center' }}>
                      <span style={{ fontSize: '0.85rem', color: '#f8fafc', fontWeight: 600 }}>
                        {selectedFile.name} ({(selectedFile.size / (1024 * 1024)).toFixed(2)} MB)
                      </span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          triggerFilePicker();
                        }}
                        className="btn btn-secondary btn-xs"
                      >
                        📁 Choose Different File
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          clearSelection();
                        }}
                        className="btn btn-secondary btn-xs"
                        style={{ color: '#f87171', borderColor: 'rgba(239, 68, 68, 0.4)' }}
                      >
                        ✕ Remove
                      </button>
                    </div>
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.65rem' }}>
                    <div style={{ display: 'flex', gap: '1rem', fontSize: '2.2rem', marginBottom: '0.2rem' }}>
                      <span title="Images & Diagrams">📸</span>
                      <span title="Lecture Voice Notes">🎙️</span>
                      <span title="PDF Research Papers">📄</span>
                      <span title="PowerPoint Slides & Word">📊</span>
                    </div>

                    <div style={{ color: '#f1f5f9', fontWeight: 700, fontSize: '1.05rem' }}>
                      Choose Files from your Laptop, Drop Here, or Paste (<kbd style={{ background: '#1e293b', padding: '2px 5px', borderRadius: '4px' }}>Ctrl+V</kbd>)
                    </div>

                    <div style={{ color: '#94a3b8', fontSize: '0.82rem', maxWidth: '560px', lineHeight: 1.4 }}>
                      Select any academic file from your computer: Images (PNG, JPG, WEBP), Audio Clips (MP3, WAV, M4A, WEBM), Research Papers (PDF), Word (.docx), or Slides (.pptx) up to 25MB
                    </div>

                    {/* Prominent Action Buttons */}
                    <div style={{ marginTop: '0.85rem', display: 'flex', gap: '0.75rem', flexWrap: 'wrap', justifyContent: 'center' }}>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          triggerFilePicker();
                        }}
                        className="btn btn-primary"
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.5rem',
                          padding: '0.65rem 1.35rem',
                          fontSize: '0.92rem',
                          fontWeight: 700,
                          background: 'linear-gradient(135deg, #2563eb, #0284c7)',
                          boxShadow: '0 4px 14px rgba(37, 99, 235, 0.4)',
                        }}
                      >
                        <span>📁</span>
                        <span>Browse Files on Laptop / Device</span>
                      </button>

                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          startVoiceRecording();
                        }}
                        className="btn btn-secondary"
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.45rem',
                          padding: '0.65rem 1.15rem',
                          fontSize: '0.9rem',
                          color: '#38bdf8',
                          borderColor: 'rgba(56, 189, 248, 0.4)',
                        }}
                      >
                        <span>🎙️</span>
                        <span>Record Voice / Lecture</span>
                      </button>
                    </div>

                    {/* Quick Category Filters */}
                    <div style={{ display: 'flex', gap: '0.4rem', marginTop: '0.5rem', flexWrap: 'wrap', justifyContent: 'center' }}>
                      <span style={{ fontSize: '0.75rem', color: '#64748b', alignSelf: 'center', marginRight: '0.2rem' }}>Quick select:</span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          triggerFilePicker('image/*');
                        }}
                        className="btn btn-secondary btn-xs"
                        style={{ color: '#cbd5e1' }}
                      >
                        📸 Photos & Diagrams
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          triggerFilePicker('application/pdf,.docx,.pptx');
                        }}
                        className="btn btn-secondary btn-xs"
                        style={{ color: '#cbd5e1' }}
                      >
                        📄 PDFs & Slides
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          triggerFilePicker('audio/*');
                        }}
                        className="btn btn-secondary btn-xs"
                        style={{ color: '#cbd5e1' }}
                      >
                        🎵 Audio Files
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Optional Query / Guiding Inquiry */}
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: '#e2e8f0', marginBottom: '0.35rem' }}>
                  Optional Guiding Prompt or Specific Question:
                </label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. 'Explain this concept and find related books' or 'Which papers cite this theory?'"
                  value={userQuery}
                  onChange={(e) => setUserQuery(e.target.value)}
                  style={{ width: '100%', background: '#080d1a', border: '1px solid #1e293b', color: '#f8fafc' }}
                />
              </div>

              {/* Submit Buttons */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
                <button type="button" onClick={onClose} className="btn btn-secondary" disabled={loading}>
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={loading || !selectedFile}
                  style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}
                >
                  {loading ? (
                    <>
                      <span className="spinner" style={{ width: '14px', height: '14px' }} />
                      <span>Gemini Analyzing Media...</span>
                    </>
                  ) : (
                    <>
                      <span>⚡</span>
                      <span>Analyze & Search Holdings</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          ) : (
            /* Analysis Results View */
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              {/* Media & Audio Transcript Breakdown */}
              <div
                style={{
                  background: 'rgba(15, 23, 42, 0.75)',
                  border: '1px solid rgba(56, 189, 248, 0.3)',
                  borderRadius: '12px',
                  padding: '1.25rem',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ fontSize: '1.2rem' }}>
                      {results.analysis.media_format === 'audio' ? '🎙️' : results.analysis.media_format === 'pdf' ? '📄' : '🔬'}
                    </span>
                    <span style={{ fontWeight: 700, fontSize: '1rem', color: '#38bdf8' }}>
                      {results.analysis.academic_field}
                    </span>
                    <span
                      style={{
                        fontSize: '0.72rem',
                        padding: '0.15rem 0.5rem',
                        background: 'rgba(56, 189, 248, 0.15)',
                        color: '#bae6fd',
                        borderRadius: '9999px',
                        textTransform: 'uppercase',
                        fontWeight: 600,
                      }}
                    >
                      {results.analysis.detected_type.replace('_', ' ')}
                    </span>
                  </div>

                  <button
                    type="button"
                    onClick={() => setResults(null)}
                    className="btn btn-secondary btn-xs"
                  >
                    ← Upload Another Media
                  </button>
                </div>

                {/* Verbatim Audio Transcript (if speech detected) */}
                {results.analysis.transcription && (
                  <div style={{ background: '#080d1a', border: '1px solid #1e293b', borderRadius: '8px', padding: '0.85rem', marginBottom: '0.85rem' }}>
                    <div style={{ fontSize: '0.78rem', color: '#38bdf8', fontWeight: 700, marginBottom: '0.25rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                      <span>🎙️</span> Spoken Audio Transcript:
                    </div>
                    <div style={{ fontStyle: 'italic', color: '#cbd5e1', fontSize: '0.85rem', lineHeight: 1.5 }}>
                      "{results.analysis.transcription}"
                    </div>
                  </div>
                )}

                {/* Academic Concept Explanation */}
                <p style={{ color: '#e2e8f0', fontSize: '0.9rem', lineHeight: 1.6, margin: '0 0 0.85rem 0' }}>
                  {results.analysis.summary}
                </p>

                {/* Extracted LaTeX Equations */}
                {results.analysis.extracted_latex && results.analysis.extracted_latex.length > 0 && (
                  <div style={{ margin: '0.75rem 0' }}>
                    <div style={{ fontSize: '0.78rem', color: '#94a3b8', fontWeight: 600, marginBottom: '0.35rem' }}>
                      Transcribed Mathematical Formulation:
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                      {results.analysis.extracted_latex.map((formula, idx) => (
                        <code
                          key={idx}
                          style={{
                            background: '#080d1a',
                            border: '1px solid #1e293b',
                            padding: '0.4rem 0.75rem',
                            borderRadius: '6px',
                            color: '#38bdf8',
                            fontFamily: 'ui-monospace, monospace',
                            fontSize: '0.82rem',
                          }}
                        >
                          {formula}
                        </code>
                      ))}
                    </div>
                  </div>
                )}

                {/* Key Concepts Tags */}
                {results.analysis.key_concepts && results.analysis.key_concepts.length > 0 && (
                  <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', marginTop: '0.5rem' }}>
                    {results.analysis.key_concepts.map((concept, idx) => (
                      <span
                        key={idx}
                        style={{
                          fontSize: '0.75rem',
                          background: '#1e293b',
                          color: '#94a3b8',
                          padding: '0.2rem 0.55rem',
                          borderRadius: '4px',
                        }}
                      >
                        #{concept}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Local Library Catalogue Holdings */}
              <div>
                <h4 style={{ margin: '0 0 0.75rem 0', fontSize: '0.98rem', fontWeight: 700, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <span>📚</span> University Library Holdings on Shelves
                  <span style={{ fontSize: '0.75rem', color: '#94a3b8', fontWeight: 400 }}>
                    ({results.catalogue_matches.length} matching textbooks)
                  </span>
                </h4>

                {results.catalogue_matches.length === 0 ? (
                  <div style={{ padding: '1rem', background: '#080d1a', borderRadius: '8px', color: '#94a3b8', fontSize: '0.85rem' }}>
                    No exact physical copies found on library shelves for this specific formulation. Check global preprints below!
                  </div>
                ) : (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '0.75rem' }}>
                    {results.catalogue_matches.map((book) => {
                      const isAvail = book.available_copies > 0;
                      return (
                        <div
                          key={book.id}
                          style={{
                            background: '#0e1626',
                            border: '1px solid #1e293b',
                            borderRadius: '8px',
                            padding: '0.85rem',
                            display: 'flex',
                            flexDirection: 'column',
                            justifyContent: 'space-between',
                            gap: '0.5rem',
                          }}
                        >
                          <div>
                            <div style={{ fontWeight: 600, color: '#f1f5f9', fontSize: '0.88rem' }}>{book.title}</div>
                            <div style={{ fontSize: '0.78rem', color: '#94a3b8', marginTop: '0.15rem' }}>
                              by {book.author} • {book.category}
                            </div>
                            <div style={{ fontSize: '0.7rem', color: '#64748b', marginTop: '0.2rem' }}>ISBN: {book.isbn}</div>
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '0.5rem' }}>
                            <span
                              style={{
                                fontSize: '0.72rem',
                                padding: '0.15rem 0.45rem',
                                borderRadius: '4px',
                                background: isAvail ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                                color: isAvail ? '#34d399' : '#f87171',
                                fontWeight: 600,
                              }}
                            >
                              {book.available_copies} / {book.total_copies} available
                            </span>

                            {onSelectBook && (
                              <button
                                type="button"
                                className="btn btn-secondary btn-xs"
                                onClick={() => {
                                  onSelectBook(book.id);
                                  onClose();
                                }}
                              >
                                View Monograph 📖
                              </button>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Global Scholarly Research Papers (arXiv, OpenAlex, Crossref) */}
              <div>
                <h4 style={{ margin: '0 0 0.75rem 0', fontSize: '0.98rem', fontWeight: 700, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <span>🎓</span> Global Scholarly Preprints (arXiv / OpenAlex)
                  <span style={{ fontSize: '0.75rem', color: '#94a3b8', fontWeight: 400 }}>
                    ({results.scholarly_papers.length} peer-reviewed papers)
                  </span>
                </h4>

                {results.scholarly_papers.length === 0 ? (
                  <div style={{ padding: '1rem', background: '#080d1a', borderRadius: '8px', color: '#94a3b8', fontSize: '0.85rem' }}>
                    No external scholarly preprints found for this query.
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                    {results.scholarly_papers.map((paper) => (
                      <div
                        key={paper.paper_id}
                        style={{
                          background: '#0e1626',
                          border: '1px solid #1e293b',
                          borderRadius: '8px',
                          padding: '0.85rem 1rem',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          gap: '1rem',
                        }}
                      >
                        <div style={{ flex: 1 }}>
                          <div style={{ fontWeight: 600, color: '#f8fafc', fontSize: '0.88rem' }}>{paper.title}</div>
                          <div style={{ fontSize: '0.78rem', color: '#94a3b8', marginTop: '0.2rem' }}>
                            {paper.authors.slice(0, 3).join(', ')}{paper.authors.length > 3 ? ' et al.' : ''} • {paper.venue || 'Academic Repository'} ({paper.year || 'Recent'})
                          </div>
                          {paper.doi && (
                            <div style={{ fontSize: '0.7rem', color: '#64748b', marginTop: '0.15rem' }}>DOI: {paper.doi}</div>
                          )}
                        </div>

                        {paper.open_access_pdf_url && (
                          <a
                            href={paper.open_access_pdf_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="btn btn-primary btn-sm"
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '0.35rem',
                              whiteSpace: 'nowrap',
                              background: '#0284c7',
                              textDecoration: 'none',
                            }}
                          >
                            <span>📄</span> Download PDF ↗
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
