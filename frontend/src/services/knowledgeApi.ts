import { apiFetch } from './apiClient';
import type {
  SubjectTree,
  KnowledgeSearchResponse,
  ModelComparisonResponse,
} from '../types/knowledge';

export async function getSubjectTree(): Promise<SubjectTree[]> {
  return apiFetch<SubjectTree[]>('/api/knowledge/subjects/tree');
}

export async function searchKnowledge(query: string, limit: number = 20): Promise<KnowledgeSearchResponse> {
  return apiFetch<KnowledgeSearchResponse>(`/api/knowledge/search?q=${encodeURIComponent(query)}&limit=${limit}`);
}

export async function seedKnowledge(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>('/api/knowledge/seed', { method: 'POST' });
}

export async function evaluateModelComparison(payload: {
  prompt: string;
  models?: string[];
  temperature?: number;
  include_rag_context?: boolean;
}): Promise<ModelComparisonResponse> {
  return apiFetch<ModelComparisonResponse>('/api/knowledge/comparison/evaluate', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

