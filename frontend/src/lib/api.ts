// API client for FastAPI backend
// Phase 2: return mock data
// Phase 4 (api-developer): replace mocks with real fetch calls

import type { Paper, QueryResult, DbStats, ApiResponse } from "./types";
import {
  MOCK_PAPERS,
  MOCK_QUERIES,
  MOCK_DB_STATS,
} from "./mockData";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// --- Research Query ---

export async function runResearchQuery(
  question: string
): Promise<ApiResponse<QueryResult>> {
  // TODO (api-developer): replace with real fetch to POST /api/research
  void question;
  const result = MOCK_QUERIES[0];
  return { data: result ?? null, error: null, status: 200 };
}

export async function getQueryResult(
  id: string
): Promise<ApiResponse<QueryResult>> {
  // TODO (api-developer): replace with real fetch to GET /api/research/:id
  const result = MOCK_QUERIES.find((q) => q.id === id) ?? null;
  if (!result) {
    return { data: null, error: "Query result not found", status: 404 };
  }
  return { data: result, error: null, status: 200 };
}

export async function listQueryResults(): Promise<
  ApiResponse<{ results: QueryResult[]; total: number }>
> {
  // TODO (api-developer): replace with real fetch to GET /api/research
  return {
    data: { results: MOCK_QUERIES, total: MOCK_QUERIES.length },
    error: null,
    status: 200,
  };
}

// --- Paper Management ---

export async function uploadPapers(
  files: File[]
): Promise<ApiResponse<{ uploaded: number; papers: Paper[] }>> {
  // TODO (api-developer): replace with real fetch to POST /api/papers/upload
  void files;
  return { data: { uploaded: 0, papers: [] }, error: null, status: 200 };
}

export async function fetchPapersByDoi(
  doisOrUrls: string[]
): Promise<ApiResponse<{ fetched: number; papers: Paper[] }>> {
  // TODO (api-developer): replace with real fetch to POST /api/papers/doi
  void doisOrUrls;
  return { data: { fetched: 0, papers: [] }, error: null, status: 200 };
}

export async function listPapers(): Promise<
  ApiResponse<{ papers: Paper[]; total: number }>
> {
  // TODO (api-developer): replace with real fetch to GET /api/papers
  return {
    data: { papers: MOCK_PAPERS, total: MOCK_PAPERS.length },
    error: null,
    status: 200,
  };
}

export async function deletePaper(
  id: string
): Promise<ApiResponse<{ deleted: boolean }>> {
  // TODO (api-developer): replace with real fetch to DELETE /api/papers/:id
  void id;
  return { data: { deleted: true }, error: null, status: 200 };
}

export async function getDbStats(): Promise<ApiResponse<DbStats>> {
  // TODO (api-developer): replace with real fetch to GET /api/stats
  return { data: MOCK_DB_STATS, error: null, status: 200 };
}

export async function checkHealth(): Promise<{
  status: string;
  chromadb: boolean;
  paper_count: number;
}> {
  try {
    const res = await fetch(`${API_BASE}/api/health`);
    return res.json() as Promise<{
      status: string;
      chromadb: boolean;
      paper_count: number;
    }>;
  } catch {
    return { status: "error", chromadb: false, paper_count: 0 };
  }
}
