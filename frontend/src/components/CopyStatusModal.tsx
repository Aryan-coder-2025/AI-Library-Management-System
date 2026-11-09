import React, { useEffect, useState } from 'react';
import type { InventoryAuditRecord } from '../types/library';

interface CopyStatusModalProps {
  copyId: number;
  copyCode: string;
  bookTitle: string;
  currentStatus: string;
  onClose: () => void;
  onStatusUpdated: () => void;
}

export const CopyStatusModal: React.FC<CopyStatusModalProps> = ({
  copyId,
  copyCode,
  bookTitle,
  currentStatus,
  onClose,
  onStatusUpdated,
}) => {
  const [selectedStatus, setSelectedStatus] = useState<string>(currentStatus);
  const [notes, setNotes] = useState<string>('');
  const [history, setHistory] = useState<InventoryAuditRecord[]>([]);
  const [loadingHistory, setLoadingHistory] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchAuditHistory();
  }, [copyId]);

  const fetchAuditHistory = async () => {
    try {
      setLoadingHistory(true);
      const res = await fetch(`/api/circulation/copies/${copyId}/audit-history`);
      if (res.ok) {
        const data = await res.json();
        setHistory(data.items || []);
      }
    } catch (err) {
      console.error('Failed to load audit history:', err);
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedStatus === currentStatus && !notes.trim()) {
      setError('Please provide notes or select a different status.');
      return;
    }

    try {
      setSubmitting(true);
      setError(null);
      const csrfToken =
        document.cookie
          .split('; ')
          .find((row) => row.startsWith('csrf_token='))
          ?.split('=')[1] || '';

      const res = await fetch(`/api/circulation/copies/${copyId}/status`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken,
        },
        body: JSON.stringify({
          status: selectedStatus,
          notes: notes.trim() || undefined,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to update copy status.');
      }

      onStatusUpdated();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Error updating status.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(8, 13, 26, 0.78)',
        backdropFilter: 'blur(4px)',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1rem',
      }}
    >
      <div
        style={{
          background: 'var(--bg-surface, #0E1626)',
          border: '1px solid var(--border-medium, rgba(148, 163, 184, 0.25))',
          borderRadius: '14px',
          maxWidth: '560px',
          width: '100%',
          boxShadow: 'var(--shadow-modal)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          maxHeight: '90vh',
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '1.25rem 1.5rem',
            borderBottom: '1px solid var(--border-subtle, rgba(148, 163, 184, 0.16))',
            background: 'var(--bg-subtle, #1C2B4A)',
          }}
        >
          <div>
            <h3 style={{ margin: 0, fontSize: '1.1rem', color: 'var(--text-primary, #F8FAFC)' }}>
              Physical Copy Maintenance & Status
            </h3>
            <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.78rem', color: 'var(--text-secondary, #94A3B8)' }}>
              Copy <span style={{ fontFamily: 'monospace', color: 'var(--accent-cyan, #38BDF8)', fontWeight: 700 }}>{copyCode}</span> • {bookTitle}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-muted, #94A3B8)',
              fontSize: '1.25rem',
              cursor: 'pointer',
              padding: '4px',
            }}
          >
            ✕
          </button>
        </div>

        <div style={{ padding: '1.5rem', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {error && (
            <div className="alert alert-error" style={{ margin: 0 }}>
              <span>⚠️ {error}</span>
            </div>
          )}

          {/* Status Form */}
          <form
            onSubmit={handleUpdate}
            style={{
              background: 'var(--bg-tertiary, #141F36)',
              border: '1px solid var(--border-subtle, rgba(148, 163, 184, 0.16))',
              borderRadius: '10px',
              padding: '1.25rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '1rem',
            }}
          >
            <span style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--brand-secondary, #38BDF8)', letterSpacing: '0.05em' }}>
              Record Operational Transition
            </span>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-secondary, #94A3B8)', marginBottom: '0.35rem' }}>
                  Current Status
                </label>
                <span
                  style={{
                    display: 'inline-block',
                    padding: '0.45rem 0.75rem',
                    borderRadius: '6px',
                    fontSize: '0.78rem',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    background: 'var(--bg-surface, #0E1626)',
                    color: 'var(--text-secondary, #94A3B8)',
                    border: '1px solid var(--border-subtle, rgba(148, 163, 184, 0.2))',
                  }}
                >
                  {currentStatus}
                </span>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-secondary, #94A3B8)', marginBottom: '0.35rem' }}>
                  New Status
                </label>
                <select
                  value={selectedStatus}
                  onChange={(e) => setSelectedStatus(e.target.value)}
                  style={{
                    width: '100%',
                    background: 'var(--bg-surface, #0E1626)',
                    border: '1px solid var(--border-medium, rgba(148, 163, 184, 0.25))',
                    color: 'var(--text-primary, #F8FAFC)',
                    fontSize: '0.8rem',
                    borderRadius: '6px',
                    padding: '0.45rem 0.65rem',
                    outline: 'none',
                  }}
                >
                  <option value="available">Available (Shelf)</option>
                  <option value="maintenance">Maintenance</option>
                  <option value="damaged">Damaged</option>
                  <option value="lost">Lost</option>
                  <option value="retired">Retired</option>
                </select>
              </div>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-secondary, #94A3B8)', marginBottom: '0.35rem' }}>
                Audit Notes / Reason
              </label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="e.g. Spine damage reported upon return, sent to conservation lab..."
                rows={3}
                style={{
                  width: '100%',
                  background: 'var(--bg-surface, #0E1626)',
                  border: '1px solid var(--border-medium, rgba(148, 163, 184, 0.25))',
                  color: 'var(--text-primary, #F8FAFC)',
                  fontSize: '0.8rem',
                  borderRadius: '6px',
                  padding: '0.5rem 0.65rem',
                  outline: 'none',
                  boxSizing: 'border-box',
                }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.65rem', marginTop: '0.25rem' }}>
              <button
                type="button"
                onClick={onClose}
                className="btn btn-secondary btn-sm"
                style={{ padding: '0.45rem 1rem' }}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="btn btn-primary btn-sm"
                style={{ padding: '0.45rem 1.15rem' }}
              >
                {submitting ? 'Recording...' : 'Record Status Change'}
              </button>
            </div>
          </form>

          {/* Audit History */}
          <div>
            <h4 style={{ margin: '0 0 0.65rem 0', fontSize: '0.78rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted, #64748B)' }}>
              Audit Trail & Incident Log
            </h4>
            {loadingHistory ? (
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted, #64748B)' }}>Loading audit events...</p>
            ) : history.length === 0 ? (
              <div
                style={{
                  padding: '1.25rem',
                  background: 'var(--bg-tertiary, #141F36)',
                  border: '1px solid var(--border-subtle, rgba(148, 163, 184, 0.12))',
                  borderRadius: '8px',
                  textAlign: 'center',
                  fontSize: '0.8rem',
                  color: 'var(--text-muted, #64748B)',
                }}
              >
                No prior status changes or audit incidents recorded for this copy.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '180px', overflowY: 'auto' }}>
                {history.map((ev) => (
                  <div
                    key={ev.id}
                    style={{
                      padding: '0.75rem',
                      background: 'var(--bg-tertiary, #141F36)',
                      border: '1px solid var(--border-subtle, rgba(148, 163, 184, 0.16))',
                      borderRadius: '8px',
                      fontSize: '0.78rem',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.25rem',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-secondary, #94A3B8)' }}>
                      <strong style={{ color: 'var(--text-primary, #F8FAFC)' }}>{ev.event_type.replace('_', ' ').toUpperCase()}</strong>
                      <span>
                        {new Date(ev.recorded_at).toLocaleDateString()} {new Date(ev.recorded_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-secondary, #94A3B8)' }}>
                      <span style={{ fontFamily: 'monospace' }}>{ev.previous_status || 'initial'}</span>
                      <span>→</span>
                      <strong style={{ fontFamily: 'monospace', color: 'var(--brand-secondary, #38BDF8)' }}>{ev.new_status}</strong>
                      <span style={{ color: 'var(--text-muted, #64748B)' }}>• Auditor: {ev.auditor_name}</span>
                    </div>
                    {ev.notes && <p style={{ margin: '0.2rem 0 0 0', fontStyle: 'italic', color: 'var(--text-muted, #64748B)' }}>"{ev.notes}"</p>}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
export default CopyStatusModal;
