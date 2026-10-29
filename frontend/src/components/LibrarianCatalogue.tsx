import React, { useEffect, useState, useCallback } from 'react';
import { apiFetch } from '../services/apiClient';
import type { Book, BookDetail, BookPaginationResponse } from '../types/library';

export const LibrarianCatalogue: React.FC = () => {
  const [books, setBooks] = useState<Book[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successNotice, setSuccessNotice] = useState<string | null>(null);

  // Search & Filter
  const [searchQuery, setSearchQuery] = useState('');
  const [includeArchived, setIncludeArchived] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  // Modals
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingBook, setEditingBook] = useState<Book | null>(null);
  const [selectedBookForCopies, setSelectedBookForCopies] = useState<BookDetail | null>(null);
  const [copiesModalLoading, setCopiesModalLoading] = useState(false);

  // Book Form State (Add / Edit)
  const [formTitle, setFormTitle] = useState('');
  const [formAuthor, setFormAuthor] = useState('');
  const [formCategory, setFormCategory] = useState('');
  const [formIsbn, setFormIsbn] = useState('');
  const [formDesc, setFormDesc] = useState('');
  const [formSubmitting, setFormSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // New Copy Form State
  const [newCopyCode, setNewCopyCode] = useState('');
  const [newCopyStatus, setNewCopyStatus] = useState<'available' | 'maintenance' | 'lost' | 'retired'>('available');
  const [newCopyNotes, setNewCopyNotes] = useState('');
  const [copySubmitting, setCopySubmitting] = useState(false);
  const [copyError, setCopyError] = useState<string | null>(null);

  const fetchBooks = useCallback(async () => {
    setLoading(true);
    setError(null);

    const params = new URLSearchParams();
    params.set('page', page.toString());
    params.set('page_size', '10');
    params.set('include_archived', includeArchived.toString());
    if (searchQuery.trim()) {
      params.set('q', searchQuery.trim());
    }

    try {
      const data = await apiFetch<BookPaginationResponse>(`/api/books?${params.toString()}`);
      setBooks(data.items);
      setTotalPages(data.total_pages);
      setTotalCount(data.total);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch catalogue';
      setError(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setLoading(false);
    }
  }, [page, includeArchived, searchQuery]);

  useEffect(() => {
    fetchBooks();
  }, [fetchBooks]);

  const openAddModal = () => {
    setFormTitle('');
    setFormAuthor('');
    setFormCategory('');
    setFormIsbn('');
    setFormDesc('');
    setFormError(null);
    setEditingBook(null);
    setShowAddModal(true);
  };

  const openEditModal = (b: Book) => {
    setEditingBook(b);
    setFormTitle(b.title);
    setFormAuthor(b.author);
    setFormCategory(b.category);
    setFormIsbn(b.isbn || '');
    setFormDesc(b.description || '');
    setFormError(null);
    setShowAddModal(true);
  };

  const handleSaveBook = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormSubmitting(true);
    setFormError(null);

    const payload: {
      title: string;
      author: string;
      category: string;
      description?: string | null;
      isbn?: string | null;
    } = {
      title: formTitle.trim(),
      author: formAuthor.trim(),
      category: formCategory.trim(),
      description: formDesc.trim() || null,
      isbn: formIsbn.trim() || null,
    };

    try {
      if (editingBook) {
        await apiFetch<Book>(`/api/books/${editingBook.id}`, {
          method: 'PATCH',
          body: JSON.stringify(payload),
        });
        setSuccessNotice(`Updated "${formTitle}" successfully.`);
      } else {
        await apiFetch<Book>('/api/books', {
          method: 'POST',
          body: JSON.stringify(payload),
        });
        setSuccessNotice(`Created new book record "${formTitle}".`);
      }
      setShowAddModal(false);
      fetchBooks();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to save book';
      setFormError(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleArchiveBook = async (book: Book) => {
    const confirmed = window.confirm(
      `Are you sure you want to archive "${book.title}"? It will be removed from standard circulation and student searches.`
    );
    if (!confirmed) return;

    try {
      await apiFetch(`/api/books/${book.id}/archive`, { method: 'POST' });
      setSuccessNotice(`Archived "${book.title}".`);
      fetchBooks();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to archive book';
      alert(`Error: ${msg.replace(/^\d+:\s*/, '')}`);
    }
  };

  // Manage Copies
  const openCopiesModal = async (book: Book) => {
    setCopiesModalLoading(true);
    setCopyError(null);
    setNewCopyCode('');
    setNewCopyNotes('');
    setNewCopyStatus('available');
    try {
      const fullDetail = await apiFetch<BookDetail>(`/api/books/${book.id}`);
      setSelectedBookForCopies(fullDetail);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load copies';
      alert(msg);
    } finally {
      setCopiesModalLoading(false);
    }
  };

  const handleAddCopy = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedBookForCopies || !newCopyCode.trim()) return;

    setCopySubmitting(true);
    setCopyError(null);

    try {
      await apiFetch(`/api/books/${selectedBookForCopies.id}/copies`, {
        method: 'POST',
        body: JSON.stringify({
          copy_code: newCopyCode.trim(),
          operational_status: newCopyStatus,
          notes: newCopyNotes.trim() || null,
        }),
      });
      // Refresh modal copy list
      const refreshed = await apiFetch<BookDetail>(`/api/books/${selectedBookForCopies.id}`);
      setSelectedBookForCopies(refreshed);
      setNewCopyCode('');
      setNewCopyNotes('');
      fetchBooks(); // Refresh available counts
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to add copy';
      setCopyError(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setCopySubmitting(false);
    }
  };

  const handleUpdateCopyStatus = async (
    copyId: number,
    status: 'available' | 'maintenance' | 'lost' | 'retired'
  ) => {
    if (!selectedBookForCopies) return;
    if (status === 'retired' || status === 'lost') {
      const confirmed = window.confirm(
        `Are you sure you want to change Copy #${copyId} status to '${status}'? This will remove it from active circulation availability.`
      );
      if (!confirmed) {
        const refreshed = await apiFetch<BookDetail>(`/api/books/${selectedBookForCopies.id}`);
        setSelectedBookForCopies(refreshed);
        return;
      }
    }
    try {
      await apiFetch(`/api/copies/${copyId}`, {
        method: 'PATCH',
        body: JSON.stringify({ operational_status: status }),
      });
      const refreshed = await apiFetch<BookDetail>(`/api/books/${selectedBookForCopies.id}`);
      setSelectedBookForCopies(refreshed);
      fetchBooks();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to update copy status';
      alert(`Error: ${msg.replace(/^\d+:\s*/, '')}`);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div className="page-title-group">
          <h1>Catalogue Management</h1>
          <p className="page-subtitle">
            Librarian administrative records, bibliographic metadata, and physical holdings
          </p>
        </div>
        <button type="button" className="btn btn-primary" onClick={openAddModal}>
          + Add New Book
        </button>
      </div>

      {successNotice && (
        <div className="alert alert-success" style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span>{successNotice}</span>
          <button
            type="button"
            onClick={() => setSuccessNotice(null)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', fontWeight: 600 }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Search & Filters */}
      <div className="search-toolbar">
        <div className="search-input-group" style={{ display: 'flex', gap: '0.5rem' }}>
          <input
            type="text"
            className="form-input"
            placeholder="Filter catalogue by title or author..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setPage(1);
            }}
          />
        </div>

        <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={includeArchived}
            onChange={(e) => {
              setIncludeArchived(e.target.checked);
              setPage(1);
            }}
          />
          Show archived titles
        </label>
      </div>

      {error && (
        <div className="alert alert-error">
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: 'center', padding: '3rem 0', color: 'var(--text-muted)' }}>
          Loading catalogue records...
        </div>
      ) : books.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-title">No books found</div>
          <p className="empty-state-text">
            No bibliographic records match the search filter.
          </p>
        </div>
      ) : (
        <>
          <div style={{ marginBottom: '0.5rem', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            Showing {books.length} of {totalCount} records
          </div>

          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Book Title & Author</th>
                  <th>Category</th>
                  <th>ISBN</th>
                  <th>Inventory Copies</th>
                  <th>Status</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {books.map((b) => (
                  <tr key={b.id}>
                    <td>
                      <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                        {b.title}
                      </div>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                        {b.author}
                      </div>
                    </td>
                    <td>
                      <span className="badge badge-neutral">{b.category}</span>
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.82rem' }}>
                      {b.isbn || '—'}
                    </td>
                    <td>
                      <span
                        className={`badge ${b.available_copies > 0 ? 'badge-success' : 'badge-danger'
                          }`}
                      >
                        {b.available_copies} / {b.total_copies} available
                      </span>
                    </td>
                    <td>
                      {b.is_archived ? (
                        <span className="badge badge-warning">Archived</span>
                      ) : (
                        <span className="badge badge-neutral">Active</span>
                      )}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'inline-flex', gap: '0.4rem' }}>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => openCopiesModal(b)}
                          title="Manage individual barcode copies"
                        >
                          Copies ({b.total_copies})
                        </button>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => openEditModal(b)}
                        >
                          Edit
                        </button>
                        {!b.is_archived && (
                          <button
                            type="button"
                            className="btn btn-danger btn-sm"
                            onClick={() => handleArchiveBook(b)}
                            title="Archive book from circulation"
                          >
                            Archive
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="pagination-container">
              <span className="pagination-info">
                Page {page} of {totalPages}
              </span>
              <div className="pagination-controls">
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Previous
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Add / Edit Book Modal */}
      {showAddModal && (
        <div className="modal-backdrop" onClick={() => setShowAddModal(false)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{editingBook ? 'Edit Book Metadata' : 'Add New Catalogue Book'}</h3>
              <button
                type="button"
                className="btn-close"
                onClick={() => setShowAddModal(false)}
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleSaveBook}>
              <div className="modal-body">
                {formError && (
                  <div className="alert alert-error">
                    <span>{formError}</span>
                  </div>
                )}

                <div className="form-group">
                  <label className="form-label" htmlFor="book-title">
                    Book Title *
                  </label>
                  <input
                    id="book-title"
                    type="text"
                    className="form-input"
                    value={formTitle}
                    onChange={(e) => setFormTitle(e.target.value)}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="book-author">
                    Author / Creator *
                  </label>
                  <input
                    id="book-author"
                    type="text"
                    className="form-input"
                    value={formAuthor}
                    onChange={(e) => setFormAuthor(e.target.value)}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="book-category">
                    Category / Discipline *
                  </label>
                  <input
                    id="book-category"
                    type="text"
                    className="form-input"
                    placeholder="e.g. Computer Science, Artificial Intelligence, Mathematics"
                    value={formCategory}
                    onChange={(e) => setFormCategory(e.target.value)}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="book-isbn">
                    ISBN-13
                    <span className="form-label-hint">
                      (Must be a valid 13-digit checksum or blank)
                    </span>
                  </label>
                  <input
                    id="book-isbn"
                    type="text"
                    className="form-input"
                    placeholder="e.g. 9780134685991"
                    value={formIsbn}
                    onChange={(e) => setFormIsbn(e.target.value)}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="book-desc">
                    Description / Abstract
                  </label>
                  <textarea
                    id="book-desc"
                    className="form-textarea"
                    placeholder="Provide a comprehensive summary or key chapter contents..."
                    value={formDesc}
                    onChange={(e) => setFormDesc(e.target.value)}
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowAddModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={formSubmitting || !formTitle.trim() || !formAuthor.trim() || !formCategory.trim()}
                >
                  {formSubmitting ? 'Saving...' : editingBook ? 'Save Changes' : 'Create Book'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Manage Physical Copies Modal */}
      {selectedBookForCopies && (
        <div className="modal-backdrop" onClick={() => setSelectedBookForCopies(null)}>
          <div className="modal-dialog modal-dialog-large" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h3>Physical Copy Inventory</h3>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                  {selectedBookForCopies.title} — {selectedBookForCopies.author}
                </p>
              </div>
              <button
                type="button"
                className="btn-close"
                onClick={() => setSelectedBookForCopies(null)}
              >
                ✕
              </button>
            </div>

            <div className="modal-body">
              {copiesModalLoading ? (
                <div style={{ textAlign: 'center', padding: '2rem 0' }}>Loading copies...</div>
              ) : (
                <>
                  <div style={{ marginBottom: '1.25rem' }}>
                    <h4 style={{ fontSize: '0.95rem', marginBottom: '0.5rem' }}>
                      Catalogued Copies ({selectedBookForCopies.copies?.length || 0})
                    </h4>
                    {selectedBookForCopies.copies && selectedBookForCopies.copies.length > 0 ? (
                      <div className="table-responsive">
                        <table className="data-table">
                          <thead>
                            <tr>
                              <th>Copy ID</th>
                              <th>Barcode Code</th>
                              <th>Operational Status</th>
                              <th>Borrow State</th>
                              <th>Notes</th>
                              <th>Change Status</th>
                            </tr>
                          </thead>
                          <tbody>
                            {selectedBookForCopies.copies.map((copy) => (
                              <tr key={copy.id}>
                                <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                                  #{copy.id}
                                </td>
                                <td style={{ fontFamily: 'var(--font-mono)' }}>
                                  {copy.copy_code}
                                </td>
                                <td>
                                  <span
                                    className={`badge ${copy.operational_status === 'available'
                                        ? 'badge-success'
                                        : copy.operational_status === 'maintenance'
                                          ? 'badge-warning'
                                          : 'badge-danger'
                                      }`}
                                  >
                                    {copy.operational_status}
                                  </span>
                                </td>
                                <td>
                                  {copy.is_borrowed ? (
                                    <span className="badge badge-warning">On Loan</span>
                                  ) : (
                                    <span className="badge badge-success">On Shelf</span>
                                  )}
                                </td>
                                <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                                  {copy.notes || '—'}
                                </td>
                                <td>
                                  <select
                                    className="form-select"
                                    style={{ fontSize: '0.78rem', padding: '0.25rem 0.5rem', width: 'auto' }}
                                    value={copy.operational_status}
                                    onChange={(e) =>
                                      handleUpdateCopyStatus(
                                        copy.id,
                                        e.target.value as 'available' | 'maintenance' | 'lost' | 'retired'
                                      )
                                    }
                                  >
                                    <option value="available">available</option>
                                    <option value="maintenance">maintenance</option>
                                    <option value="lost">lost</option>
                                    <option value="retired">retired</option>
                                  </select>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                        No copies exist for this book yet.
                      </p>
                    )}
                  </div>

                  {/* Add Copy Form */}
                  <div style={{ background: 'var(--bg-subtle)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
                    <h4 style={{ fontSize: '0.95rem', marginBottom: '0.75rem' }}>Add New Physical Copy</h4>
                    {copyError && <div className="alert alert-error">{copyError}</div>}
                    <form onSubmit={handleAddCopy}>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem' }}>
                        <div className="form-group" style={{ marginBottom: 0 }}>
                          <label className="form-label" htmlFor="new-copy-code">
                            Barcode Code *
                          </label>
                          <input
                            id="new-copy-code"
                            type="text"
                            className="form-input"
                            placeholder="e.g. CS-AI-001-A"
                            value={newCopyCode}
                            onChange={(e) => setNewCopyCode(e.target.value)}
                            required
                          />
                        </div>

                        <div className="form-group" style={{ marginBottom: 0 }}>
                          <label className="form-label" htmlFor="new-copy-status">
                            Initial Status
                          </label>
                          <select
                            id="new-copy-status"
                            className="form-select"
                            value={newCopyStatus}
                            onChange={(e) =>
                              setNewCopyStatus(
                                e.target.value as 'available' | 'maintenance' | 'lost' | 'retired'
                              )
                            }
                          >
                            <option value="available">Available</option>
                            <option value="maintenance">Maintenance</option>
                            <option value="lost">Lost</option>
                            <option value="retired">Retired</option>
                          </select>
                        </div>

                        <div className="form-group" style={{ marginBottom: 0 }}>
                          <label className="form-label" htmlFor="new-copy-notes">
                            Shelf / Condition Notes
                          </label>
                          <input
                            id="new-copy-notes"
                            type="text"
                            className="form-input"
                            placeholder="e.g. Shelf 4B, pristine condition"
                            value={newCopyNotes}
                            onChange={(e) => setNewCopyNotes(e.target.value)}
                          />
                        </div>
                      </div>

                      <button
                        type="submit"
                        className="btn btn-primary"
                        style={{ marginTop: '0.85rem' }}
                        disabled={copySubmitting || !newCopyCode.trim()}
                      >
                        {copySubmitting ? 'Registering Copy...' : 'Register Physical Copy'}
                      </button>
                    </form>
                  </div>
                </>
              )}
            </div>

            <div className="modal-footer">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setSelectedBookForCopies(null)}
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
