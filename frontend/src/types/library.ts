export interface UserProfile {
  id: number;
  email: string;
  full_name: string;
  role: 'student' | 'librarian';
  is_active: boolean;
  created_at: string;
}

export interface Book {
  id: number;
  title: string;
  author: string;
  isbn: string | null;
  category: string;
  description: string | null;
  is_archived: boolean;
  total_copies: number;
  available_copies: number;
  created_at: string;
  updated_at: string;
}

export interface BookCopy {
  id: number;
  book_id: number;
  copy_code: string;
  operational_status: 'available' | 'maintenance' | 'lost' | 'retired';
  is_borrowed: boolean;
  effective_status: string;
  notes: string | null;
  added_at: string;
}

export interface BookDetail extends Book {
  copies: BookCopy[];
}

export interface BookPaginationResponse {
  items: Book[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface Loan {
  id: number;
  student_id: number;
  student_name?: string;
  student_email?: string;
  copy_id: number;
  copy_code: string;
  book_id: number;
  book_title: string;
  book_author: string;
  issued_by_id: number;
  issued_at: string;
  due_date: string;
  returned_at: string | null;
  status: 'active' | 'overdue' | 'returned';
  is_overdue: boolean;
}

export interface LoanPaginationResponse {
  items: Loan[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface SemanticBookResult {
  id: number;
  title: string;
  author: string;
  isbn: string | null;
  category: string;
  description: string | null;
  total_copies: number;
  available_copies: number;
  similarity_score: number;
}

export interface SemanticSearchResponse {
  items: SemanticBookResult[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  query: string;
  disclaimer: string;
}

export interface BookRecommendationResult {
  id: number;
  title: string;
  author: string;
  isbn: string | null;
  category: string;
  description: string | null;
  similarity_score: number;
}

export interface BookRecommendationResponse {
  source_book_id: number;
  source_book_title: string;
  recommendations: BookRecommendationResult[];
  total: number;
  disclaimer: string;
}

export interface EmbeddingStatusResponse {
  total_books: number;
  with_embedding: number;
  missing_embedding: number;
  stale_embedding: number;
  model_name: string;
  model_available: boolean;
  is_processing: boolean;
}

export interface EmbeddingRefreshResponse {
  status: string;
  total_candidates: number;
  processed: number;
  failed: number;
  stale: number;
  missing: number;
  message: string;
  errors?: string[];
}
