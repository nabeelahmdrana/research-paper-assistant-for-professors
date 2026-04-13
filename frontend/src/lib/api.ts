// API client for FastAPI backend
// All functions call the real FastAPI endpoints.

import type { Paper, QueryResult, DbStats, ApiResponse, ExternalPaper } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function apiFetch<T>(
  path: string,
  init?: RequestInit
): Promise<ApiResponse<T>> {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
    const body = await res.json();
    return {
      data: body.data ?? null,
      error: body.error ?? null,
      status: res.status,
    };
  } catch (err) {
    return {
      data: null,
      error: err instanceof Error ? err.message : "Network error",
      status: 0,
    };
  }
}

/** Map a raw backend paper dict to the frontend Paper type. */
function mapPaper(raw: Record<string, unknown>): Paper {
  return {
    id: String(raw["id"] ?? ""),
    title: String(raw["title"] ?? ""),
    authors: Array.isArray(raw["authors"])
      ? (raw["authors"] as string[])
      : [String(raw["authors"] ?? "")],
    year: Number(raw["year"] ?? 0),
    source: (raw["source"] as Paper["source"]) ?? "pdf",
    abstract: String(raw["abstract"] ?? ""),
    dateAdded: String(raw["dateAdded"] ?? ""),
    doi: raw["doi"] ? String(raw["doi"]) : undefined,
    url: raw["url"] ? String(raw["url"]) : undefined,
  };
}

/** Map a raw backend result dict to the frontend QueryResult type. */
function mapQueryResult(raw: Record<string, unknown>): QueryResult {
  const rawCitations = Array.isArray(raw["citations"]) ? raw["citations"] : [];
  return {
    id: String(raw["id"] ?? ""),
    question: String(raw["question"] ?? ""),
    createdAt: String(raw["createdAt"] ?? raw["created_at"] ?? ""),
    summary: String(raw["summary"] ?? ""),
    agreements: Array.isArray(raw["agreements"])
      ? (raw["agreements"] as string[])
      : [],
    contradictions: Array.isArray(raw["contradictions"])
      ? (raw["contradictions"] as string[])
      : [],
    researchGaps: Array.isArray(raw["researchGaps"])
      ? (raw["researchGaps"] as string[])
      : Array.isArray(raw["research_gaps"])
        ? (raw["research_gaps"] as string[])
        : [],
    citations: (rawCitations as Record<string, unknown>[]).map((c) => ({
      index: Number(c["index"] ?? 0),
      title: String(c["title"] ?? ""),
      authors: Array.isArray(c["authors"])
        ? (c["authors"] as string[])
        : [String(c["authors"] ?? "")],
      year: Number(c["year"] ?? 0),
      source: (c["source"] as "local" | "external") ?? "local",
      doi: c["doi"] ? String(c["doi"]) : undefined,
      url: c["url"] ? String(c["url"]) : undefined,
    })),
    externalPapersFetched: Boolean(raw["externalPapersFetched"] ?? false),
    newPapersCount: Number(raw["newPapersCount"] ?? 0),
  };
}

// ---------------------------------------------------------------------------
// Research Query
// ---------------------------------------------------------------------------

export async function runResearchQuery(
  question: string
): Promise<ApiResponse<QueryResult>> {
  const res = await apiFetch<Record<string, unknown>>("/api/research", {
    method: "POST",
    body: JSON.stringify({ question }),
  });
  if (res.error || !res.data) return { data: null, error: res.error, status: res.status };
  return { data: mapQueryResult(res.data), error: null, status: res.status };
}

export async function getQueryResult(
  id: string
): Promise<ApiResponse<QueryResult>> {
  const res = await apiFetch<Record<string, unknown>>(`/api/research/${id}`);
  if (res.error || !res.data) return { data: null, error: res.error, status: res.status };
  return { data: mapQueryResult(res.data), error: null, status: res.status };
}

export async function listQueryResults(): Promise<
  ApiResponse<{ results: QueryResult[]; total: number }>
> {
  const res = await apiFetch<{
    results: Record<string, unknown>[];
    total: number;
  }>("/api/research");
  if (res.error || !res.data) {
    return { data: { results: [], total: 0 }, error: res.error, status: res.status };
  }
  return {
    data: {
      results: (res.data.results ?? []).map(mapQueryResult),
      total: res.data.total ?? 0,
    },
    error: null,
    status: res.status,
  };
}

// ---------------------------------------------------------------------------
// Paper Management
// ---------------------------------------------------------------------------

