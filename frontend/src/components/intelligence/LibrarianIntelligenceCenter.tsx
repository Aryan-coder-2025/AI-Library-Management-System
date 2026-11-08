import React, { useEffect, useState } from 'react';
import type {
  AcquisitionRequestItem,
  AcquisitionSuggestionItem,
  CirculationTrends,
  IntelligenceSnapshot,
  InventoryAnalytics,
  TwoWeekDemandForecast,
} from '../../types/library';

export const LibrarianIntelligenceCenter: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'snapshot' | 'inventory' | 'forecast' | 'acquisitions'>('snapshot');

  // Data states
  const [snapshot, setSnapshot] = useState<IntelligenceSnapshot | null>(null);
  const [inventory, setInventory] = useState<InventoryAnalytics | null>(null);
  const [trends, setTrends] = useState<CirculationTrends | null>(null);
  const [forecast, setForecast] = useState<TwoWeekDemandForecast | null>(null);
  const [suggestions, setSuggestions] = useState<AcquisitionSuggestionItem[]>([]);
  const [acquisitions, setAcquisitions] = useState<AcquisitionRequestItem[]>([]);

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // New acquisition modal
  const [showAddModal, setShowAddModal] = useState<boolean>(false);
  const [reqTitle, setReqTitle] = useState<string>('');
  const [reqAuthor, setReqAuthor] = useState<string>('');
  const [reqIsbn, setReqIsbn] = useState<string>('');
  const [reqNotes, setReqNotes] = useState<string>('');
  const [submittingReq, setSubmittingReq] = useState<boolean>(false);

  useEffect(() => {
    fetchAllIntelligenceData();
  }, []);

  const fetchAllIntelligenceData = async () => {
    try {
      setLoading(true);
      setError(null);

      const [resSnap, resInv, resTrends, resFore, resSugg, resAcq] = await Promise.all([
        fetch('/api/intelligence/snapshot'),
        fetch('/api/intelligence/inventory'),
        fetch('/api/intelligence/circulation-trends?days=14'),
        fetch('/api/intelligence/forecast'),
        fetch('/api/intelligence/acquisitions/suggestions?limit=15'),
        fetch('/api/intelligence/acquisitions/requests'),
      ]);

      if (resSnap.ok) setSnapshot(await resSnap.json());
      if (resInv.ok) setInventory(await resInv.json());
      if (resTrends.ok) setTrends(await resTrends.json());
      if (resFore.ok) setForecast(await resFore.json());
      if (resSugg.ok) {
        const data = await resSugg.json();
        setSuggestions(data.suggestions || []);
      }
      if (resAcq.ok) {
        const data = await resAcq.json();
        setAcquisitions(data.items || []);
      }
    } catch (err) {
      setError('Failed to load library intelligence metrics.');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateAcquisitionRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reqTitle.trim()) return;

    try {
      setSubmittingReq(true);
      const csrfToken = document.cookie
        .split('; ')
        .find((row) => row.startsWith('csrf_token='))
        ?.split('=')[1] || '';

      const res = await fetch('/api/intelligence/acquisitions/requests', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken,
        },
        body: JSON.stringify({
          title: reqTitle.trim(),
          author: reqAuthor.trim() || undefined,
          isbn: reqIsbn.trim() || undefined,
          notes: reqNotes.trim() || undefined,
        }),
      });

      if (!res.ok) {
        throw new Error('Failed to create acquisition request.');
      }

      setShowAddModal(false);
      setReqTitle('');
      setReqAuthor('');
      setReqIsbn('');
      setReqNotes('');
      // Refresh requests
      const resAcq = await fetch('/api/intelligence/acquisitions/requests');
      if (resAcq.ok) {
        const data = await resAcq.json();
        setAcquisitions(data.items || []);
      }
    } catch (err: any) {
      alert(err.message || 'Error submitting request.');
    } finally {
      setSubmittingReq(false);
    }
  };

  const handleUpdateAcquisitionStatus = async (
    reqId: number,
    newStatus: 'approved' | 'rejected' | 'ordered' | 'received',
  ) => {
    try {
      const csrfToken = document.cookie
        .split('; ')
        .find((row) => row.startsWith('csrf_token='))
        ?.split('=')[1] || '';

      const res = await fetch(`/api/intelligence/acquisitions/requests/${reqId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken,
        },
        body: JSON.stringify({ status: newStatus }),
      });

      if (res.ok) {
        setAcquisitions((prev) =>
          prev.map((item) => (item.id === reqId ? { ...item, status: newStatus } : item))
        );
      }
    } catch (err) {
      console.error('Failed to update acquisition status:', err);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-8 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center space-x-3">
            <span className="text-3xl">🏛️</span>
            <h1 className="text-2xl md:text-3xl font-extrabold text-slate-100 tracking-tight">
              Librarian Intelligence Centre
            </h1>
          </div>
          <p className="text-slate-400 text-sm mt-1 max-w-2xl">
            Unified administrative intelligence cockpit for institutional circulation trends, collection turnover, predictive demand forecasting, and zero-search procurement workflows.
          </p>
        </div>

        <button
          onClick={fetchAllIntelligenceData}
          className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-xl border border-slate-700 transition flex items-center space-x-2"
        >
          <span>🔄</span>
          <span>Refresh Data</span>
        </button>
      </div>

      {error && (
        <div className="p-4 bg-red-950/40 border border-red-800/60 rounded-xl text-xs text-red-300">
          {error}
        </div>
      )}

      {/* Navigation Sub-Tabs */}
      <div className="flex space-x-2 border-b border-slate-800">
        <button
          onClick={() => setActiveTab('snapshot')}
          className={`px-4 py-2.5 text-xs font-bold rounded-t-xl transition ${
            activeTab === 'snapshot'
              ? 'bg-slate-800/90 text-cyan-400 border-t-2 border-cyan-500 border-x border-slate-700'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/30'
          }`}
        >
          📊 Executive Snapshot (INTEL-02)
        </button>
        <button
          onClick={() => setActiveTab('inventory')}
          className={`px-4 py-2.5 text-xs font-bold rounded-t-xl transition ${
            activeTab === 'inventory'
              ? 'bg-slate-800/90 text-cyan-400 border-t-2 border-cyan-500 border-x border-slate-700'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/30'
          }`}
        >
          📦 Inventory & Turnover (INTEL-04)
        </button>
        <button
          onClick={() => setActiveTab('forecast')}
          className={`px-4 py-2.5 text-xs font-bold rounded-t-xl transition ${
            activeTab === 'forecast'
              ? 'bg-slate-800/90 text-cyan-400 border-t-2 border-cyan-500 border-x border-slate-700'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/30'
          }`}
        >
          📈 2-Week Demand Forecast (INTEL-03)
        </button>
        <button
          onClick={() => setActiveTab('acquisitions')}
          className={`px-4 py-2.5 text-xs font-bold rounded-t-xl transition ${
            activeTab === 'acquisitions'
              ? 'bg-slate-800/90 text-cyan-400 border-t-2 border-cyan-500 border-x border-slate-700'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/30'
          }`}
        >
          🛍️ Acquisitions Pipeline (INTEL-05)
        </button>
      </div>

      {loading ? (
        <div className="py-16 text-center text-slate-500 text-sm">Aggregating institutional telemetry...</div>
      ) : (
        <div>
          {/* TAB 1: EXECUTIVE SNAPSHOT */}
          {activeTab === 'snapshot' && snapshot && (
            <div className="space-y-6">
              {/* KPI Cards Grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-2xl space-y-1">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Active Loans</span>
                  <p className="text-2xl font-black text-slate-100">{snapshot.active_loans_count}</p>
                  <p className="text-[11px] text-cyan-400">Total circulating items</p>
                </div>

                <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-2xl space-y-1">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Overdue Rate</span>
                  <p className="text-2xl font-black text-rose-400">{snapshot.overdue_rate_pct}%</p>
                  <p className="text-[11px] text-slate-400">{snapshot.overdue_loans_count} overdue accounts</p>
                </div>

                <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-2xl space-y-1">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Active Holds</span>
                  <p className="text-2xl font-black text-amber-400">{snapshot.active_holds_count}</p>
                  <p className="text-[11px] text-slate-400">Patrons in waitlist queue</p>
                </div>

                <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-2xl space-y-1">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Space Occupancy</span>
                  <p className="text-2xl font-black text-emerald-400">{snapshot.current_occupancy_pct}%</p>
                  <p className="text-[11px] text-slate-400">Peak Hour: ~{snapshot.peak_occupancy_hour}:00</p>
                </div>
              </div>

              {/* 14-Day Circulation Trends */}
              {trends && (
                <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6 space-y-4">
                  <div className="flex justify-between items-center">
                    <div>
                      <h3 className="text-sm font-bold text-slate-200">14-Day Circulation Velocity</h3>
                      <p className="text-xs text-slate-400">Daily monograph issue and return volume.</p>
                    </div>
                    <div className="flex items-center space-x-4 text-xs">
                      <span className="flex items-center space-x-1.5 text-cyan-400">
                        <span className="w-2.5 h-2.5 rounded-full bg-cyan-500"></span>
                        <span>Issues ({trends.total_issues})</span>
                      </span>
                      <span className="flex items-center space-x-1.5 text-emerald-400">
                        <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
                        <span>Returns ({trends.total_returns})</span>
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-7 md:grid-cols-14 gap-2 pt-4">
                    {trends.points.map((pt) => (
                      <div key={pt.date} className="flex flex-col items-center space-y-1">
                        <div className="w-full bg-slate-950/60 rounded-lg p-2 text-center border border-slate-800">
                          <span className="text-[10px] text-cyan-300 font-bold block">{pt.issues}</span>
                          <span className="text-[10px] text-emerald-300 font-bold block">{pt.returns}</span>
                        </div>
                        <span className="text-[9px] text-slate-500 font-mono">{pt.date.slice(5)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 2: INVENTORY ANALYTICS */}
          {activeTab === 'inventory' && inventory && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6 space-y-4">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Collection Turnover</h3>
                  <div className="flex items-baseline space-x-2">
                    <p className="text-4xl font-extrabold text-cyan-400">{inventory.collection_turnover_rate}x</p>
                    <span className="text-xs text-slate-400">lifetime loan turnover</span>
                  </div>
                  <p className="text-xs text-slate-400 leading-relaxed">
                    Evaluated across {inventory.total_monographs} monograph titles and {inventory.total_physical_copies} copies.
                  </p>
                </div>

                <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6 space-y-4">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Demand Distribution</h3>
                  <div className="space-y-2 text-xs">
                    <div className="flex justify-between">
                      <span className="text-slate-400">High-Demand Titles:</span>
                      <span className="font-bold text-amber-300">{inventory.high_demand_titles_count}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Zero-Borrow Titles:</span>
                      <span className="font-bold text-slate-300">{inventory.zero_borrow_titles_count}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Audit Events Recorded:</span>
                      <span className="font-bold text-cyan-300">{inventory.total_audit_events_count}</span>
                    </div>
                  </div>
                </div>

                <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6 space-y-4">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Degradation & Loss</h3>
                  <div className="space-y-2 text-xs">
                    <div className="flex justify-between">
                      <span className="text-slate-400">Under Maintenance:</span>
                      <span className="font-bold text-amber-400">{inventory.maintenance_copies}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Damaged Flagged:</span>
                      <span className="font-bold text-rose-400">{inventory.damaged_copies}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Lost Reported:</span>
                      <span className="font-bold text-red-500">{inventory.lost_copies}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Physical Copy Operational Status Bar */}
              <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6 space-y-4">
                <h3 className="text-sm font-bold text-slate-200">Physical Copy Fleet Distribution</h3>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-center">
                  <div className="p-3 bg-slate-950/60 border border-emerald-800/40 rounded-xl">
                    <span className="text-xs text-emerald-400 font-semibold block">Available</span>
                    <span className="text-lg font-bold text-slate-100">{inventory.available_copies}</span>
                  </div>
                  <div className="p-3 bg-slate-950/60 border border-cyan-800/40 rounded-xl">
                    <span className="text-xs text-cyan-400 font-semibold block">On Loan</span>
                    <span className="text-lg font-bold text-slate-100">{inventory.borrowed_copies}</span>
                  </div>
                  <div className="p-3 bg-slate-950/60 border border-amber-800/40 rounded-xl">
                    <span className="text-xs text-amber-400 font-semibold block">Maintenance</span>
                    <span className="text-lg font-bold text-slate-100">{inventory.maintenance_copies}</span>
                  </div>
                  <div className="p-3 bg-slate-950/60 border border-rose-800/40 rounded-xl">
                    <span className="text-xs text-rose-400 font-semibold block">Damaged</span>
                    <span className="text-lg font-bold text-slate-100">{inventory.damaged_copies}</span>
                  </div>
                  <div className="p-3 bg-slate-950/60 border border-red-800/40 rounded-xl">
                    <span className="text-xs text-red-400 font-semibold block">Lost</span>
                    <span className="text-lg font-bold text-slate-100">{inventory.lost_copies}</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: DEMAND FORECASTING */}
          {activeTab === 'forecast' && forecast && (
            <div className="space-y-6">
              <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6 space-y-4">
                <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-2">
                  <div>
                    <h3 className="text-sm font-bold text-slate-200">14-Day Forward Checkout Demand Projection</h3>
                    <p className="text-xs text-slate-400">{forecast.methodology}</p>
                  </div>
                  <div className="flex items-center space-x-3 text-xs">
                    <span className="px-2.5 py-1 bg-slate-800 text-slate-300 rounded-lg">
                      Baseline: <strong className="text-cyan-300">{forecast.baseline_daily_average}/day</strong>
                    </span>
                    <span className="px-2.5 py-1 bg-slate-800 text-slate-300 rounded-lg">
                      Trend: <strong className="text-emerald-300 uppercase">{forecast.trend_direction}</strong>
                    </span>
                  </div>
                </div>

                {/* Forecast Table / Graph Cards */}
                <div className="grid grid-cols-2 md:grid-cols-7 gap-3 pt-4">
                  {forecast.projections.map((p) => (
                    <div key={p.date} className="p-3 bg-slate-950/60 border border-slate-800 rounded-xl text-center space-y-1">
                      <span className="text-[11px] font-bold text-slate-300 block">{p.day_of_week.slice(0, 3)}</span>
                      <span className="text-[10px] text-slate-500 font-mono block">{p.date.slice(5)}</span>
                      <p className="text-lg font-extrabold text-cyan-400 mt-1">{p.projected_checkouts}</p>
                      <p className="text-[9px] text-slate-400 font-mono">
                        [{p.lower_bound} - {p.upper_bound}]
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: ACQUISITIONS PIPELINE */}
          {activeTab === 'acquisitions' && (
            <div className="space-y-6">
              <div className="flex justify-between items-center">
                <div>
                  <h3 className="text-sm font-bold text-slate-200">Zero-Result Search Demand Signals (INTEL-05)</h3>
                  <p className="text-xs text-slate-400">Unmet student search demand revealing gaps in library holdings.</p>
                </div>
                <button
                  onClick={() => setShowAddModal(true)}
                  className="px-3.5 py-2 bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold rounded-xl transition"
                >
                  + Add Candidate Title
                </button>
              </div>

              {/* Zero-Result Search Suggestions Table */}
              <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-4 space-y-3">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Patron Search Telemetry Signals</h4>
                {suggestions.length === 0 ? (
                  <p className="text-xs text-slate-500 p-4 text-center">No zero-result searches logged in current period.</p>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    {suggestions.map((s, idx) => (
                      <div key={idx} className="p-3 bg-slate-950/60 border border-slate-800 rounded-xl flex justify-between items-center text-xs">
                        <div>
                          <p className="font-semibold text-slate-200">"{s.query_text}"</p>
                          <span className="text-[10px] text-slate-500">Last: {new Date(s.last_searched).toLocaleDateString()}</span>
                        </div>
                        <span className="px-2 py-0.5 rounded bg-cyan-950 border border-cyan-800 text-cyan-300 font-bold text-xs">
                          {s.frequency}x
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Acquisition Requests Review Triage Table */}
              <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-4 space-y-3">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Collection Development Triage</h4>
                {acquisitions.length === 0 ? (
                  <p className="text-xs text-slate-500 p-4 text-center">No acquisition requests pending review.</p>
                ) : (
                  <div className="divide-y divide-slate-800 border border-slate-800 rounded-xl overflow-hidden bg-slate-950/40">
                    {acquisitions.map((item) => (
                      <div key={item.id} className="p-3.5 flex flex-col md:flex-row justify-between items-start md:items-center gap-3 text-xs">
                        <div>
                          <div className="flex items-center space-x-2">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                                item.status === 'approved'
                                  ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                                  : item.status === 'ordered'
                                  ? 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                                  : item.status === 'received'
                                  ? 'bg-blue-950 text-blue-300 border border-blue-800'
                                  : item.status === 'rejected'
                                  ? 'bg-red-950 text-red-300 border border-red-800'
                                  : 'bg-slate-800 text-slate-300 border border-slate-700'
                              }`}
                            >
                              {item.status}
                            </span>
                            <span className="font-bold text-slate-200">{item.suggested_title}</span>
                          </div>
                          <p className="text-[11px] text-slate-400 mt-0.5">
                            Author: {item.suggested_author || 'N/A'} {item.isbn && `• ISBN: ${item.isbn}`}
                          </p>
                        </div>

                        <div className="flex items-center space-x-2">
                          {item.status === 'suggested' && (
                            <>
                              <button
                                onClick={() => handleUpdateAcquisitionStatus(item.id, 'approved')}
                                className="px-2.5 py-1 bg-emerald-900/60 hover:bg-emerald-800/60 text-emerald-300 rounded transition font-medium"
                              >
                                Approve
                              </button>
                              <button
                                onClick={() => handleUpdateAcquisitionStatus(item.id, 'rejected')}
                                className="px-2.5 py-1 bg-red-900/60 hover:bg-red-800/60 text-red-300 rounded transition font-medium"
                              >
                                Reject
                              </button>
                            </>
                          )}
                          {item.status === 'approved' && (
                            <button
                              onClick={() => handleUpdateAcquisitionStatus(item.id, 'ordered')}
                              className="px-2.5 py-1 bg-cyan-900/60 hover:bg-cyan-800/60 text-cyan-300 rounded transition font-medium"
                            >
                              Mark Ordered
                            </button>
                          )}
                          {item.status === 'ordered' && (
                            <button
                              onClick={() => handleUpdateAcquisitionStatus(item.id, 'received')}
                              className="px-2.5 py-1 bg-blue-900/60 hover:bg-blue-800/60 text-blue-300 rounded transition font-medium"
                            >
                              Mark Received
                            </button>
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
      )}

      {/* Modal: Create Acquisition Candidate */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="bg-slate-900 border border-slate-700/80 rounded-2xl w-full max-w-md overflow-hidden shadow-2xl">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/50">
              <h2 className="text-base font-bold text-slate-100">Add Acquisition Candidate</h2>
              <button onClick={() => setShowAddModal(false)} className="text-slate-400 hover:text-slate-200">✕</button>
            </div>
            <form onSubmit={handleCreateAcquisitionRequest} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Book Title *</label>
                <input
                  type="text"
                  required
                  value={reqTitle}
                  onChange={(e) => setReqTitle(e.target.value)}
                  placeholder="e.g. Deep Reinforcement Learning in Practice"
                  className="w-full bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5 focus:ring-2 focus:ring-cyan-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Author</label>
                <input
                  type="text"
                  value={reqAuthor}
                  onChange={(e) => setReqAuthor(e.target.value)}
                  placeholder="e.g. Richard S. Sutton"
                  className="w-full bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">ISBN</label>
                <input
                  type="text"
                  value={reqIsbn}
                  onChange={(e) => setReqIsbn(e.target.value)}
                  placeholder="e.g. 9780262039246"
                  className="w-full bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Notes / Rationale</label>
                <input
                  type="text"
                  value={reqNotes}
                  onChange={(e) => setReqNotes(e.target.value)}
                  placeholder="e.g. Requested for CS-400 Machine Learning seminar"
                  className="w-full bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5 focus:outline-none"
                />
              </div>

              <div className="flex justify-end space-x-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-lg transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingReq}
                  className="px-5 py-2 bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold rounded-lg transition shadow disabled:opacity-50"
                >
                  {submittingReq ? 'Submitting...' : 'Submit Request'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
