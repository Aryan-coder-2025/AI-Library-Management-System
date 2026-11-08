import React, { useEffect, useState } from 'react';
import { apiFetch } from '../services/apiClient';
import type { Book, Course, CourseReadingListItem, CourseReserve, UserProfile } from '../types/library';

interface TeacherPortalProps {
  currentUser: UserProfile | null;
}

interface BookPaginationResponse {
  items: Book[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
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
  const [selectedCategory, setSelectedCategory] = useState<string>('All Categories');
  const [searchResults, setSearchResults] = useState<Book[]>([]);
  const [searchPage, setSearchPage] = useState<number>(1);
  const [totalSearchCount, setTotalSearchCount] = useState<number>(0);
  const [totalSearchPages, setTotalSearchPages] = useState<number>(1);
  const [searching, setSearching] = useState<boolean>(false);
  const [isPaginating, setIsPaginating] = useState<boolean>(false);
  const [hasSearched, setHasSearched] = useState<boolean>(false);
  const [reqType, setReqType] = useState<'required' | 'recommended' | 'supplementary'>('required');
  const [itemNotes, setItemNotes] = useState<string>('');
  const [addingBookId, setAddingBookId] = useState<number | null>(null);

  const ACADEMIC_CATEGORIES = [
    'All Categories',
    'Artificial Intelligence',
    'Computer Science',
    'Algorithms & Complexity',
    'Data Science',
    'Cybersecurity & Cryptography',
    'Distributed Systems',
    'Software Engineering',
    'Robotics',
    'Mathematics',
    'Physics',
    'Information Systems',
    'Philosophy of Technology',
  ];

  // Course reserve modal state
  const [showReserveModal, setShowReserveModal] = useState<boolean>(false);
  const [reserveCopyId, setReserveCopyId] = useState<string>('');
  const [reserveType, setReserveType] = useState<'2_hour' | '24_hour'>('2_hour');
  const [reserveNotes, setReserveNotes] = useState<string>('');
  const [savingReserve, setSavingReserve] = useState<boolean>(false);

  // Live Toast & Export Syllabus Modal
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [showExportModal, setShowExportModal] = useState<boolean>(false);
  const [copyFeedback, setCopyFeedback] = useState<boolean>(false);

  const canManage = currentUser?.role === 'teacher' || currentUser?.role === 'librarian';

  useEffect(() => {
    if (toastMessage) {
      const timer = setTimeout(() => setToastMessage(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [toastMessage]);

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
      const data = await apiFetch<{ courses: Course[] }>('/api/courses');
      setCourses(data.courses || []);
      if (data.courses?.length > 0 && !selectedCourse) {
        setSelectedCourse(data.courses[0]);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load courses.';
      setError(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setLoading(false);
    }
  };

  const fetchCourseDetails = async (courseId: number) => {
    try {
      setLoadingDetails(true);
      const [rlData, resData] = await Promise.all([
        apiFetch<CourseReadingListItem[]>(`/api/courses/${courseId}/reading-list`),
        apiFetch<CourseReserve[]>(`/api/courses/reserves?course_id=${courseId}`),
      ]);
      setReadingList(rlData || []);
      setReserves(resData || []);
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
      const created = await apiFetch<Course>('/api/courses', {
        method: 'POST',
        body: JSON.stringify({
          code: newCode.trim(),
          title: newTitle.trim(),
          department: newDept.trim(),
          term: newTerm.trim(),
          description: newDesc.trim() || undefined,
        }),
      });

      setCourses((prev) => [created, ...prev]);
      setSelectedCourse(created);
      setShowCourseModal(false);
      setNewCode('');
      setNewTitle('');
      setNewDept('');
      setNewDesc('');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error creating course.';
      setError(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setSavingCourse(false);
    }
  };

  const handleSearchCatalogue = async (
    page: number = 1,
    overrideCat?: string,
    overrideQ?: string,
    isPaginationClick: boolean = false
  ) => {
    try {
      if (isPaginationClick) {
        setIsPaginating(true);
      } else {
        setSearching(true);
      }
      setHasSearched(true);
      const cat = overrideCat !== undefined ? overrideCat : selectedCategory;
      const q = overrideQ !== undefined ? overrideQ : searchQuery;
      const params = new URLSearchParams();
      if (q.trim()) params.set('search', q.trim());
      if (cat && cat !== 'All Categories') params.set('category', cat);
      params.set('page', String(page));
      params.set('page_size', '12');

      const data = await apiFetch<BookPaginationResponse>(`/api/books?${params.toString()}`);
      setSearchResults(data.items || []);
      setTotalSearchCount(data.total || 0);
      setTotalSearchPages(data.total_pages || 1);
      setSearchPage(page);
    } catch (err) {
      console.error('Search failed:', err);
      setSearchResults([]);
      setTotalSearchCount(0);
      setTotalSearchPages(1);
    } finally {
      setSearching(false);
      setIsPaginating(false);
    }
  };

  const openAddBookModal = () => {
    const initialQ = '';
    const initialCat = selectedCourse?.department && ACADEMIC_CATEGORIES.includes(selectedCourse.department)
      ? selectedCourse.department
      : 'All Categories';
    setSearchQuery(initialQ);
    setSelectedCategory(initialCat);
    setHasSearched(false);
    setShowAddBookModal(true);
    handleSearchCatalogue(1, initialCat, initialQ);
  };

  const handleAddReadingListItem = async (bookId: number) => {
    if (!selectedCourse) return;
    const addedBook = searchResults.find((b) => b.id === bookId);
    try {
      setAddingBookId(bookId);
      await apiFetch(`/api/courses/${selectedCourse.id}/reading-list`, {
        method: 'POST',
        body: JSON.stringify({
          book_id: bookId,
          requirement_type: reqType,
          notes: itemNotes.trim() || undefined,
        }),
      });

      setShowAddBookModal(false);
      setSearchQuery('');
      setSearchResults([]);
      setItemNotes('');
      fetchCourseDetails(selectedCourse.id);
      fetchCourses();
      setToastMessage(`✓ "${addedBook?.title || 'Book'}" saved live to ${selectedCourse.code} syllabus.`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error adding monograph to reading list.';
      alert(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setAddingBookId(null);
    }
  };

  const handleRemoveReadingListItem = async (itemId: number) => {
    if (!selectedCourse || !confirm('Remove this monograph from course reading list?')) return;
    const itemToRemove = readingList.find((i) => i.id === itemId);
    try {
      await apiFetch(`/api/courses/${selectedCourse.id}/reading-list/${itemId}`, {
        method: 'DELETE',
      });
      setReadingList((prev) => prev.filter((i) => i.id !== itemId));
      fetchCourses();
      setToastMessage(`Removed "${itemToRemove?.book_title || 'item'}" from ${selectedCourse.code} syllabus.`);
    } catch (err) {
      console.error('Failed to remove item:', err);
    }
  };

  const handleAddCourseReserve = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCourse || !reserveCopyId.trim()) return;

    try {
      setSavingReserve(true);
      await apiFetch(`/api/courses/${selectedCourse.id}/reserves`, {
        method: 'POST',
        body: JSON.stringify({
          copy_id: parseInt(reserveCopyId.trim(), 10),
          reserve_type: reserveType,
          notes: reserveNotes.trim() || undefined,
        }),
      });

      const copyCode = reserveCopyId.trim();
      setShowReserveModal(false);
      setReserveCopyId('');
      setReserveNotes('');
      fetchCourseDetails(selectedCourse.id);
      fetchCourses();
      setToastMessage(`✓ Copy #${copyCode} designated as ${reserveType.replace('_', '-')} course reserve.`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error designating course reserve.';
      alert(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setSavingReserve(false);
    }
  };

  const handleRemoveReserve = async (reserveId: number) => {
    if (!selectedCourse || !confirm('Release this physical copy from short-term course reserve?')) return;
    try {
      await apiFetch(`/api/courses/reserves/${reserveId}`, {
        method: 'DELETE',
      });
      setReserves((prev) => prev.filter((r) => r.id !== reserveId));
      fetchCourseDetails(selectedCourse.id);
      fetchCourses();
      setToastMessage(`Released reserve copy from circulation hold.`);
    } catch (err) {
      console.error('Failed to remove reserve:', err);
    }
  };

  const generateSyllabusMarkdown = () => {
    if (!selectedCourse) return '';
    let md = `# ${selectedCourse.code}: ${selectedCourse.title}\n`;
    md += `**Academic Discipline:** ${selectedCourse.department} | **Term:** ${selectedCourse.term}\n`;
    md += `**Instructor:** ${selectedCourse.instructor_name || 'Faculty'}\n\n`;
    if (selectedCourse.description) {
      md += `${selectedCourse.description}\n\n`;
    }
    md += `## Required & Recommended Library Course Readings\n\n`;
    if (readingList.length === 0) {
      md += `*No assigned monographs at this time.*\n`;
    } else {
      readingList.forEach((item, idx) => {
        const tag = item.requirement_type ? item.requirement_type.toUpperCase() : 'REQUIRED';
        md += `${idx + 1}. **${item.book_title}**\n`;
        md += `   - Author: ${item.book_author || 'N/A'}\n`;
        if (item.book_isbn) md += `   - ISBN: ${item.book_isbn}\n`;
        md += `   - Syllabus Requirement: ${tag}\n`;
        md += `   - Library Shelf Status: ${item.available_copies_count ?? 0} of ${item.total_copies_count ?? 0} copies currently on shelf\n`;
        if (item.notes) md += `   - Syllabus Assignment: ${item.notes}\n`;
        md += `\n`;
      });
    }

    if (reserves.length > 0) {
      md += `## Active Short-Term Course Reserves (CIRC-06 Policy)\n\n`;
      reserves.forEach((res, idx) => {
        md += `${idx + 1}. **${res.book_title || `Copy #${res.copy_id}`}** (Copy #${res.copy_id})\n`;
        md += `   - Policy: ${res.reserve_type.replace('_', '-')} Front Desk Checkout Only\n`;
        if (res.notes) md += `   - Notes: ${res.notes}\n`;
        md += `\n`;
      });
    }

    return md;
  };

  const handleCopyToClipboard = async () => {
    const text = generateSyllabusMarkdown();
    try {
      await navigator.clipboard.writeText(text);
      setCopyFeedback(true);
      setTimeout(() => setCopyFeedback(false), 2500);
    } catch (e) {
      console.error('Failed to copy to clipboard', e);
    }
  };

  const handleDownloadMarkdown = () => {
    if (!selectedCourse) return;
    const text = generateSyllabusMarkdown();
    const blob = new Blob([text], { type: 'text/markdown;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `${selectedCourse.code}_Syllabus_Reading_List.md`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div style={{ maxWidth: '1360px', margin: '0 auto', padding: '1.5rem 1.25rem', display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      {/* Hero Card Header */}
      <div
        style={{
          background: 'linear-gradient(135deg, rgba(30, 41, 69, 0.7) 0%, rgba(19, 27, 46, 0.9) 100%)',
          border: '1px solid var(--border-medium, #29334F)',
          borderRadius: 'var(--radius-lg, 16px)',
          padding: '1.75rem 2rem',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '1.25rem',
          boxShadow: 'var(--shadow-md, 0 8px 24px rgba(0,0,0,0.25))',
        }}
      >
        <div>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.45rem', padding: '0.2rem 0.65rem', borderRadius: '9999px', background: 'rgba(6, 182, 212, 0.12)', border: '1px solid rgba(6, 182, 212, 0.3)', color: '#38BDF8', fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase', marginBottom: '0.5rem' }}>
            <span>🎓</span> Academic Faculty Portal
          </div>
          <h1 style={{ fontSize: '1.65rem', fontWeight: 800, color: 'var(--text-primary, #F5F6FF)', letterSpacing: '-0.02em', margin: 0 }}>
            Teacher Academic Resource Planner
          </h1>
          <p style={{ color: 'var(--text-muted, #77829E)', fontSize: '0.85rem', marginTop: '0.35rem', marginBottom: 0, maxWidth: '640px' }}>
            Organize course reading lists, monitor live physical library inventory support for your syllabi, and designate short-term high-demand course reserves.
          </p>
        </div>

        {canManage && (
          <button
            type="button"
            onClick={() => setShowCourseModal(true)}
            style={{
              padding: '0.65rem 1.25rem',
              borderRadius: '10px',
              border: 'none',
              background: 'linear-gradient(135deg, #06B6D4 0%, #3B82F6 100%)',
              color: '#FFFFFF',
              fontWeight: 700,
              fontSize: '0.82rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.45rem',
              boxShadow: '0 4px 14px rgba(6, 182, 212, 0.35)',
              transition: 'transform 0.15s ease',
            }}
          >
            <span>+</span> Create New Course
          </button>
        )}
      </div>

      {error && (
        <div style={{ padding: '0.85rem 1.25rem', borderRadius: '10px', background: 'rgba(239, 68, 68, 0.12)', border: '1px solid rgba(239, 68, 68, 0.35)', color: '#FCA5A5', fontSize: '0.82rem' }}>
          {error}
        </div>
      )}

      {/* Main Grid: Sidebar + Selected Course Workspace */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(280px, 320px) 1fr', gap: '1.5rem', alignItems: 'start' }}>
        {/* Left Column: Course Sidebar */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-muted, #77829E)' }}>
              Academic Courses ({courses.length})
            </span>
          </div>

          {loading ? (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.82rem' }}>
              Loading courses...
            </div>
          ) : courses.length === 0 ? (
            <div
              style={{
                padding: '1.5rem',
                borderRadius: '12px',
                background: 'var(--bg-card, #131B2E)',
                border: '1px dashed var(--border-medium, #29334F)',
                textAlign: 'center',
                color: 'var(--text-muted, #77829E)',
                fontSize: '0.82rem',
              }}
            >
              No courses registered yet. Click "+ Create New Course" above to add your syllabus.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
              {courses.map((course) => {
                const isSelected = selectedCourse?.id === course.id;
                return (
                  <button
                    key={course.id}
                    type="button"
                    onClick={() => setSelectedCourse(course)}
                    style={{
                      width: '100%',
                      textAlign: 'left',
                      padding: '1rem 1.15rem',
                      borderRadius: '12px',
                      border: isSelected ? '1px solid #06B6D4' : '1px solid var(--border-medium, #29334F)',
                      background: isSelected
                        ? 'linear-gradient(135deg, rgba(6, 182, 212, 0.15) 0%, rgba(30, 41, 69, 0.7) 100%)'
                        : 'var(--bg-card, #131B2E)',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                      boxShadow: isSelected ? '0 0 16px rgba(6, 182, 212, 0.2)' : 'none',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
                      <span style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: '0.82rem', fontWeight: 800, color: '#38BDF8' }}>
                        {course.code}
                      </span>
                      <span style={{ fontSize: '0.72rem', color: 'var(--text-muted, #77829E)' }}>{course.term}</span>
                    </div>
                    <div style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--text-primary, #F5F6FF)', marginBottom: '0.45rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {course.title}
                    </div>
                    <div style={{ display: 'flex', gap: '0.75rem', fontSize: '0.75rem', color: 'var(--text-muted, #77829E)' }}>
                      <span>📚 {course.reading_list_count ?? 0} titles</span>
                      <span>🔒 {course.reserves_count ?? 0} reserves</span>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Column: Course Workspace */}
        <div>
          {selectedCourse ? (
            <div
              style={{
                background: 'var(--bg-card, #131B2E)',
                border: '1px solid var(--border-medium, #29334F)',
                borderRadius: 'var(--radius-lg, 16px)',
                padding: '1.75rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '1.5rem',
              }}
            >
              {/* Course Banner Header */}
              <div
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  gap: '1rem',
                  paddingBottom: '1.25rem',
                  borderBottom: '1px solid var(--border-medium, #29334F)',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem', flexWrap: 'wrap' }}>
                    <span style={{ padding: '0.2rem 0.6rem', borderRadius: '6px', background: 'rgba(6, 182, 212, 0.15)', border: '1px solid rgba(6, 182, 212, 0.35)', color: '#38BDF8', fontFamily: 'var(--font-mono, monospace)', fontWeight: 800, fontSize: '0.78rem' }}>
                      {selectedCourse.code}
                    </span>
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted, #77829E)' }}>
                      • {selectedCourse.department} • {selectedCourse.term}
                    </span>
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.35rem',
                        fontSize: '0.7rem',
                        fontWeight: 700,
                        padding: '0.15rem 0.55rem',
                        borderRadius: '12px',
                        background: 'rgba(16, 185, 129, 0.12)',
                        border: '1px solid rgba(16, 185, 129, 0.35)',
                        color: '#6EE7B7',
                      }}
                      title="All course reading list and reserve changes are automatically persisted in real-time"
                    >
                      <span style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', background: '#10B981', boxShadow: '0 0 6px #10B981' }} />
                      Live Synced
                    </span>
                  </div>
                  <h2 style={{ fontSize: '1.35rem', fontWeight: 800, color: 'var(--text-primary, #F5F6FF)', margin: 0 }}>
                    {selectedCourse.title}
                  </h2>
                  {selectedCourse.description && (
                    <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary, #A0AEC0)', marginTop: '0.35rem', marginBottom: 0 }}>
                      {selectedCourse.description}
                    </p>
                  )}
                  <p style={{ fontSize: '0.76rem', color: 'var(--text-muted, #77829E)', marginTop: '0.25rem', marginBottom: 0 }}>
                    Instructor: <strong>{selectedCourse.instructor_name || 'Prof. Faculty'}</strong>
                  </p>
                </div>

                {canManage && (
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      onClick={openAddBookModal}
                      style={{
                        padding: '0.55rem 0.95rem',
                        borderRadius: '8px',
                        border: '1px solid #06B6D4',
                        background: 'rgba(6, 182, 212, 0.1)',
                        color: '#38BDF8',
                        fontWeight: 700,
                        fontSize: '0.78rem',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.35rem',
                      }}
                    >
                      <span>+</span> Add Book to Syllabus
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowReserveModal(true)}
                      style={{
                        padding: '0.55rem 0.95rem',
                        borderRadius: '8px',
                        border: '1px solid rgba(245, 158, 11, 0.5)',
                        background: 'rgba(245, 158, 11, 0.12)',
                        color: '#FBBF24',
                        fontWeight: 700,
                        fontSize: '0.78rem',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.35rem',
                      }}
                    >
                      <span>🔒</span> Designate Reserve
                    </button>
                    <button
                      type="button"
                      disabled={readingList.length === 0}
                      onClick={() => setShowExportModal(true)}
                      style={{
                        padding: '0.55rem 0.95rem',
                        borderRadius: '8px',
                        border: '1px solid rgba(139, 92, 246, 0.45)',
                        background: 'rgba(139, 92, 246, 0.12)',
                        color: '#C4B5FD',
                        fontWeight: 700,
                        fontSize: '0.78rem',
                        cursor: readingList.length === 0 ? 'not-allowed' : 'pointer',
                        opacity: readingList.length === 0 ? 0.5 : 1,
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.35rem',
                      }}
                      title="Export syllabus citations and bibliography for Canvas, LMS, or printing"
                    >
                      <span>📄</span> Export Reading List
                    </button>
                  </div>
                )}
              </div>

              {/* Section 1: Syllabus Reading List */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.85rem' }}>
                  <h3 style={{ fontSize: '0.98rem', fontWeight: 800, color: 'var(--text-primary, #F5F6FF)', margin: 0 }}>
                    Syllabus Reading List & Inventory Availability
                  </h3>
                  <span style={{ fontSize: '0.76rem', color: 'var(--text-muted, #77829E)' }}>
                    {readingList.length} monograph{readingList.length === 1 ? '' : 's'} assigned
                  </span>
                </div>

                {loadingDetails ? (
                  <div style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.82rem' }}>
                    Loading syllabus items...
                  </div>
                ) : readingList.length === 0 ? (
                  <div
                    style={{
                      padding: '2rem',
                      borderRadius: '12px',
                      background: 'rgba(15, 23, 42, 0.4)',
                      border: '1px dashed var(--border-medium, #29334F)',
                      textAlign: 'center',
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      gap: '0.45rem',
                    }}
                  >
                    <span style={{ fontSize: '1.5rem' }}>📖</span>
                    <span style={{ color: 'var(--text-muted, #77829E)', fontSize: '0.82rem' }}>
                      No monographs added to this course syllabus yet.
                    </span>
                    {canManage && (
                      <button
                        type="button"
                        onClick={openAddBookModal}
                        style={{
                          background: 'none',
                          border: 'none',
                          color: '#38BDF8',
                          fontSize: '0.78rem',
                          fontWeight: 700,
                          cursor: 'pointer',
                          padding: 0,
                          textDecoration: 'underline',
                        }}
                      >
                        Search catalogue to add required or recommended textbooks
                      </button>
                    )}
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                    {readingList.map((item) => {
                      const reqBadgeColor =
                        item.requirement_type === 'required'
                          ? { bg: 'rgba(239, 68, 68, 0.15)', border: 'rgba(239, 68, 68, 0.4)', text: '#FCA5A5' }
                          : item.requirement_type === 'recommended'
                          ? { bg: 'rgba(245, 158, 11, 0.15)', border: 'rgba(245, 158, 11, 0.4)', text: '#FCD34D' }
                          : { bg: 'rgba(100, 116, 139, 0.15)', border: 'rgba(100, 116, 139, 0.4)', text: '#CBD5E1' };

                      const isAvail = (item.available_copies_count ?? 0) > 0;

                      return (
                        <div
                          key={item.id}
                          style={{
                            padding: '0.95rem 1.15rem',
                            borderRadius: '10px',
                            background: 'rgba(15, 23, 42, 0.5)',
                            border: '1px solid var(--border-medium, #29334F)',
                            display: 'flex',
                            flexWrap: 'wrap',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            gap: '0.85rem',
                          }}
                        >
                          <div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.2rem' }}>
                              <span
                                style={{
                                  padding: '0.15rem 0.45rem',
                                  borderRadius: '4px',
                                  fontSize: '0.68rem',
                                  fontWeight: 800,
                                  textTransform: 'uppercase',
                                  letterSpacing: '0.04em',
                                  background: reqBadgeColor.bg,
                                  border: `1px solid ${reqBadgeColor.border}`,
                                  color: reqBadgeColor.text,
                                }}
                              >
                                {item.requirement_type}
                              </span>
                              <span style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-primary, #F5F6FF)' }}>
                                {item.book_title}
                              </span>
                            </div>
                            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted, #77829E)' }}>
                              Author: {item.book_author || 'N/A'} {item.book_isbn && `• ISBN: ${item.book_isbn}`}
                            </div>
                            {item.notes && (
                              <div style={{ fontSize: '0.75rem', color: '#93C5FD', fontStyle: 'italic', marginTop: '0.15rem' }}>
                                "{item.notes}"
                              </div>
                            )}
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', flexWrap: 'wrap' }}>
                            {item.requirement_type === 'required' && (item.available_copies_count ?? 0) <= 1 && (item.total_copies_count ?? 0) > 0 && (
                              <span
                                style={{
                                  padding: '0.3rem 0.6rem',
                                  borderRadius: '8px',
                                  fontSize: '0.72rem',
                                  fontWeight: 700,
                                  background: 'rgba(245, 158, 11, 0.12)',
                                  border: '1px solid rgba(245, 158, 11, 0.4)',
                                  color: '#FCD34D',
                                }}
                                title="High-demand required monograph with 1 or fewer copies on shelf. Recommended to designate a short-term desk reserve."
                              >
                                ⚠️ Low Shelf Stock
                              </span>
                            )}
                            <span
                              style={{
                                padding: '0.35rem 0.75rem',
                                borderRadius: '8px',
                                fontSize: '0.75rem',
                                fontWeight: 700,
                                background: isAvail ? 'rgba(16, 185, 129, 0.12)' : 'rgba(239, 68, 68, 0.12)',
                                border: isAvail ? '1px solid rgba(16, 185, 129, 0.35)' : '1px solid rgba(239, 68, 68, 0.35)',
                                color: isAvail ? '#6EE7B7' : '#FCA5A5',
                              }}
                            >
                              {item.available_copies_count ?? 0} of {item.total_copies_count ?? 0} on shelf
                            </span>

                            {canManage && (
                              <button
                                type="button"
                                onClick={() => handleRemoveReadingListItem(item.id)}
                                title="Remove from reading list"
                                style={{
                                  background: 'none',
                                  border: 'none',
                                  color: 'var(--text-muted, #77829E)',
                                  fontSize: '0.95rem',
                                  cursor: 'pointer',
                                  padding: '0.2rem 0.4rem',
                                  borderRadius: '4px',
                                }}
                                onMouseEnter={(e) => (e.currentTarget.style.color = '#EF4444')}
                                onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted, #77829E)')}
                              >
                                ✕
                              </button>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Section 2: Active Course Reserves */}
              <div style={{ paddingTop: '1.25rem', borderTop: '1px solid var(--border-medium, #29334F)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.85rem' }}>
                  <div>
                    <h3 style={{ fontSize: '0.98rem', fontWeight: 800, color: 'var(--text-primary, #F5F6FF)', margin: 0 }}>
                      Active Course Reserves (CIRC-06)
                    </h3>
                    <p style={{ fontSize: '0.76rem', color: 'var(--text-muted, #77829E)', margin: '0.15rem 0 0 0' }}>
                      Designated physical copies held at the circulation desk for short-term fair patron checkout.
                    </p>
                  </div>
                  <span style={{ fontSize: '0.76rem', color: 'var(--text-muted, #77829E)' }}>
                    {reserves.length} reserve cop{reserves.length === 1 ? 'y' : 'ies'}
                  </span>
                </div>

                {reserves.length === 0 ? (
                  <div
                    style={{
                      padding: '1.5rem',
                      borderRadius: '12px',
                      background: 'rgba(15, 23, 42, 0.4)',
                      border: '1px solid var(--border-medium, #29334F)',
                      textAlign: 'center',
                      color: 'var(--text-muted, #77829E)',
                      fontSize: '0.82rem',
                    }}
                  >
                    No physical copies currently designated as high-demand course reserves for this class.
                  </div>
                ) : (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '0.85rem' }}>
                    {reserves.map((res) => (
                      <div
                        key={res.id}
                        style={{
                          padding: '0.95rem 1.15rem',
                          borderRadius: '10px',
                          background: 'rgba(15, 23, 42, 0.6)',
                          border: '1px solid rgba(245, 158, 11, 0.35)',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          gap: '0.85rem',
                        }}
                      >
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', marginBottom: '0.2rem' }}>
                            <span style={{ fontFamily: 'var(--font-mono, monospace)', fontWeight: 800, fontSize: '0.78rem', color: '#FBBF24' }}>
                              {res.copy_code}
                            </span>
                            <span style={{ padding: '0.15rem 0.45rem', borderRadius: '4px', fontSize: '0.68rem', fontWeight: 800, textTransform: 'uppercase', background: 'rgba(245, 158, 11, 0.15)', border: '1px solid rgba(245, 158, 11, 0.4)', color: '#FCD34D' }}>
                              {res.reserve_type.replace('_', ' ')} Limit
                            </span>
                          </div>
                          <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary, #F5F6FF)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '220px' }}>
                            {res.book_title}
                          </div>
                          {res.notes && (
                            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted, #77829E)', fontStyle: 'italic', marginTop: '0.15rem' }}>
                              "{res.notes}"
                            </div>
                          )}
                        </div>

                        {canManage && (
                          <button
                            type="button"
                            onClick={() => handleRemoveReserve(res.id)}
                            style={{
                              padding: '0.35rem 0.65rem',
                              borderRadius: '6px',
                              border: '1px solid var(--border-medium, #29334F)',
                              background: 'rgba(239, 68, 68, 0.1)',
                              color: '#FCA5A5',
                              fontSize: '0.72rem',
                              fontWeight: 700,
                              cursor: 'pointer',
                            }}
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
            <div
              style={{
                background: 'var(--bg-card, #131B2E)',
                border: '1px solid var(--border-medium, #29334F)',
                borderRadius: 'var(--radius-lg, 16px)',
                padding: '3rem',
                textAlign: 'center',
                color: 'var(--text-muted, #77829E)',
                fontSize: '0.85rem',
              }}
            >
              Select or create an academic course on the left to manage syllabus monographs and short-term reserves.
            </div>
          )}
        </div>
      </div>

      {/* Floating Modal: Create Course */}
      {showCourseModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(5, 7, 15, 0.82)',
            backdropFilter: 'blur(8px)',
            zIndex: 1200,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1rem',
          }}
          onClick={() => setShowCourseModal(false)}
        >
          <div
            style={{
              background: 'var(--bg-card, #131B2E)',
              border: '1px solid var(--border-medium, #29334F)',
              borderRadius: '16px',
              maxWidth: '520px',
              width: '100%',
              overflow: 'hidden',
              boxShadow: '0 20px 48px rgba(0,0,0,0.6)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1.15rem 1.5rem', borderBottom: '1px solid var(--border-medium, #29334F)' }}>
              <h2 style={{ fontSize: '1.05rem', fontWeight: 800, color: 'var(--text-primary, #F5F6FF)', margin: 0 }}>
                Create Academic Course
              </h2>
              <button
                type="button"
                onClick={() => setShowCourseModal(false)}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted, #77829E)', fontSize: '1.1rem', cursor: 'pointer', padding: 0 }}
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateCourse} style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.85rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary, #A0AEC0)', marginBottom: '0.35rem' }}>
                    Course Code *
                  </label>
                  <input
                    type="text"
                    required
                    value={newCode}
                    onChange={(e) => setNewCode(e.target.value)}
                    placeholder="e.g. CS-301"
                    className="form-input"
                    style={{ width: '100%' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary, #A0AEC0)', marginBottom: '0.35rem' }}>
                    Academic Term *
                  </label>
                  <input
                    type="text"
                    required
                    value={newTerm}
                    onChange={(e) => setNewTerm(e.target.value)}
                    placeholder="e.g. Fall 2026"
                    className="form-input"
                    style={{ width: '100%' }}
                  />
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary, #A0AEC0)', marginBottom: '0.35rem' }}>
                  Course Title *
                </label>
                <input
                  type="text"
                  required
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="e.g. Distributed Systems Engineering"
                  className="form-input"
                  style={{ width: '100%' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary, #A0AEC0)', marginBottom: '0.35rem' }}>
                  Department *
                </label>
                <input
                  type="text"
                  required
                  value={newDept}
                  onChange={(e) => setNewDept(e.target.value)}
                  placeholder="e.g. Computer Science"
                  className="form-input"
                  style={{ width: '100%' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary, #A0AEC0)', marginBottom: '0.35rem' }}>
                  Syllabus Overview
                </label>
                <textarea
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  placeholder="Brief course objectives and syllabus description..."
                  rows={2}
                  className="form-textarea"
                  style={{ width: '100%' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.65rem', paddingTop: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => setShowCourseModal(false)}
                  className="btn btn-secondary"
                  style={{ fontSize: '0.8rem' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingCourse}
                  className="btn btn-primary"
                  style={{ fontSize: '0.8rem' }}
                >
                  {savingCourse ? 'Creating...' : 'Create Course'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Floating Modal: Add Book to Syllabus Reading List */}
      {showAddBookModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(5, 7, 15, 0.82)',
            backdropFilter: 'blur(8px)',
            zIndex: 1200,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1rem',
          }}
          onClick={() => setShowAddBookModal(false)}
        >
          <div
            style={{
              background: 'var(--bg-card, #131B2E)',
              border: '1px solid var(--border-medium, #29334F)',
              borderRadius: '16px',
              maxWidth: '720px',
              width: '100%',
              overflow: 'hidden',
              boxShadow: '0 20px 48px rgba(0,0,0,0.6)',
              display: 'flex',
              flexDirection: 'column',
              maxHeight: '88vh',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1.15rem 1.5rem', borderBottom: '1px solid var(--border-medium, #29334F)' }}>
              <div>
                <h2 style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--text-primary, #F5F6FF)', margin: 0 }}>
                  Add Book to Syllabus Reading List
                </h2>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted, #77829E)' }}>
                  {selectedCourse?.code}: {selectedCourse?.title}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setShowAddBookModal(false)}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted, #77829E)', fontSize: '1.1rem', cursor: 'pointer', padding: 0 }}
              >
                ✕
              </button>
            </div>

            <div style={{ padding: '1.25rem 1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem', overflowY: 'auto' }}>
              {/* Search & Academic Category Filter Bar */}
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSearchCatalogue(1);
                }}
                style={{ display: 'grid', gridTemplateColumns: '1fr minmax(180px, 220px) auto', gap: '0.5rem' }}
              >
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search title, author, or keyword..."
                  className="form-input"
                />
                <select
                  value={selectedCategory}
                  onChange={(e) => {
                    const newCat = e.target.value;
                    setSelectedCategory(newCat);
                    handleSearchCatalogue(1, newCat, searchQuery);
                  }}
                  className="form-select"
                >
                  {ACADEMIC_CATEGORIES.map((cat) => (
                    <option key={cat} value={cat}>
                      {cat}
                    </option>
                  ))}
                </select>
                <button
                  type="submit"
                  disabled={searching || isPaginating}
                  className="btn btn-primary"
                  style={{ fontSize: '0.8rem', whiteSpace: 'nowrap', minWidth: '72px' }}
                >
                  {searching ? '...' : 'Search'}
                </button>
              </form>

              {/* Requirement Tag & Notes: Clearly labeled as settings applied upon adding */}
              <div
                style={{
                  padding: '0.75rem 1rem',
                  borderRadius: '10px',
                  background: 'rgba(15, 23, 42, 0.45)',
                  border: '1px solid var(--border-medium, #29334F)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.45rem',
                }}
              >
                <div style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-muted, #77829E)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  📌 Syllabus Tag to Apply on Add:
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'minmax(180px, 220px) 1fr', gap: '0.75rem' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-secondary, #A0AEC0)', marginBottom: '0.2rem' }}>
                      Requirement Level
                    </label>
                    <select
                      value={reqType}
                      onChange={(e: any) => setReqType(e.target.value)}
                      className="form-select"
                      style={{ width: '100%' }}
                    >
                      <option value="required">🔴 Required Syllabus</option>
                      <option value="recommended">🟡 Recommended Reading</option>
                      <option value="supplementary">⚪ Supplementary Reference</option>
                    </select>
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-secondary, #A0AEC0)', marginBottom: '0.2rem' }}>
                      Syllabus Notes (Optional)
                    </label>
                    <input
                      type="text"
                      value={itemNotes}
                      onChange={(e) => setItemNotes(e.target.value)}
                      placeholder="e.g. Chapters 1-4 for Midterm Examination"
                      className="form-input"
                      style={{ width: '100%' }}
                    />
                  </div>
                </div>
              </div>

              {/* Search Results List */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--text-muted, #77829E)' }}>
                    Catalogue Holdings {totalSearchCount > 0 && `(${totalSearchCount} total in ${selectedCategory})`}
                  </span>
                  {totalSearchPages > 1 && (
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-muted, #77829E)' }}>
                      Page {searchPage} of {totalSearchPages}
                    </span>
                  )}
                </div>

                {searchResults.length === 0 ? (
                  searching ? (
                    <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.82rem' }}>
                      Querying catalogue collection...
                    </div>
                  ) : (
                    <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted, #77829E)', fontSize: '0.82rem', background: 'rgba(15, 23, 42, 0.4)', borderRadius: '10px' }}>
                      {hasSearched
                        ? `No monographs found matching "${searchQuery}" in ${selectedCategory}. Try adjusting category or keywords.`
                        : 'Choose an academic category or enter search terms above.'}
                    </div>
                  )
                ) : (
                  <div
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.5rem',
                    }}
                  >
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem', maxHeight: '340px', overflowY: 'auto' }}>
                      {searchResults.map((b) => (
                        <div
                          key={b.id}
                          style={{
                            padding: '0.75rem 0.95rem',
                            borderRadius: '10px',
                            background: 'rgba(15, 23, 42, 0.6)',
                            border: '1px solid var(--border-medium, #29334F)',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            gap: '0.75rem',
                          }}
                        >
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--text-primary, #F5F6FF)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {b.title}
                            </div>
                            <div style={{ fontSize: '0.74rem', color: 'var(--text-muted, #77829E)', marginTop: '0.15rem' }}>
                              {b.author} • <span style={{ color: '#38BDF8', fontWeight: 600 }}>{b.category}</span>
                            </div>
                          </div>

                          <button
                            type="button"
                            disabled={addingBookId === b.id}
                            onClick={() => handleAddReadingListItem(b.id)}
                            className="btn btn-primary btn-sm"
                            style={{ fontSize: '0.75rem', whiteSpace: 'nowrap' }}
                          >
                            {addingBookId === b.id ? 'Adding...' : '+ Add to Syllabus'}
                          </button>
                        </div>
                      ))}
                    </div>

                    {/* Pagination Controls */}
                    {totalSearchPages > 1 && (
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '0.5rem', borderTop: '1px solid var(--border-medium, #29334F)' }}>
                        <button
                          type="button"
                          disabled={searchPage <= 1 || searching || isPaginating}
                          onClick={() => handleSearchCatalogue(searchPage - 1, undefined, undefined, true)}
                          className="btn btn-secondary btn-sm"
                          style={{ fontSize: '0.72rem' }}
                        >
                          ← Previous
                        </button>
                        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted, #77829E)' }}>
                          Page {searchPage} of {totalSearchPages} ({totalSearchCount} monographs)
                        </span>
                        <button
                          type="button"
                          disabled={searchPage >= totalSearchPages || searching || isPaginating}
                          onClick={() => handleSearchCatalogue(searchPage + 1, undefined, undefined, true)}
                          className="btn btn-secondary btn-sm"
                          style={{ fontSize: '0.72rem' }}
                        >
                          Next →
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Floating Modal: Designate Course Reserve */}
      {showReserveModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(5, 7, 15, 0.82)',
            backdropFilter: 'blur(8px)',
            zIndex: 1200,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1rem',
          }}
          onClick={() => setShowReserveModal(false)}
        >
          <div
            style={{
              background: 'var(--bg-card, #131B2E)',
              border: '1px solid var(--border-medium, #29334F)',
              borderRadius: '16px',
              maxWidth: '480px',
              width: '100%',
              overflow: 'hidden',
              boxShadow: '0 20px 48px rgba(0,0,0,0.6)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1.15rem 1.5rem', borderBottom: '1px solid var(--border-medium, #29334F)' }}>
              <div>
                <h2 style={{ fontSize: '1.05rem', fontWeight: 800, color: 'var(--text-primary, #F5F6FF)', margin: 0 }}>
                  Designate Course Reserve
                </h2>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted, #77829E)' }}>
                  Restrict copy checkout to short-term desk loan
                </span>
              </div>
              <button
                type="button"
                onClick={() => setShowReserveModal(false)}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted, #77829E)', fontSize: '1.1rem', cursor: 'pointer', padding: 0 }}
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleAddCourseReserve} style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary, #A0AEC0)', marginBottom: '0.35rem' }}>
                  Physical Copy ID or Barcode *
                </label>
                <input
                  type="number"
                  required
                  value={reserveCopyId}
                  onChange={(e) => setReserveCopyId(e.target.value)}
                  placeholder="Enter Copy ID (e.g. 1)"
                  className="form-input"
                  style={{ width: '100%' }}
                />
                <p style={{ fontSize: '0.72rem', color: 'var(--text-muted, #77829E)', marginTop: '0.35rem', marginBottom: 0 }}>
                  Physical copy must have 'available' operational status on shelf.
                </p>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary, #A0AEC0)', marginBottom: '0.35rem' }}>
                  Reserve Duration Limit *
                </label>
                <select
                  value={reserveType}
                  onChange={(e: any) => setReserveType(e.target.value)}
                  className="form-select"
                  style={{ width: '100%' }}
                >
                  <option value="2_hour">⏱️ 2-Hour In-Library Desk Reserve</option>
                  <option value="24_hour">🌙 24-Hour Overnight Desk Reserve</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary, #A0AEC0)', marginBottom: '0.35rem' }}>
                  Instructor Reserve Notes
                </label>
                <input
                  type="text"
                  value={reserveNotes}
                  onChange={(e) => setReserveNotes(e.target.value)}
                  placeholder="e.g. Dedicated for Midterm Examination week"
                  className="form-input"
                  style={{ width: '100%' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.65rem', paddingTop: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => setShowReserveModal(false)}
                  className="btn btn-secondary"
                  style={{ fontSize: '0.8rem' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingReserve}
                  className="btn btn-primary"
                  style={{ fontSize: '0.8rem', background: 'linear-gradient(135deg, #F59E0B 0%, #D97706 100%)', borderColor: '#F59E0B' }}
                >
                  {savingReserve ? 'Designating...' : 'Confirm Reserve'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Floating Modal: Export Course Reading List */}
      {showExportModal && selectedCourse && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(5, 7, 15, 0.82)',
            backdropFilter: 'blur(8px)',
            zIndex: 1200,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1rem',
          }}
          onClick={() => setShowExportModal(false)}
        >
          <div
            style={{
              background: '#0B0F19',
              border: '1px solid var(--border-medium, #29334F)',
              borderRadius: '16px',
              boxShadow: '0 25px 60px rgba(0, 0, 0, 0.7)',
              width: '100%',
              maxWidth: '680px',
              maxHeight: '88vh',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div
              style={{
                padding: '1.25rem 1.5rem',
                borderBottom: '1px solid var(--border-medium, #29334F)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <div>
                <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800, color: 'var(--text-primary, #F5F6FF)', display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                  <span>📄</span> Export Course Reading List
                </h3>
                <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--text-muted, #77829E)', marginTop: '0.2rem' }}>
                  {selectedCourse.code}: {selectedCourse.title} • Formatted for Canvas, Blackboard, or syllabus printouts.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowExportModal(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-muted, #77829E)',
                  fontSize: '1.2rem',
                  cursor: 'pointer',
                  padding: '0.2rem 0.5rem',
                  borderRadius: '4px',
                }}
              >
                ✕
              </button>
            </div>

            {/* Preview Body */}
            <div style={{ padding: '1.25rem 1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem', overflowY: 'auto' }}>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary, #A0AEC0)' }}>
                You can copy the generated syllabus bibliography to your clipboard or download it as a markdown file for your course pack.
              </div>

              <pre
                style={{
                  padding: '1rem',
                  borderRadius: '10px',
                  background: 'rgba(15, 23, 42, 0.65)',
                  border: '1px solid var(--border-medium, #29334F)',
                  fontFamily: 'var(--font-mono, monospace)',
                  fontSize: '0.78rem',
                  lineHeight: 1.5,
                  color: '#E2E8F0',
                  whiteSpace: 'pre-wrap',
                  maxHeight: '360px',
                  overflowY: 'auto',
                }}
              >
                {generateSyllabusMarkdown()}
              </pre>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem', paddingTop: '0.5rem', borderTop: '1px solid var(--border-medium, #29334F)' }}>
                <span style={{ fontSize: '0.75rem', color: copyFeedback ? '#10B981' : 'var(--text-muted, #77829E)', fontWeight: 600 }}>
                  {copyFeedback ? '✓ Copied to clipboard!' : `${readingList.length} monograph(s) included`}
                </span>

                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <button
                    type="button"
                    onClick={handleDownloadMarkdown}
                    className="btn btn-secondary btn-sm"
                    style={{ fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}
                  >
                    <span>📥</span> Download .md
                  </button>
                  <button
                    type="button"
                    onClick={handleCopyToClipboard}
                    className="btn btn-primary btn-sm"
                    style={{ fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}
                  >
                    <span>📋</span> {copyFeedback ? 'Copied!' : 'Copy to Clipboard'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Floating Live-Save Toast Notification */}
      {toastMessage && (
        <div
          style={{
            position: 'fixed',
            bottom: '24px',
            right: '24px',
            background: 'rgba(15, 23, 42, 0.95)',
            border: '1px solid #10B981',
            borderRadius: '10px',
            padding: '0.75rem 1.25rem',
            color: '#F5F6FF',
            fontSize: '0.84rem',
            fontWeight: 600,
            boxShadow: '0 8px 30px rgba(0, 0, 0, 0.5)',
            zIndex: 9999,
            display: 'flex',
            alignItems: 'center',
            gap: '0.65rem',
            backdropFilter: 'blur(8px)',
          }}
        >
          <span style={{ color: '#10B981', fontSize: '1.1rem' }}>✓</span>
          <span>{toastMessage}</span>
          <button
            type="button"
            onClick={() => setToastMessage(null)}
            style={{
              background: 'none',
              border: 'none',
              color: '#94A3B8',
              cursor: 'pointer',
              marginLeft: '0.5rem',
              fontSize: '0.85rem',
            }}
          >
            ✕
          </button>
        </div>
      )}
    </div>
  );
};
