export interface Paper {
  id: string;
  title: string;
  authors: string[];
  year: number;
  source: "pdf" | "doi" | "arxiv";
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
}

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
