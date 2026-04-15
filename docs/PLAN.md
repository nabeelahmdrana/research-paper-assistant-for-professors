# Research Paper Assistant — System Design & Implementation Plan

## Overview

An AI-powered, **local-first** research assistant for professors. Users pre-load academic papers (PDFs, DOIs, URLs) into a local ChromaDB vector database. When a research question is submitted the system:

1. Checks a two-layer cache (exact-match + semantic) to avoid redundant LLM calls.
2. On a cache miss, runs a **LangGraph multi-agent pipeline**: query expansion → hybrid retrieval (dense + BM25) → cross-encoder reranking → confidence evaluation.
3. Fetches external papers from **Semantic Scholar** and **arXiv** via MCP tools **only** when the local library has zero relevant chunks.
4. Synthesises the retrieved chunks into a grounded literature review with inline citations.
5. Persists the final answer to ChromaDB and a JSONL results file.

---

## Core Principles

1. Never fabricate sources — every citation must come from retrieved content.
2. Prefer local knowledge; external search is the last resort.
3. Minimise token usage via caching, reranking, and context pruning.
4. Maximise reuse through semantic + exact-match caching.
5. User controls what enters the local library (controlled ingestion).
6. Hybrid retrieval (semantic + BM25 keyword) for robust coverage.
7. Store only high-quality, relevant data.

---

## System Architecture

### High-Level Flow

```
User Query
    ↓
Exact-match cache check (in-memory, zero API calls on hit)
    ↓ miss
Query Processor (normalise + embed + HyDE)
    ↓
Semantic Cache Check (ChromaDB cosine similarity ≥ 0.90)
    ↓ miss
Query Expander (3 sub-queries via LLM)
    ↓
Hybrid Retriever (dense vector + BM25 → RRF merge → top 20)
    ↓
Reranker (cross-encoder → top 8)
    ↓
Confidence Evaluator (score = 0.4·rerank + 0.35·sim + 0.25·diversity)
    ↓
IF confidence ≥ 0.70 OR chunks exist → Analysis Agent
ELSE (zero local chunks)             → External Search (MCP) → Analysis Agent
    ↓
Storage Agent (persist to cache + JSONL)
```

---

## Components

### 1. Query Processing Layer (`agents/query_processor.py`)

**Responsibilities:**
- Normalise query text
- Generate dense embedding (`text-embedding-3-small`)
- Generate HyDE (Hypothetical Document Embedding) for improved semantic recall

**Output fields added to state:**
```
normalized_query, query_embedding, hyde_embedding
```

---

### 2. Cache Layer

#### A. Exact-Match Cache (in-memory, API layer)

- Key: `question.strip().lower()`
- Value: last full result dict
- Seeded from persisted JSONL results on startup
- Zero API calls on hit
- Invalidated when a cited paper is deleted

#### B. Semantic Answer Cache (ChromaDB `answers` collection)

- Key: query embedding (cosine similarity ≥ **0.90**)
- Value: serialised answer JSON stored in ChromaDB metadata
- TTL: 30 days (entries older than this are treated as misses and pruned)
- Max size: 1 000 entries (oldest pruned opportunistically)
- Checked **before** query expansion to skip the LLM expansion call on hits

---

### 3. Local Knowledge Base (ChromaDB)

#### Collection `chunks` (primary retrieval target)

| Field | Type | Description |
|---|---|---|
| `chunk_id` | string | UUID |
| `paper_id` | string | Parent paper slug |
| `text` | string | Chunk content |
| `embedding` | vector | `text-embedding-3-small` (1536-dim) |
| `section` | string | Optional heading |
| `title`, `authors`, `year`, `source`, `doi`, `url` | string | Paper metadata |

#### Collection `papers` (metadata registry)

| Field | Type |
|---|---|
| `paper_id` | string |
| `title` | string |
| `authors` | string |
| `abstract` | string |
| `year` | string |
| `source` | string (`local` / `external`) |
| `doi`, `url` | string |
| `date_added` | ISO timestamp |

#### Collection `answers` (semantic cache)

| Field | Type |
|---|---|
| `id` | UUID |
| `document` | normalised query text |
| `embedding` | query embedding |
| `answer_json` | serialised answer (metadata field) |
| `stored_at` | ISO timestamp (metadata field) |
| `paper_ids` | comma-separated IDs (for invalidation) |

---

### 4. Chunking Strategy (`ingestion/pipeline.py`)

| Parameter | Value |
|---|---|
| Chunk size | 512 tokens |
| Overlap | 64 tokens |
| Splitter | `RecursiveCharacterTextSplitter` (LangChain) |

---

### 5. Retrieval Layer (`agents/retriever.py`)

**Hybrid search:**
1. Dense vector search — ChromaDB cosine similarity (top 20)
2. BM25 keyword search — `rank_bm25` in-memory index (`k1=1.5`, `b=0.75`)
3. Merge via **Reciprocal Rank Fusion (RRF)**
4. Multi-query: repeats search for each of the 3 expanded sub-queries

**Output:** top 20 deduplicated chunks

---

