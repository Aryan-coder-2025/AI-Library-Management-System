import React, { useEffect, useState, useCallback } from 'react';
import { apiFetch } from '../services/apiClient';
import type { Book, BookPaginationResponse } from '../types/library';
import { BookCover } from './BookCover';

interface StudentCatalogueProps {
  onSelectBook: (id: number) => void;
}

export const StudentCatalogue: React.FC<StudentCatalogueProps> = ({ onSelectBook }) => {
  const [books, setBooks] = useState<Book[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filter and pagination state
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [submittedQuery, setSubmittedQuery] = useState<string>('');
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  const [page, setPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [totalItems, setTotalItems] = useState<number>(0);
  const pageSize = 12;

  const fetchBooks = useCallback(async () => {
    setLoading(true);
    setError(null);

    const params = new URLSearchParams();
    params.set('page', page.toString());
    params.set('page_size', pageSize.toString());
    params.set('include_archived', 'false');

    if (submittedQuery.trim()) {
      params.set('q', submittedQuery.trim());
    }
    if (categoryFilter) {
      params.set('category', categoryFilter);
    }

    try {
      const response = await apiFetch<BookPaginationResponse>(`/api/books?${params.toString()}`);
      setBooks(response.items);
      setTotalPages(response.total_pages);
      setTotalItems(response.total);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load catalogue';
      setError(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setLoading(false);
    }
  }, [page, submittedQuery, categoryFilter]);

  useEffect(() => {
    fetchBooks();
  }, [fetchBooks]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    setSubmittedQuery(searchQuery);
  };

  const handleClearFilters = () => {
    setSearchQuery('');
    setSubmittedQuery('');
    setCategoryFilter('');
    setPage(1);
  };

  return (
    <div>
      <div className="page-header">
        <div className="page-title-group">
          <h1>Book Catalogue</h1>
          <p className="page-subtitle">
            Explore published titles, monographs, and library holdings
          </p>
        </div>
      </div>

      {/* Search Toolbar */}
      <div className="search-toolbar">
        <form onSubmit={handleSearchSubmit} className="search-input-group" style={{ display: 'flex', gap: '0.5rem' }}>
          <input
            type="search"
            className="form-input"
            placeholder="Search by title, author, or ISBN..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          <button type="submit" className="btn btn-primary">
            Search
          </button>
        </form>

        <select
          className="form-select search-category-select"
          value={categoryFilter}
          onChange={(e) => {
            setCategoryFilter(e.target.value);
            setPage(1);
          }}
          aria-label="Filter catalogue by category"
        >
          <option value="">All Categories</option>
          <option value="Computer Science">Computer Science</option>
          <option value="Artificial Intelligence">Artificial Intelligence</option>
          <option value="Mathematics">Mathematics</option>
          <option value="Physics">Physics</option>
          <option value="Literature">Literature</option>
          <option value="Philosophy">Philosophy</option>
        </select>

        {(submittedQuery || categoryFilter) && (
          <button type="button" className="btn btn-secondary" onClick={handleClearFilters}>
            Clear Filters
          </button>
        )}
      </div>

      {error && (
        <div className="alert alert-error">
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: 'center', padding: '3rem 0', color: 'var(--text-muted)' }}>
          Loading library catalogue...
        </div>
      ) : books.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-title">No books match your criteria</div>
          <p className="empty-state-text">
            Try adjusting your search terms or clearing the category filter to browse all holdings.
          </p>
          {(submittedQuery || categoryFilter) && (
            <button type="button" className="btn btn-secondary" onClick={handleClearFilters}>
              Browse All Books
            </button>
          )}
        </div>
      ) : (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Showing {books.length} of {totalItems} titles
            </span>
          </div>

          <div className="book-grid">
            {books.map((book) => {
              const inStock = book.available_copies > 0;
              return (
                <div
                  key={book.id}
                  className="book-card"
                  onClick={() => onSelectBook(book.id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      onSelectBook(book.id);
                    }
                  }}
                  aria-label={`View details for ${book.title}`}
                >
                  <BookCover title={book.title} author={book.author} category={book.category} />
                  <div className="book-card-body">
                    <h3 className="book-card-title">{book.title}</h3>
                    <div className="book-card-author">{book.author}</div>
                    {book.description && (
                      <p className="book-card-desc">{book.description}</p>
                    )}
                    <div className="book-card-footer">
                      <span className="badge badge-neutral" style={{ fontSize: '0.7rem' }}>
                        {book.category}
                      </span>
                      <span
                        className={`availability-indicator ${
                          inStock ? 'in-stock' : 'out-of-stock'
                        }`}
                      >
                        {inStock
                          ? `${book.available_copies} available`
                          : 'Checked out'}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
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
    </div>
  );
};
