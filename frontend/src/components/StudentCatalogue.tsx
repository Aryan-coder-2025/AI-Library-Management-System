import React, { useEffect, useState, useCallback } from 'react';
import { apiFetch } from '../services/apiClient';
import type {
  Book,
  BookPaginationResponse,
  HybridSearchResponse,
  SemanticSearchResponse,
} from '../types/library';
import { BookCover } from './BookCover';

interface DisplayBook extends Book {
  rrf_score?: number;
  match_channels?: string[];
  similarity_score?: number | null;
}

interface StudentCatalogueProps {
  onSelectBook: (id: number) => void;
}

export const StudentCatalogue: React.FC<StudentCatalogueProps> = ({ onSelectBook }) => {
  const [books, setBooks] = useState<DisplayBook[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filter and pagination state
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [submittedQuery, setSubmittedQuery] = useState<string>('');
  const [searchMode, setSearchMode] = useState<'hybrid' | 'keyword' | 'semantic'>('hybrid');
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

    if (categoryFilter) {
      params.set('category', categoryFilter);
    }

    try {
      if (submittedQuery.trim()) {
        params.set('q', submittedQuery.trim());
        if (searchMode === 'hybrid') {
          const res = await apiFetch<HybridSearchResponse>(`/api/search/hybrid?${params.toString()}`);
          const mapped: DisplayBook[] = res.items.map((item) => ({
            id: item.id,
            title: item.title,
            author: item.author,
            isbn: item.isbn,
            category: item.category,
            description: item.description,
            is_archived: false,
            total_copies: item.total_copies,
            available_copies: item.available_copies,
            created_at: '',
            updated_at: '',
            rrf_score: item.rrf_score,
            match_channels: item.match_channels,
            similarity_score: item.similarity_score,
          }));
          setBooks(mapped);
          setTotalPages(res.total_pages);
          setTotalItems(res.total);
        } else if (searchMode === 'semantic') {
          const res = await apiFetch<SemanticSearchResponse>(`/api/search/semantic?${params.toString()}`);
          const mapped: DisplayBook[] = res.items.map((item) => ({
            id: item.id,
            title: item.title,
            author: item.author,
            isbn: item.isbn,
            category: item.category,
            description: item.description,
            is_archived: false,
            total_copies: item.total_copies,
            available_copies: item.available_copies,
            created_at: '',
            updated_at: '',
            similarity_score: item.similarity_score,
            match_channels: ['semantic'],
          }));
          setBooks(mapped);
          setTotalPages(res.total_pages);
          setTotalItems(res.total);
        } else {
          params.set('include_archived', 'false');
          const res = await apiFetch<BookPaginationResponse>(`/api/books?${params.toString()}`);
          setBooks(res.items);
          setTotalPages(res.total_pages);
          setTotalItems(res.total);
        }
      } else {
        params.set('include_archived', 'false');
        const res = await apiFetch<BookPaginationResponse>(`/api/books?${params.toString()}`);
        setBooks(res.items);
        setTotalPages(res.total_pages);
        setTotalItems(res.total);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load catalogue';
      setError(msg.replace(/^\d+:\s*/, ''));
    } finally {
      setLoading(false);
    }
  }, [page, submittedQuery, categoryFilter, searchMode]);

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
      <div className="search-toolbar" data-tour="catalogue-search-bar">
        <form onSubmit={handleSearchSubmit} className="search-input-group" style={{ display: 'flex', gap: '0.5rem' }}>
          <input
            type="search"
            className="form-input"
            placeholder="Search by title, author, concept, or ISBN..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          <button type="submit" className="btn btn-primary">
            Search
          </button>
        </form>

        <select
          className="form-select search-mode-select"
          value={searchMode}
          onChange={(e) => {
            setSearchMode(e.target.value as 'hybrid' | 'keyword' | 'semantic');
            setPage(1);
          }}
          aria-label="Select search retrieval mode"
        >
          <option value="hybrid">⚡ Hybrid Search (AI + Keywords)</option>
          <option value="keyword">🔍 Keyword Search</option>
          <option value="semantic">🧠 Semantic AI Search</option>
        </select>

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
          <option value="Algorithms & Complexity">Algorithms & Complexity</option>
          <option value="Distributed Systems">Distributed Systems</option>
          <option value="Cybersecurity & Cryptography">Cybersecurity & Cryptography</option>
          <option value="Software Engineering">Software Engineering</option>
          <option value="Mathematics">Mathematics</option>
          <option value="Physics">Physics</option>
          <option value="Data Science">Data Science</option>
          <option value="Information Systems">Information Systems</option>
        </select>

        {(submittedQuery || categoryFilter) && (
          <button type="button" className="btn btn-secondary" onClick={handleClearFilters}>
            Clear Filters
          </button>
        )}
      </div>

      {/* Main Content Area */}
      {error && (
        <div className="alert alert-danger" role="alert" style={{ marginBottom: '1.5rem' }}>
          {error}
        </div>
      )}

      {loading && books.length === 0 ? (
        <div className="empty-state">
          <div className="loading-spinner" />
          <p style={{ marginTop: '1rem', color: 'var(--text-muted)' }}>
            Retrieving catalogue holdings...
          </p>
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
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Showing {books.length} of {totalItems} titles {submittedQuery && `for "${submittedQuery}" (${searchMode})`}
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
                      {book.match_channels && book.match_channels.length > 0 && (
                        <span
                          className={`badge ${
                            book.match_channels.includes('exact_identifier')
                              ? 'badge-success'
                              : book.match_channels.length > 1
                              ? 'badge-primary'
                              : 'badge-neutral'
                          }`}
                          style={{ fontSize: '0.65rem' }}
                        >
                          {book.match_channels.includes('exact_identifier')
                            ? 'Exact ISBN'
                            : book.match_channels.length > 1
                            ? 'Hybrid Match'
                            : book.match_channels[0] === 'semantic'
                            ? 'AI Semantic'
                            : 'Keyword Match'}
                        </span>
                      )}
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
                  disabled={page <= 1 || loading}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Previous
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={page >= totalPages || loading}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