### 6. Reranking Layer (`agents/reranker_agent.py`)

| Parameter | Value |
|---|---|
| Model | `cross-encoder/ms-marco-MiniLM-L-6-v2` (HuggingFace, local) |
| Input | top 20 chunks |
| Output | top **8** chunks (scored, pruned below threshold) |
| Model load | Pre-warmed once at server startup |

**Fallback:** if reranker fails, use vector + BM25 top 10 directly.

---

### 7. Confidence Scoring (`agents/confidence_evaluator.py`)

```
avg_similarity  = mean(1 - distance) over reranked chunks
rerank_signal   = mean(sigmoid(rerank_score)) over chunks with a score
paper_diversity = min(unique_paper_count / 5, 1.0)

confidence = 0.40 · rerank_signal
           + 0.35 · avg_similarity
           + 0.25 · paper_diversity
```

| Threshold | Action |
|---|---|
| `confidence ≥ 0.70` OR chunks exist | Generate answer from local library |
| `confidence < 0.70` AND zero chunks | Trigger external search (MCP) |

---

### 8. External Search (`agents/external_search_agent.py`)

**Trigger condition:** confidence below threshold **and** local library returned zero chunks.

**Sources (via MCP tools):**
- Semantic Scholar (`search_semantic_scholar`)
- arXiv (`search_arxiv`)

**Flow:**
1. Query MCP tools in parallel
2. Fetch top 10–15 papers
3. Filter: must have abstract + relevance threshold
4. Ingest selected papers into ChromaDB (chunked + embedded)
5. Proceed to analysis with the newly ingested chunks

---

### 9. Analysis Agent (`agents/analysis_agent.py`)

**Input:** reranked chunks (local or freshly ingested external)

**Output format:**
```json
{
  "summary": "...",
  "agreements": ["..."],
  "contradictions": ["..."],
  "researchGaps": ["..."],
  "citations": [{"title": "...", "authors": "...", "year": "...", "doi": "..."}]
}
```

- Streams token-by-token via SSE (word-by-word output)
- LLM temperature: `0.3`
- All citations strictly grounded in retrieved content

---

### 10. Storage Agent (`agents/storage_agent.py`)

After each successful answer:
1. Store in semantic answer cache (`answers` ChromaDB collection)
2. Append to JSONL results file (`research_results.jsonl`)
3. Persist pipeline stats to `pipeline_stats.json`

---

## Ingestion Pipeline

Papers enter through two paths:

| Path | Entry point | Notes |
|---|---|---|
| PDF upload | `POST /api/papers/upload` | `pypdf` parsing, max 50 MB |
| DOI / URL | `POST /api/papers/doi` | Semantic Scholar or arXiv metadata |
| External save (single) | `POST /api/papers/save-external` | Professor-selected paper |
| Bulk import | `POST /api/papers/import` | From external search results |
| Cited paper ingest | `POST /api/papers/ingest-citation` | Saves papers cited in results |

All paths go through `ingestion/pipeline.py` which handles deduplication (DOI / URL hash), metadata normalisation, and ChromaDB upsert.

---

## API Design (FastAPI)

### Research Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/research` | Run pipeline, return full result |
| `POST` | `/api/research/stream` | Run pipeline, stream SSE events |
| `POST` | `/api/research/confirm` | Two-step: ingest selected external papers then analyse |
| `GET` | `/api/research` | List all past results |
| `GET` | `/api/research/{id}` | Get a specific result |

### Paper Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/papers/upload` | Upload PDF(s) |
| `POST` | `/api/papers/doi` | Ingest by DOI or URL |
| `GET` | `/api/papers` | List all papers (paginated) |
| `GET` | `/api/papers/{id}` | Get paper detail |
| `DELETE` | `/api/papers/{id}` | Delete paper + invalidate cache |
| `GET` | `/api/papers/search` | Search external databases (no storage) |
| `POST` | `/api/papers/import` | Bulk import from search results |
| `POST` | `/api/papers/save-external` | Save single external paper |
| `POST` | `/api/papers/ingest-citation` | Save a cited paper |
| `GET` | `/api/papers/check` | Check if paper already in library |

### Stats Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/stats` | Paper count, DB size, connection status |
| `GET` | `/api/cache/stats` | Cache hit rate, avg confidence, external usage ratio |
| `GET` | `/api/health` | Liveness check |

**Response envelope:** all responses use `{ data, error, status }`.

---

## LangGraph Agent Pipeline (`agents/supervisor.py`)

```
query_processor
      ↓
cache_checker ──── cache_hit=True ─────────────────────────────────→ END
      ↓ miss
query_expander
      ↓
retriever (hybrid: dense + BM25 + RRF, multi-query)
      ↓
reranker_agent (cross-encoder, top 8)
      ↓
confidence_evaluator
      ├── local_sufficient=True           → analyze → storage_agent → END
      ├── local_sufficient=False, chunks  → analyze → storage_agent → END
      └── local_sufficient=False, empty   → external_search
                                                  ↓
                                            analyze → storage_agent → END
```

### Agent Responsibilities

