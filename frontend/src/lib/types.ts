export interface Paper {
  id: string;
  title: string;
  authors: string[];
  year: number;
  /** Ingestion channel; ``local``/``pdf``/… mean stored in your library. ``external`` is legacy rows only. */
  source: "pdf" | "doi" | "arxiv" | "local" | "external";
  abstract: string;
  dateAdded: string;
  doi?: string;
  url?: string;
}

export interface Citation {
  index: number;
  title: string;
  authors: string[];
  year: number;
  /** ``local`` = excerpt from your Chroma chunks; ``external`` = MCP abstract-only context. */
  source: "local" | "external";
  doi?: string;
  url?: string;
}

export interface QueryResult {
  id: string;
  question: string;
  createdAt: string;
  summary: string;
  agreements: string[];
  contradictions: string[];
  researchGaps: string[];
  citations: Citation[];
  externalPapersFetched: boolean;
  newPapersCount: number;
}

export type ExternalPaper = {
  paper_id: string;
  title: string;
  abstract: string;
  authors: string[];
  year: string;
  doi: string;
  url: string;
  relevance_score?: number;
};

export type CacheStats = {
  cache_hit_rate: number;
  avg_confidence: number;
  external_usage_ratio: number;
  total_queries: number;
  cached_answers: number;
};

export type QueryResponse =
  | { status: "complete"; data: QueryResult }
  | { status: "needs_external_selection"; result_id: string; external_papers: ExternalPaper[] };

export interface DbStats {
  paperCount: number;
  dbSizeMB: number;
  isConnected: boolean;
}

export interface ApiResponse<T> {
  data: T | null;
  error: string | null;
  status: number;
}
