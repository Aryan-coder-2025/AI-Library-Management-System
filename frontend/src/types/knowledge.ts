export interface Concept {
  id: number;
  topic_id: number;
  name: string;
  description?: string;
  created_at: string;
}

export interface Topic {
  id: number;
  subject_id: number;
  name: string;
  description?: string;
  concepts: Concept[];
  created_at: string;
}

export interface SubjectTree {
  id: number;
  name: string;
  code: string;
  description?: string;
  parent_id?: number | null;
  children: SubjectTree[];
  topics: Topic[];
  created_at: string;
}

export interface KnowledgeSearchResult {
  item_type: 'subject' | 'topic' | 'concept' | 'book';
  id: number;
  title: string;
  description?: string;
  relevance_score: number;
  explanation: string;
  context_path: string;
  associated_books_count: number;
}

export interface KnowledgeSearchResponse {
  query: string;
  results: KnowledgeSearchResult[];
  total: number;
}

export interface ModelExecutionResult {
  model_name: string;
  provider: string;
  response_text: string;
  latency_ms: number;
  token_usage?: {
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
  };
  factual_grounding_score: number;
  citations_count: number;
  error?: string | null;
}

export interface ModelComparisonResponse {
  prompt: string;
  timestamp: string;
  rag_context_used?: string | null;
  results: ModelExecutionResult[];
}