| Agent | File | What It Does |
|---|---|---|
| `query_processor` | `agents/query_processor.py` | Normalise, embed, HyDE |
| `cache_checker` | `agents/cache_checker.py` | Semantic cache lookup (ChromaDB) |
| `query_expander` | `agents/query_expander.py` | Generate 3 sub-queries via LLM |
| `retriever` | `agents/retriever.py` | Dense + BM25 hybrid, RRF merge |
| `reranker_agent` | `agents/reranker_agent.py` | Cross-encoder rescore, prune |
| `confidence_evaluator` | `agents/confidence_evaluator.py` | Score local coverage, decide path |
| `external_search_agent` | `agents/external_search_agent.py` | MCP calls, ingest new papers |
| `analysis_agent` | `agents/analysis_agent.py` | Literature review with citations, streaming |
| `storage_agent` | `agents/storage_agent.py` | Persist to cache + JSONL |

---

## SSE Streaming Stages

The `POST /api/research/stream` endpoint emits one SSE event per stage:

```
processing_query → checking_cache → expanding_query → retrieving
→ reranking → evaluating → [searching_external] → analyzing
→ [token …] → storing → complete
```

The `analyzing` stage forwards LLM token deltas to the browser for word-by-word output.

---

## Frontend Pages

| Route | Purpose |
|---|---|
| `/` | Dashboard — stats, recent results, quick-start |
| `/upload` | Upload PDFs or ingest by URL/DOI |
| `/library` | Browse and manage ingested papers |
| `/library/[id]` | Paper detail view |
| `/query` | Submit research questions, live SSE streaming output |
| `/results/[id]` | Full literature review with citations |

---

## Key Numerical Parameters

| Parameter | Value | Location |
|---|---|---|
| Chunk size | 512 tokens | `config.py` |
| Chunk overlap | 64 tokens | `config.py` |
| Embedding model | `text-embedding-3-small` | `config.py` |
| Embedding dimensions | 1536 | OpenAI model spec |
| Top-K retrieval | 20 chunks (pre-rerank) | `agents/retriever.py` |
| Reranker top-K | 8 chunks (post-rerank) | `agents/reranker_agent.py` |
| Reranker model | `cross-encoder/ms-marco-MiniLM-L-6-v2` | `config.py` |
| Confidence threshold | 0.70 | `config.py` (`relevance_threshold`) |
| Confidence weights | rerank 0.40 / sim 0.35 / diversity 0.25 | `config.py` |
| Semantic cache threshold | 0.90 cosine similarity | `config.py` |
| Cache TTL | 30 days | `tools/answer_cache.py` |
| Max cache size | 1 000 entries | `tools/answer_cache.py` |
| BM25 k1 | 1.5 | `tools/bm25_search.py` |
| BM25 b | 0.75 | `tools/bm25_search.py` |
| LLM (analysis) | `gpt-4o`, temperature 0.3 | `config.py`, `agents/analysis_agent.py` |
| LLM (expansion) | `gpt-4o-mini`, temperature 0.1 | `agents/query_expander.py` |
| Max PDF size | 50 MB | `config.py` |

---

## Failure Handling

| Failure | Fallback |
|---|---|
| Reranker model crash | Use vector + BM25 top 10 directly |
| BM25 empty index | Vector search only |
| External MCP tools unavailable | Return best-effort local answer |
| No local chunks + MCP failure | Return "no relevant papers" response (never cached) |

---

## Optimisation Strategies

### Token Reduction
- Reranking prunes context from 20 → 8 chunks before LLM call
- No full-paper injection — only relevant chunks reach the LLM
- Cache-first: identical / similar questions bypass the entire pipeline

### Speed
- Exact-match cache: zero latency for repeated questions
- Semantic cache checked before query expansion (saves one LLM call)
- Reranker pre-warmed at startup (avoids cold-load penalty per request)
- External search triggered only when truly needed (empty local library)

### Storage
- External papers only ingested when explicitly selected by the professor
- "No relevant papers" responses never cached (they become stale on new uploads)
- Cache invalidation on paper delete (both in-memory and ChromaDB caches)
- JSONL append-only format for O(1) result writes; compacted on startup

---

## Development Phases

| Phase | What Was Built | Status |
|---|---|---|
| 1 | UI/UX wireframes & design system | Complete |
| 2 | Next.js frontend (all pages, mock data) | Complete |
| 3 | FastAPI backend + ChromaDB + ingestion | Complete |
| 4 | API endpoints (frontend ↔ backend connected) | Complete |
| 5 | LangGraph multi-agent RAG pipeline + MCP | Complete |

---

## Key Rules

- Never hallucinate sources
- Always ground answers in retrieved content
- Prefer reuse over recomputation
- Avoid storing low-quality or stale data
- Keep system scalable and efficient

---

## Future Enhancements

- Knowledge graph (paper citation relationships)
- Claim-level contradiction detection
- Multi-user shared intelligence
- Semantic deduplication across queries
- Retrieval cache layer (currently omitted — low ROI vs. complexity)
- Query expansion refinement (currently 3 sub-queries via GPT-4o-mini)
