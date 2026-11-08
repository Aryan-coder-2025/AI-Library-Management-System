import React, { useEffect, useState } from 'react';
import type { Book, Course, CourseReadingListItem, CourseReserve, UserProfile } from '../types/library';

interface TeacherPortalProps {
  currentUser: UserProfile | null;
}

export const TeacherPortal: React.FC<TeacherPortalProps> = ({ currentUser }) => {
  const [courses, setCourses] = useState<Course[]>([]);
  const [selectedCourse, setSelectedCourse] = useState<Course | null>(null);
  const [readingList, setReadingList] = useState<CourseReadingListItem[]>([]);
  const [reserves, setReserves] = useState<CourseReserve[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [loadingDetails, setLoadingDetails] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // New course modal state
  const [showCourseModal, setShowCourseModal] = useState<boolean>(false);
  const [newCode, setNewCode] = useState<string>('');
  const [newTitle, setNewTitle] = useState<string>('');
  const [newDept, setNewDept] = useState<string>('');
  const [newTerm, setNewTerm] = useState<string>('Fall 2026');
  const [newDesc, setNewDesc] = useState<string>('');
  const [savingCourse, setSavingCourse] = useState<boolean>(false);

  // Add reading list item search modal
  const [showAddBookModal, setShowAddBookModal] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [searchResults, setSearchResults] = useState<Book[]>([]);
  const [searching, setSearching] = useState<boolean>(false);
  const [reqType, setReqType] = useState<'required' | 'recommended' | 'supplementary'>('required');
  const [itemNotes, setItemNotes] = useState<string>('');

  // Course reserve modal state
  const [showReserveModal, setShowReserveModal] = useState<boolean>(false);
  const [reserveCopyId, setReserveCopyId] = useState<string>('');
  const [reserveType, setReserveType] = useState<'2_hour' | '24_hour'>('2_hour');
  const [reserveNotes, setReserveNotes] = useState<string>('');
  const [savingReserve, setSavingReserve] = useState<boolean>(false);

  useEffect(() => {
    fetchCourses();
  }, []);

  useEffect(() => {
    if (selectedCourse) {
      fetchCourseDetails(selectedCourse.id);
    }
  }, [selectedCourse]);

  const fetchCourses = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch('/api/courses');
      if (res.ok) {
        const data = await res.json();
        setCourses(data.courses || []);
        if (data.courses?.length > 0 && !selectedCourse) {
          setSelectedCourse(data.courses[0]);
        }
      }
    } catch (err) {
      setError('Failed to load courses.');
    } finally {
      setLoading(false);
    }
  };

  const fetchCourseDetails = async (courseId: number) => {
    try {
      setLoadingDetails(true);
      const [resRL, resRes] = await Promise.all([
        fetch(`/api/courses/${courseId}/reading-list`),
        fetch(`/api/courses/reserves?course_id=${courseId}`),
      ]);

      if (resRL.ok) {
        const rlData = await resRL.json();
        setReadingList(rlData || []);
      }
      if (resRes.ok) {
        const resData = await resRes.json();
        setReserves(resData || []);
      }
    } catch (err) {
      console.error('Failed to load course details:', err);
    } finally {
      setLoadingDetails(false);
    }
  };

  const handleCreateCourse = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCode.trim() || !newTitle.trim() || !newDept.trim()) return;

    try {
      setSavingCourse(true);
      setError(null);
      const csrfToken = document.cookie
        .split('; ')
        .find((row) => row.startsWith('csrf_token='))
        ?.split('=')[1] || '';

      const res = await fetch('/api/courses', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken,
        },
        body: JSON.stringify({
          code: newCode.trim(),
          title: newTitle.trim(),
          department: newDept.trim(),
          term: newTerm.trim(),
          description: newDesc.trim() || undefined,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to create course.');
      }

      const created: Course = await res.json();
      setCourses((prev) => [created, ...prev]);
      setSelectedCourse(created);
      setShowCourseModal(false);
      setNewCode('');
      setNewTitle('');
      setNewDept('');
      setNewDesc('');
    } catch (err: any) {
      setError(err.message || 'Error creating course.');
    } finally {
      setSavingCourse(false);
    }
  };

  const handleSearchCatalogue = async () => {
    if (!searchQuery.trim()) return;
    try {
      setSearching(true);
      const res = await fetch(`/api/books?search=${encodeURIComponent(searchQuery)}&limit=5`);
      if (res.ok) {
        const data = await res.json();
        setSearchResults(data.books || []);
      }
    } catch (err) {
      console.error('Search failed:', err);
    } finally {
      setSearching(false);
    }
  };

  const handleAddReadingListItem = async (bookId: number) => {
    if (!selectedCourse) return;
    try {
      const csrfToken = document.cookie
        .split('; ')
        .find((row) => row.startsWith('csrf_token='))
        ?.split('=')[1] || '';

      const res = await fetch(`/api/courses/${selectedCourse.id}/reading-list`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken,
        },
        body: JSON.stringify({
          book_id: bookId,
          requirement_type: reqType,
          notes: itemNotes.trim() || undefined,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to add reading list item.');
      }

      setShowAddBookModal(false);
      setSearchQuery('');
      setSearchResults([]);
      setItemNotes('');
      fetchCourseDetails(selectedCourse.id);
      fetchCourses();
    } catch (err: any) {
      alert(err.message || 'Error adding book to reading list.');
    }
  };

  const handleRemoveReadingListItem = async (itemId: number) => {
    if (!selectedCourse || !confirm('Remove this monograph from the course reading list?')) return;
    try {
      const csrfToken = document.cookie
        .split('; ')
        .find((row) => row.startsWith('csrf_token='))
        ?.split('=')[1] || '';

      const res = await fetch(`/api/courses/${selectedCourse.id}/reading-list/${itemId}`, {
        method: 'DELETE',
        headers: { 'X-CSRF-Token': csrfToken },
      });

      if (res.ok) {
        setReadingList((prev) => prev.filter((i) => i.id !== itemId));
        fetchCourses();
      }
    } catch (err) {
      console.error('Failed to remove item:', err);
    }
  };

  const handleAddCourseReserve = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCourse || !reserveCopyId.trim()) return;

    try {
      setSavingReserve(true);
      const csrfToken = document.cookie
        .split('; ')
        .find((row) => row.startsWith('csrf_token='))
        ?.split('=')[1] || '';

      const res = await fetch(`/api/courses/${selectedCourse.id}/reserves`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken,
        },
        body: JSON.stringify({
          copy_id: parseInt(reserveCopyId),
          reserve_type: reserveType,
          notes: reserveNotes.trim() || undefined,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to designate course reserve.');
      }

      setShowReserveModal(false);
      setReserveCopyId('');
      setReserveNotes('');
      fetchCourseDetails(selectedCourse.id);
      fetchCourses();
    } catch (err: any) {
      alert(err.message || 'Error designating course reserve.');
    } finally {
      setSavingReserve(false);
    }
  };

  const handleRemoveReserve = async (reserveId: number) => {
    if (!confirm('Remove this copy from course reserve? It will return to regular circulating inventory.')) return;
    try {
      const csrfToken = document.cookie
        .split('; ')
        .find((row) => row.startsWith('csrf_token='))
        ?.split('=')[1] || '';

      const res = await fetch(`/api/courses/reserves/${reserveId}`, {
        method: 'DELETE',
        headers: { 'X-CSRF-Token': csrfToken },
      });

      if (res.ok && selectedCourse) {
        fetchCourseDetails(selectedCourse.id);
        fetchCourses();
      }
    } catch (err) {
      console.error('Failed to remove reserve:', err);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-8 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center space-x-3">
            <span className="text-3xl">🎓</span>
            <h1 className="text-2xl md:text-3xl font-extrabold text-slate-100 tracking-tight">
              Teacher Academic Resource Planner
            </h1>
          </div>
          <p className="text-slate-400 text-sm mt-1 max-w-2xl">
            Organize course reading lists, monitor real-time library inventory support for your syllabi, and designate short-term Course Reserves.
          </p>
        </div>

        {(currentUser?.role === 'teacher' || currentUser?.role === 'librarian') && (
          <button
            onClick={() => setShowCourseModal(true)}
            className="flex items-center space-x-2 px-4 py-2.5 bg-gradient-to-r from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white font-semibold text-xs rounded-xl shadow-lg transition"
          >
            <span>+</span>
            <span>Create New Course</span>
          </button>
        )}
      </div>

      {error && (
        <div className="p-4 bg-red-950/40 border border-red-800/60 rounded-xl text-xs text-red-300">
          {error}
        </div>
      )}

      {/* Main Layout: Course Sidebar + Course Content */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
        {/* Course List Sidebar */}
        <div className="space-y-4">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Academic Courses</h2>

          {loading ? (
            <div className="p-8 text-center text-xs text-slate-500">Loading courses...</div>
          ) : courses.length === 0 ? (
            <div className="p-6 bg-slate-900/60 border border-slate-800 rounded-2xl text-center text-xs text-slate-400">
              No academic courses registered yet. Click "Create New Course" to start.
            </div>
          ) : (
            <div className="space-y-2">
              {courses.map((course) => {
                const isSelected = selectedCourse?.id === course.id;
                return (
                  <button
                    key={course.id}
                    onClick={() => setSelectedCourse(course)}
                    className={`w-full text-left p-3.5 rounded-xl border transition flex flex-col justify-between ${
                      isSelected
                        ? 'bg-slate-800/90 border-cyan-500/80 shadow-md ring-1 ring-cyan-500/30'
                        : 'bg-slate-900/60 border-slate-800 hover:border-slate-700 hover:bg-slate-800/40'
                    }`}
                  >
                    <div className="flex justify-between items-center w-full">
                      <span className="font-mono text-xs font-bold text-cyan-400">{course.code}</span>
                      <span className="text-[10px] text-slate-500">{course.term}</span>
                    </div>
                    <h3 className="text-xs font-bold text-slate-200 mt-1 line-clamp-1">{course.title}</h3>
                    <div className="flex items-center space-x-3 text-[11px] text-slate-400 mt-2">
                      <span>📚 {course.reading_list_count} titles</span>
                      <span>🔒 {course.reserves_count} reserves</span>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Selected Course Content Workspace */}
        <div className="lg:col-span-3 space-y-6">
          {selectedCourse ? (
            <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6 space-y-6">
              {/* Course Banner */}
              <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 pb-6 border-b border-slate-800">
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="px-2.5 py-0.5 bg-cyan-950/80 border border-cyan-800/80 text-cyan-300 font-mono text-xs rounded-lg font-bold">
                      {selectedCourse.code}
                    </span>
                    <span className="text-xs text-slate-400">• {selectedCourse.department} • {selectedCourse.term}</span>
                  </div>
                  <h2 className="text-xl font-extrabold text-slate-100 mt-1.5">{selectedCourse.title}</h2>
                  {selectedCourse.description && (
                    <p className="text-xs text-slate-400 mt-1">{selectedCourse.description}</p>
                  )}
                  <p className="text-xs text-slate-500 mt-1">Instructor: {selectedCourse.instructor_name}</p>
                </div>

                <div className="flex space-x-3">
                  <button
                    onClick={() => setShowAddBookModal(true)}
                    className="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-cyan-300 text-xs font-semibold rounded-xl border border-slate-700 transition"
                  >
                    + Add Book to Syllabus
                  </button>
                  <button
                    onClick={() => setShowReserveModal(true)}
                    className="px-3.5 py-2 bg-gradient-to-r from-amber-600 to-amber-700 hover:from-amber-500 hover:to-amber-600 text-white text-xs font-semibold rounded-xl transition shadow"
                  >
                    🔒 Designate Course Reserve
                  </button>
                </div>
              </div>

              {/* Section 1: Syllabus Reading List */}
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <h3 className="text-sm font-bold text-slate-200">Syllabus Reading List & Inventory Availability</h3>
                  <span className="text-xs text-slate-400">{readingList.length} titles listed</span>
                </div>

                {loadingDetails ? (
                  <p className="text-xs text-slate-500">Loading syllabus items...</p>
                ) : readingList.length === 0 ? (
                  <div className="p-8 bg-slate-950/40 border border-dashed border-slate-800 rounded-xl text-center space-y-2">
                    <p className="text-xs text-slate-400">No books added to this course syllabus yet.</p>
                    <button
                      onClick={() => setShowAddBookModal(true)}
                      className="text-xs text-cyan-400 hover:underline font-semibold"
                    >
                      Search catalogue to add required textbooks
                    </button>
                  </div>
                ) : (
                  <div className="divide-y divide-slate-800/80 border border-slate-800 rounded-xl overflow-hidden bg-slate-950/30">
                    {readingList.map((item) => (
                      <div key={item.id} className="p-4 flex flex-col md:flex-row justify-between items-start md:items-center gap-3 hover:bg-slate-800/20 transition">
                        <div>
                          <div className="flex items-center space-x-2">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                                item.requirement_type === 'required'
                                  ? 'bg-rose-950/80 text-rose-300 border border-rose-800/80'
                                  : item.requirement_type === 'recommended'
                                  ? 'bg-amber-950/80 text-amber-300 border border-amber-800/80'
                                  : 'bg-slate-800 text-slate-300 border border-slate-700'
                              }`}
                            >
                              {item.requirement_type}
                            </span>
                            <h4 className="text-xs font-bold text-slate-200">{item.book_title}</h4>
                          </div>
                          <p className="text-[11px] text-slate-400 mt-0.5">
                            Author: {item.book_author || 'N/A'} {item.book_isbn && `• ISBN: ${item.book_isbn}`}
                          </p>
                          {item.notes && <p className="text-[11px] text-slate-500 italic mt-0.5">"{item.notes}"</p>}
                        </div>

                        <div className="flex items-center space-x-4">
                          <div className="text-right">
                            <span
                              className={`px-2.5 py-1 rounded-lg text-xs font-semibold ${
                                item.available_copies_count > 0
                                  ? 'bg-emerald-950/60 text-emerald-300 border border-emerald-800/60'
                                  : 'bg-red-950/60 text-red-300 border border-red-800/60'
                              }`}
                            >
                              {item.available_copies_count} of {item.total_copies_count} on shelf
                            </span>
                          </div>
                          {(currentUser?.role === 'teacher' || currentUser?.role === 'librarian') && (
                            <button
                              onClick={() => handleRemoveReadingListItem(item.id)}
                              className="text-slate-500 hover:text-red-400 text-xs p-1"
                              title="Remove from reading list"
                            >
                              ✕
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Section 2: Active Course Reserves */}
              <div className="space-y-4 pt-4 border-t border-slate-800">
                <div className="flex justify-between items-center">
                  <div>
                    <h3 className="text-sm font-bold text-slate-200">Active Course Reserves (CIRC-06)</h3>
                    <p className="text-xs text-slate-400">High-demand copies restricted to short-term reserve shelf checkouts.</p>
                  </div>
                  <span className="text-xs text-slate-400">{reserves.length} reserve copies</span>
                </div>

                {reserves.length === 0 ? (
                  <div className="p-6 bg-slate-950/20 border border-slate-800/60 rounded-xl text-center text-xs text-slate-500">
                    No physical copies currently designated as high-demand course reserves for this class.
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {reserves.map((res) => (
                      <div key={res.id} className="p-3.5 bg-slate-950/60 border border-amber-800/40 rounded-xl flex justify-between items-center">
                        <div>
                          <div className="flex items-center space-x-2">
                            <span className="font-mono text-xs font-bold text-amber-400">{res.copy_code}</span>
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-amber-950/90 text-amber-300 border border-amber-800">
                              {res.reserve_type.replace('_', ' ')} Limit
                            </span>
                          </div>
                          <h4 className="text-xs font-semibold text-slate-200 mt-1 line-clamp-1">{res.book_title}</h4>
                          {res.notes && <p className="text-[11px] text-slate-500 italic mt-0.5">"{res.notes}"</p>}
                        </div>

                        {(currentUser?.role === 'teacher' || currentUser?.role === 'librarian') && (
                          <button
                            onClick={() => handleRemoveReserve(res.id)}
                            className="px-2 py-1 bg-slate-800 hover:bg-red-950/60 text-slate-400 hover:text-red-300 text-xs rounded transition"
                          >
                            Release
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="p-12 bg-slate-900/40 border border-slate-800 rounded-2xl text-center text-xs text-slate-500">
              Select or create a course to view syllabus resources and reserves.
            </div>
          )}
        </div>
      </div>

      {/* Modal: Create Course */}
      {showCourseModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="bg-slate-900 border border-slate-700/80 rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/50">
              <h2 className="text-base font-bold text-slate-100">Create Academic Course</h2>
              <button onClick={() => setShowCourseModal(false)} className="text-slate-400 hover:text-slate-200">✕</button>
            </div>
            <form onSubmit={handleCreateCourse} className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Course Code *</label>
                  <input
                    type="text"
                    required
                    value={newCode}
                    onChange={(e) => setNewCode(e.target.value)}
                    placeholder="e.g. CS-301"
                    className="w-full bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5 focus:ring-2 focus:ring-cyan-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Academic Term *</label>
                  <input
                    type="text"
                    required
                    value={newTerm}
                    onChange={(e) => setNewTerm(e.target.value)}
                    placeholder="e.g. Fall 2026"
                    className="w-full bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5 focus:ring-2 focus:ring-cyan-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Course Title *</label>
                <input
                  type="text"
                  required
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="e.g. Quantum Algorithms and Cryptography"
                  className="w-full bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5 focus:ring-2 focus:ring-cyan-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Department *</label>
                <input
                  type="text"
                  required
                  value={newDept}
                  onChange={(e) => setNewDept(e.target.value)}
                  placeholder="e.g. Computer Science"
                  className="w-full bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5 focus:ring-2 focus:ring-cyan-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Syllabus Overview</label>
                <textarea
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  placeholder="Brief course description..."
                  rows={2}
                  className="w-full bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5 focus:ring-2 focus:ring-cyan-500 focus:outline-none"
                />
              </div>

              <div className="flex justify-end space-x-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCourseModal(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-lg transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingCourse}
                  className="px-5 py-2 bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold rounded-lg transition shadow disabled:opacity-50"
                >
                  {savingCourse ? 'Creating...' : 'Create Course'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Search Catalogue to Add to Reading List */}
      {showAddBookModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="bg-slate-900 border border-slate-700/80 rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/50">
              <h2 className="text-base font-bold text-slate-100">Add Book to Syllabus Reading List</h2>
              <button onClick={() => setShowAddBookModal(false)} className="text-slate-400 hover:text-slate-200">✕</button>
            </div>
            <div className="p-6 space-y-4">
              <div className="flex space-x-2">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearchCatalogue()}
                  placeholder="Search catalogue by title, author, or keyword..."
                  className="flex-1 bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5 focus:ring-2 focus:ring-cyan-500 focus:outline-none"
                />
                <button
                  type="button"
                  onClick={handleSearchCatalogue}
                  disabled={searching}
                  className="px-4 py-2.5 bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold rounded-lg transition"
                >
                  {searching ? '...' : 'Search'}
                </button>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Requirement Type</label>
                  <select
                    value={reqType}
                    onChange={(e: any) => setReqType(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg p-2 focus:outline-none"
                  >
                    <option value="required">Required</option>
                    <option value="recommended">Recommended</option>
                    <option value="supplementary">Supplementary</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Syllabus Notes</label>
                  <input
                    type="text"
                    value={itemNotes}
                    onChange={(e) => setItemNotes(e.target.value)}
                    placeholder="e.g. Chapters 1-4 for Midterm"
                    className="w-full bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg p-2 focus:outline-none"
                  />
                </div>
              </div>

              <div className="space-y-2 max-h-56 overflow-y-auto">
                {searchResults.map((b) => (
                  <div key={b.id} className="p-3 bg-slate-950/60 border border-slate-800 rounded-xl flex justify-between items-center text-xs">
                    <div>
                      <h4 className="font-bold text-slate-200">{b.title}</h4>
                      <p className="text-[11px] text-slate-400">{b.author} • {b.category}</p>
                    </div>
                    <button
                      onClick={() => handleAddReadingListItem(b.id)}
                      className="px-3 py-1 bg-cyan-600 hover:bg-cyan-500 text-white font-semibold text-xs rounded-lg transition"
                    >
                      + Add
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Designate Course Reserve */}
      {showReserveModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="bg-slate-900 border border-slate-700/80 rounded-2xl w-full max-w-md overflow-hidden shadow-2xl">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/50">
              <h2 className="text-base font-bold text-slate-100">Designate Course Reserve</h2>
              <button onClick={() => setShowReserveModal(false)} className="text-slate-400 hover:text-slate-200">✕</button>
            </div>
            <form onSubmit={handleAddCourseReserve} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Physical Copy ID *</label>
                <input
                  type="number"
                  required
                  value={reserveCopyId}
                  onChange={(e) => setReserveCopyId(e.target.value)}
                  placeholder="Enter Copy ID (e.g. 101)"
                  className="w-full bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5 focus:ring-2 focus:ring-amber-500 focus:outline-none"
                />
                <p className="text-[11px] text-slate-500 mt-1">Copy must currently have 'available' operational status.</p>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Reserve Duration Limit *</label>
                <select
                  value={reserveType}
                  onChange={(e: any) => setReserveType(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5 focus:ring-2 focus:ring-amber-500 focus:outline-none"
                >
                  <option value="2_hour">2-Hour In-Library Reserve</option>
                  <option value="24_hour">24-Hour Overnight Reserve</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Notes</label>
                <input
                  type="text"
                  value={reserveNotes}
                  onChange={(e) => setReserveNotes(e.target.value)}
                  placeholder="e.g. Dedicated for Exam Prep week"
                  className="w-full bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5 focus:outline-none"
                />
              </div>

              <div className="flex justify-end space-x-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowReserveModal(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-lg transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingReserve}
                  className="px-5 py-2 bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold rounded-lg transition shadow disabled:opacity-50"
                >
                  {savingReserve ? 'Designating...' : 'Confirm Reserve'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
