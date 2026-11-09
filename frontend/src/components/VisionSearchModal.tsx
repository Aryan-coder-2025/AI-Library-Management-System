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
  const [userQuery, setUserQuery] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<VisionResearchResponse | null>(null);
  const [isDragging, setIsDragging] = useState<boolean>(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Clipboard Paste Support (Ctrl+V)
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
    if (!file.type.startsWith('image/')) {
      setError('Please select a valid image file (PNG, JPEG, WEBP).');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError('Image file size must be under 10MB.');
      return;
    }
    setError(null);
    setSelectedFile(file);
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    setResults(null);
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
      setError('Please select, drop, or paste an image to analyze.');
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

      const res = await fetch('/api/research/vision-search', {
        method: 'POST',
        headers: {
          'X-CSRF-Token': csrfToken,
        },
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Vision analysis request failed.');
      }

      const data: VisionResearchResponse = await res.json();
      setResults(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error processing image.';
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

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1050,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'rgba(8, 13, 26, 0.85)',
        backdropFilter: 'blur(6px)',
        padding: '1.25rem',
      }}
    >
      <div
        style={{
          background: '#0e1626',
          border: '1px solid rgba(56, 189, 248, 0.35)',
          borderRadius: '16px',
          width: '100%',
          maxWidth: '820px',
          maxHeight: '92vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7)',
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
            <span style={{ fontSize: '1.4rem' }}>📸</span>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 700, color: '#f8fafc' }}>
                Multimodal AI Vision Research Discovery
              </h3>
              <p style={{ margin: '2px 0 0 0', fontSize: '0.78rem', color: '#94a3b8' }}>
                Upload or paste (<kbd style={{ background: '#1e293b', padding: '1px 4px', borderRadius: '4px' }}>Ctrl+V</kbd>) diagrams, equations, or lecture notes to find matching textbooks & research papers
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
            <form onSubmit={handleAnalyze}>
              {/* Drop Zone */}
              <div
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onClick={() => !previewUrl && fileInputRef.current?.click()}
                style={{
                  border: `2px dashed ${isDragging ? '#38bdf8' : previewUrl ? '#10b981' : 'rgba(56, 189, 248, 0.35)'}`,
                  background: isDragging ? 'rgba(56, 189, 248, 0.12)' : previewUrl ? 'rgba(16, 185, 129, 0.05)' : '#080d1a',
                  borderRadius: '12px',
                  padding: '1.75rem',
                  textAlign: 'center',
                  cursor: previewUrl ? 'default' : 'pointer',
                  transition: 'all 0.2s ease',
                  marginBottom: '1.25rem',
                  position: 'relative',
                }}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  style={{ display: 'none' }}
                  onChange={(e) => e.target.files?.[0] && handleFileSelect(e.target.files[0])}
                />

                {previewUrl ? (
                  <div style={{ position: 'relative', display: 'inline-block' }}>
                    <img
                      src={previewUrl}
                      alt="Uploaded preview"
                      style={{
                        maxHeight: '240px',
                        maxWidth: '100%',
                        borderRadius: '8px',
                        border: '1px solid rgba(255, 255, 255, 0.15)',
                        objectFit: 'contain',
                      }}
                    />
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        clearSelection();
                      }}
                      className="btn btn-secondary btn-sm"
                      style={{
                        position: 'absolute',
                        top: '-10px',
                        right: '-10px',
                        background: '#ef4444',
                        color: '#fff',
                        borderColor: '#dc2626',
                        borderRadius: '50%',
                        width: '26px',
                        height: '26px',
                        padding: 0,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '0.8rem',
                        fontWeight: 'bold',
                      }}
                      title="Remove image"
                    >
                      ✕
                    </button>
                    <div style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: '#10b981', fontWeight: 600 }}>
                      ✓ {selectedFile?.name} ({(selectedFile?.size ? (selectedFile.size / 1024).toFixed(1) : 0)} KB)
                    </div>
                  </div>
                ) : (
                  <div>
                    <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>📷</div>
                    <div style={{ fontWeight: 600, color: '#f8fafc', fontSize: '1rem' }}>
                      Drag & drop an academic image, screenshot, or click to browse
                    </div>
                    <p style={{ margin: '0.35rem 0 0 0', fontSize: '0.825rem', color: '#94a3b8' }}>
                      Supports mathematical formulas, system architecture diagrams, textbook excerpts, or lecture slides (PNG, JPG, WEBP)
                    </p>
                    <div style={{ marginTop: '0.75rem', display: 'inline-block', padding: '0.25rem 0.75rem', background: 'rgba(56, 189, 248, 0.12)', border: '1px solid rgba(56, 189, 248, 0.3)', borderRadius: '20px', fontSize: '0.75rem', color: '#38bdf8' }}>
                      💡 Tip: Press <kbd style={{ background: '#1e293b', padding: '1px 5px', borderRadius: '4px' }}>Ctrl+V</kbd> anywhere on this screen to paste from clipboard
                    </div>
                  </div>
                )}
              </div>

              {/* Optional Prompt Input */}
              <div className="form-group" style={{ marginBottom: '1.25rem' }}>
                <label className="form-label" htmlFor="vision-prompt-input">
                  Specific Research Question / Instructions <span className="form-label-hint">(Optional)</span>
                </label>
                <input
                  id="vision-prompt-input"
                  type="text"
                  className="form-input"
                  placeholder="e.g. Find textbooks explaining this equation, or retrieve papers related to this diagram..."
                  value={userQuery}
                  onChange={(e) => setUserQuery(e.target.value)}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={onClose}
                  disabled={loading}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={loading || !selectedFile}
                  style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', minWidth: '180px', justifyContent: 'center' }}
                >
                  {loading ? (
                    <>
                      <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true" />
                      <span>Analyzing with Gemini...</span>
                    </>
                  ) : (
                    <>
                      <span>⚡</span>
                      <span>Analyze & Search</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          ) : (
            /* Results Presentation View */
            <div>
              {/* Top Action Bar */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', borderBottom: '1px solid rgba(255, 255, 255, 0.08)', paddingBottom: '0.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span className="badge badge-primary" style={{ textTransform: 'capitalize' }}>
                    {results.analysis.detected_type.replace('_', ' ')}
                  </span>
                  <span className="badge badge-secondary" style={{ color: '#38bdf8', borderColor: 'rgba(56, 189, 248, 0.3)' }}>
                    {results.analysis.academic_field}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={clearSelection}
                  className="btn btn-secondary btn-sm"
                  style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}
                >
                  <span>🔄</span>
                  <span>Upload Another Image</span>
                </button>
              </div>

              {/* Analysis Card */}
              <div
                style={{
                  background: 'rgba(37, 99, 235, 0.08)',
                  border: '1px solid rgba(56, 189, 248, 0.35)',
                  borderRadius: '12px',
                  padding: '1.25rem',
                  marginBottom: '1.5rem',
                }}
              >
                <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '1rem', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <span>🧠</span>
                  <span>Gemini Multimodal Analysis</span>
                </h4>
                <p style={{ margin: 0, fontSize: '0.9rem', lineHeight: 1.55, color: '#cbd5e1' }}>
                  {results.analysis.summary}
                </p>

                {/* Extracted LaTeX Equations */}
                {results.analysis.extracted_latex.length > 0 && (
                  <div style={{ marginTop: '0.85rem', paddingTop: '0.75rem', borderTop: '1px solid rgba(255, 255, 255, 0.08)' }}>
                    <div style={{ fontSize: '0.78rem', fontWeight: 600, color: '#38bdf8', marginBottom: '0.35rem' }}>
                      Transcribed Mathematical Equations (LaTeX):
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                      {results.analysis.extracted_latex.map((eq, i) => (
                        <code
                          key={i}
                          style={{
                            background: '#080d1a',
                            border: '1px solid rgba(56, 189, 248, 0.25)',
                            padding: '4px 8px',
                            borderRadius: '6px',
                            color: '#38bdf8',
                            fontSize: '0.85rem',
                            fontFamily: 'var(--font-mono)',
                          }}
                        >
                          {eq}
                        </code>
                      ))}
                    </div>
                  </div>
                )}

                {/* Key Concepts */}
                {results.analysis.key_concepts.length > 0 && (
                  <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                    {results.analysis.key_concepts.map((concept, i) => (
                      <span
                        key={i}
                        style={{
                          fontSize: '0.75rem',
                          background: 'rgba(255, 255, 255, 0.06)',
                          padding: '2px 8px',
                          borderRadius: '12px',
                          color: '#94a3b8',
                        }}
                      >
                        #{concept}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Library Monograph Holdings */}
              <div style={{ marginBottom: '1.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                  <h4 style={{ margin: 0, fontSize: '0.95rem', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                    <span>📚</span>
                    <span>Matching University Library Monographs ({results.catalogue_matches.length})</span>
                  </h4>
                  <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
                    Matched via '{results.analysis.suggested_catalogue_search}'
                  </span>
                </div>

                {results.catalogue_matches.length === 0 ? (
                  <div style={{ background: '#080d1a', padding: '1rem', borderRadius: '8px', color: '#94a3b8', fontSize: '0.85rem' }}>
                    No exact physical monographs found matching these terms. Check global papers below or refine your query.
                  </div>
                ) : (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '0.75rem' }}>
                    {results.catalogue_matches.map((book) => (
                      <div
                        key={book.id}
                        style={{
                          background: '#080d1a',
                          border: '1px solid rgba(255, 255, 255, 0.08)',
                          borderRadius: '10px',
                          padding: '0.85rem',
                          display: 'flex',
                          flexDirection: 'column',
                          justifyContent: 'space-between',
                          gap: '0.5rem',
                        }}
                      >
                        <div>
                          <strong style={{ fontSize: '0.88rem', color: '#f8fafc', display: 'block', marginBottom: '2px' }}>
                            {book.title}
                          </strong>
                          <div style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
                            {book.author} • <span style={{ fontFamily: 'var(--font-mono)' }}>{book.category}</span>
                          </div>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '4px' }}>
                          <span
                            className={`badge ${book.available_copies > 0 ? 'badge-success' : 'badge-warning'}`}
                            style={{ fontSize: '0.7rem' }}
                          >
                            {book.available_copies > 0 ? `🟢 ${book.available_copies} available` : '⚠️ All copies on loan'}
                          </span>

                          {onSelectBook && (
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              onClick={() => {
                                onSelectBook(book.id);
                                onClose();
                              }}
                              style={{ fontSize: '0.75rem', padding: '0.2rem 0.55rem' }}
                            >
                              View Book →
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Global Scholarly Research Papers */}
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                  <h4 style={{ margin: 0, fontSize: '0.95rem', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                    <span>🌐</span>
                    <span>Scholarly Research Papers ({results.scholarly_papers.length})</span>
                  </h4>
                  <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
                    arXiv • OpenAlex • Crossref
                  </span>
                </div>

                {results.scholarly_papers.length === 0 ? (
                  <div style={{ background: '#080d1a', padding: '1rem', borderRadius: '8px', color: '#94a3b8', fontSize: '0.85rem' }}>
                    Searching external preprint archives...
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                    {results.scholarly_papers.map((paper) => (
                      <div
                        key={paper.paper_id}
                        style={{
                          background: '#080d1a',
                          border: '1px solid rgba(255, 255, 255, 0.08)',
                          borderRadius: '10px',
                          padding: '0.85rem 1rem',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          gap: '1rem',
                          flexWrap: 'wrap',
                        }}
                      >
                        <div style={{ flex: 1, minWidth: '240px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '2px' }}>
                            <span
                              style={{
                                fontSize: '0.68rem',
                                textTransform: 'uppercase',
                                padding: '1px 6px',
                                borderRadius: '4px',
                                background: paper.provider === 'arxiv' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(56, 189, 248, 0.15)',
                                color: paper.provider === 'arxiv' ? '#f87171' : '#38bdf8',
                                fontWeight: 700,
                              }}
                            >
                              {paper.provider}
                            </span>
                            {paper.year && (
                              <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
                                ({paper.year})
                              </span>
                            )}
                          </div>
                          <strong style={{ fontSize: '0.9rem', color: '#f8fafc' }}>
                            {paper.title}
                          </strong>
                          <div style={{ fontSize: '0.78rem', color: '#94a3b8', marginTop: '2px' }}>
                            {paper.authors.slice(0, 3).join(', ')}{paper.authors.length > 3 ? ' et al.' : ''}
                            {paper.venue ? ` • ${paper.venue}` : ''}
                          </div>
                        </div>

                        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                          {paper.open_access_pdf_url && (
                            <a
                              href={paper.open_access_pdf_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="btn btn-primary btn-sm"
                              style={{ fontSize: '0.75rem', whiteSpace: 'nowrap', textDecoration: 'none' }}
                            >
                              📄 Open PDF
                            </a>
                          )}
                          {paper.doi && (
                            <a
                              href={`https://doi.org/${paper.doi}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="btn btn-secondary btn-sm"
                              style={{ fontSize: '0.75rem', whiteSpace: 'nowrap', textDecoration: 'none' }}
                            >
                              DOI ↗
                            </a>
                          )}
                        </div>
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

