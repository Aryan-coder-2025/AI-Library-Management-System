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
      const csrfToken = document.cookie
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="bg-slate-900 border border-slate-700/80 rounded-2xl w-full max-w-xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh]">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/50">
          <div>
            <h2 className="text-lg font-bold text-slate-100">Physical Copy Maintenance & Status</h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Copy <span className="font-mono text-cyan-400 font-semibold">{copyCode}</span> • {bookTitle}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 text-xl font-bold p-1 rounded-lg hover:bg-slate-800 transition"
          >
            ✕
          </button>
        </div>

        <div className="p-6 overflow-y-auto space-y-6">
          {error && (
            <div className="p-3 bg-red-950/40 border border-red-800/60 rounded-xl text-xs text-red-300">
              {error}
            </div>
          )}

          {/* Status Form */}
          <form onSubmit={handleUpdate} className="space-y-4 bg-slate-950/40 p-4 border border-slate-800/80 rounded-xl">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-cyan-400">Record Operational Transition</h3>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Current Status</label>
                <span className="inline-block px-3 py-1.5 rounded-lg text-xs font-semibold uppercase tracking-wide bg-slate-800 text-slate-300 border border-slate-700">
                  {currentStatus}
                </span>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">New Status</label>
                <select
                  value={selectedStatus}
                  onChange={(e) => setSelectedStatus(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-2 focus:ring-2 focus:ring-cyan-500 focus:outline-none"
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
              <label className="block text-xs font-medium text-slate-300 mb-1">Audit Notes / Reason</label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="e.g. Spine damage reported upon return, sent to conservation lab..."
                rows={3}
                className="w-full bg-slate-800/80 border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5 focus:ring-2 focus:ring-cyan-500 focus:outline-none"
              />
            </div>

            <div className="flex justify-end space-x-3 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-lg transition"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="px-5 py-2 bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold rounded-lg transition shadow-md disabled:opacity-50"
              >
                {submitting ? 'Recording...' : 'Record Status Change'}
              </button>
            </div>
          </form>

          {/* Audit History */}
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">Audit Trail & Incident Log</h3>
            {loadingHistory ? (
              <p className="text-xs text-slate-500">Loading audit events...</p>
            ) : history.length === 0 ? (
              <div className="p-4 bg-slate-950/20 border border-slate-800/40 rounded-xl text-center text-xs text-slate-500">
                No prior status changes or audit incidents recorded for this copy.
              </div>
            ) : (
              <div className="space-y-2.5 max-h-48 overflow-y-auto pr-1">
                {history.map((ev) => (
                  <div key={ev.id} className="p-3 bg-slate-950/60 border border-slate-800/80 rounded-xl text-xs space-y-1">
                    <div className="flex justify-between items-center text-slate-400">
                      <span className="font-semibold text-slate-200">{ev.event_type.replace('_', ' ').toUpperCase()}</span>
                      <span>{new Date(ev.recorded_at).toLocaleDateString()} {new Date(ev.recorded_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                    <div className="flex items-center space-x-2 text-slate-300">
                      <span className="font-mono text-[11px] text-slate-400">{ev.previous_status || 'initial'}</span>
                      <span>→</span>
                      <span className="font-mono text-[11px] text-cyan-300 font-bold">{ev.new_status}</span>
                      <span className="text-slate-500">• Auditor: {ev.auditor_name}</span>
                    </div>
                    {ev.notes && <p className="text-slate-400 italic text-[11px] mt-0.5">"{ev.notes}"</p>}
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
