// API client for FastAPI backend
// Phase 2: return mock data
// Phase 4 (api-developer): replace mocks with real fetch calls

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Paper {
  id: string;
  title: string;
  authors: string[];
  year: number;
  source: "local" | "external";
  doi?: string;
}

export interface ResearchResult {
  summary: string;
  agreements: string[];
  contradictions: string[];
  gaps: string[];
  citations: Citation[];
}

export interface Citation {
  id: string;
  title: string;
  authors: string[];
  year: number;
  doi?: string;
  source: "local" | "external";
}

export interface ApiResponse<T> {
  data: T | null;
  error: string | null;
}

// --- Research Query ---

export async function runResearchQuery(
  question: string
): Promise<ApiResponse<ResearchResult>> {
  // TODO (api-developer): replace with real fetch
  return {
    data: {
      summary: `Mock summary for: ${question}`,
      agreements: ["Mock agreement 1", "Mock agreement 2"],
      contradictions: ["Mock contradiction 1"],
      gaps: ["Mock research gap 1"],
      citations: [],
    },
    error: null,
  };
}

// --- Paper Management ---

export async function uploadPapers(
  files: File[]
): Promise<ApiResponse<{ uploaded: number; papers: Paper[] }>> {
  // TODO (api-developer): replace with real fetch
  void files;
  return { data: { uploaded: 0, papers: [] }, error: null };
}

export async function fetchPapersByDoi(
  doisOrUrls: string[]
): Promise<ApiResponse<{ fetched: number; papers: Paper[] }>> {
  // TODO (api-developer): replace with real fetch
  void doisOrUrls;
  return { data: { fetched: 0, papers: [] }, error: null };
}

export async function listPapers(): Promise<
  ApiResponse<{ papers: Paper[]; total: number }>
> {
  // TODO (api-developer): replace with real fetch
  return { data: { papers: [], total: 0 }, error: null };
}

export async function deletePaper(
  id: string
): Promise<ApiResponse<{ deleted: boolean }>> {
  // TODO (api-developer): replace with real fetch
  void id;
  return { data: { deleted: true }, error: null };
}

export async function checkHealth(): Promise<{
  status: string;
  chromadb: boolean;
  paper_count: number;
}> {
  const res = await fetch(`${API_BASE}/api/health`);
  return res.json() as Promise<{
    status: string;
    chromadb: boolean;
    paper_count: number;
  }>;
}