export async function uploadPapers(
  files: File[]
): Promise<ApiResponse<{ uploaded: number; papers: Paper[]; errors: string[] }>> {
  try {
    const formData = new FormData();
    files.forEach((f) => formData.append("files", f));

    const res = await fetch(`${API_BASE}/api/papers/upload`, {
      method: "POST",
      body: formData,
    });
    const body = await res.json();

    const rawData = body.data ?? {};
    return {
      data: {
        uploaded: rawData.uploaded ?? 0,
        papers: (rawData.papers ?? []).map(mapPaper),
        errors: rawData.errors ?? [],
      },
      error: body.error ?? null,
      status: res.status,
    };
  } catch (err) {
    return {
      data: { uploaded: 0, papers: [], errors: [] },
      error: err instanceof Error ? err.message : "Upload failed",
      status: 0,
    };
  }
}

export async function fetchPapersByDoi(
  doisOrUrls: string[]
): Promise<ApiResponse<{ fetched: number; papers: Paper[] }>> {
  const res = await apiFetch<{
    fetched: number;
    papers: Record<string, unknown>[];
  }>("/api/papers/doi", {
    method: "POST",
    body: JSON.stringify({ dois: doisOrUrls }),
  });
  if (res.error || !res.data) {
    return { data: { fetched: 0, papers: [] }, error: res.error, status: res.status };
  }
  return {
    data: {
      fetched: res.data.fetched ?? 0,
      papers: (res.data.papers ?? []).map(mapPaper),
    },
    error: null,
    status: res.status,
  };
}

export async function listPapers(): Promise<
  ApiResponse<{ papers: Paper[]; total: number }>
> {
  const res = await apiFetch<{
    papers: Record<string, unknown>[];
    total: number;
  }>("/api/papers");
  if (res.error || !res.data) {
    return { data: { papers: [], total: 0 }, error: res.error, status: res.status };
  }
  return {
    data: {
      papers: (res.data.papers ?? []).map(mapPaper),
      total: res.data.total ?? 0,
    },
    error: null,
    status: res.status,
  };
}

export async function getPaper(id: string): Promise<ApiResponse<Paper>> {
  const res = await apiFetch<Record<string, unknown>>(`/api/papers/${id}`);
  if (res.error || !res.data) return { data: null, error: res.error, status: res.status };
  return { data: mapPaper(res.data), error: null, status: res.status };
}

export async function deletePaper(
  id: string
): Promise<ApiResponse<{ deleted: boolean }>> {
  const res = await apiFetch<{ deleted: boolean; paper_id: string }>(
    `/api/papers/${id}`,
    { method: "DELETE" }
  );
  if (res.error || !res.data) {
    return { data: { deleted: false }, error: res.error, status: res.status };
  }
  return { data: { deleted: res.data.deleted }, error: null, status: res.status };
}

export async function getDbStats(): Promise<ApiResponse<DbStats>> {
  const res = await apiFetch<{
    paperCount: number;
    dbSizeMB: number;
    isConnected: boolean;
  }>("/api/stats");
  if (res.error || !res.data) {
    return {
      data: { paperCount: 0, dbSizeMB: 0, isConnected: false },
      error: res.error,
      status: res.status,
    };
  }
  return {
    data: {
      paperCount: res.data.paperCount ?? 0,
      dbSizeMB: res.data.dbSizeMB ?? 0,
      isConnected: res.data.isConnected ?? false,
    },
    error: null,
    status: res.status,
  };
}

// ---------------------------------------------------------------------------
// External Paper Search & Import (MCP-backed)
// ---------------------------------------------------------------------------

export async function searchExternalPapers(
  query: string,
  limit = 10
): Promise<ApiResponse<{ papers: ExternalPaper[]; total: number }>> {
  const params = new URLSearchParams({ q: query, limit: String(limit) });
  const res = await apiFetch<{ papers: ExternalPaper[]; total: number }>(
    `/api/papers/search?${params}`
  );
  if (res.error || !res.data) {
    return { data: { papers: [], total: 0 }, error: res.error, status: res.status };
  }
  return { data: res.data, error: null, status: res.status };
}

export async function importExternalPapers(
  papers: ExternalPaper[]
): Promise<ApiResponse<{ imported: number; chunks: number; errors: string[] }>> {
  const res = await apiFetch<{ imported: number; chunks: number; errors: string[] }>(
    "/api/papers/import",
    { method: "POST", body: JSON.stringify({ papers }) }
  );
  if (res.error || !res.data) {
    return {
      data: { imported: 0, chunks: 0, errors: [] },
      error: res.error,
      status: res.status,
    };
  }
  return { data: res.data, error: null, status: res.status };
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
