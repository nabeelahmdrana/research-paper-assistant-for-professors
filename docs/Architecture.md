# Research Paper Assistant — Production Architecture

## 1. Overview

An AI-powered, **local-first** research assistant for professors that:

- Accepts natural-language research questions
- Retrieves relevant academic literature from a local ChromaDB vector store and, as a last resort, from external APIs (Semantic Scholar, arXiv)
- Generates structured literature reviews: summary, agreements, contradictions, research gaps, and grounded citations
- Continuously improves through a two-layer cache (exact-match + semantic) and incremental learning
- Ensures every citation traces back to retrieved content — no hallucinated references

---

## 2. Design Philosophy

| Goal | Approach |
|---|---|
| Production-grade reliability | Startup pre-warming, graceful fallbacks, persistent stats + results |
| High retrieval accuracy | Hybrid search (dense + BM25), HyDE embeddings, cross-encoder reranking |
| Minimal token waste | Two-layer cache, reranking prunes context before LLM call |
| Low operational complexity | Single FastAPI process, local ChromaDB, no external vector DB |
| Correct cache invalidation | Delete paper → evict all cached answers that cite it |

**Deliberately excluded** to avoid over-engineering:

- Retrieval cache layer (low ROI)
- Complex 8+ node agent graphs
- Knowledge graph of papers (future enhancement)
- Claim-level contradiction engine (future enhancement)
- Chunk compression pipeline

---

## 3. High-Level System Flow

```
User Query
    ↓
Exact-Match Cache (in-memory, zero API calls on hit)
    ↓ miss
Query Processor
  → normalise text
  → generate dense embedding (text-embedding-3-small)
  → generate HyDE embedding
    ↓
Semantic Answer Cache (ChromaDB, cosine ≥ 0.90)
    ↓ miss
Query Expander (3 sub-queries via GPT-4o-mini, temp=0.1)
    ↓
Hybrid Retriever
  → Dense vector search (ChromaDB, top 20)
  → BM25 keyword search (rank_bm25, top 20)
  → Merge via Reciprocal Rank Fusion
  → Repeat for each sub-query, deduplicate
    ↓
Cross-Encoder Reranker (ms-marco-MiniLM-L-6-v2, top 8)
    ↓
Confidence Evaluator
  confidence = 0.40·rerank_signal + 0.35·avg_similarity + 0.25·paper_diversity
    ↓
IF confidence ≥ 0.70 OR reranked_chunks non-empty:
    → Analysis Agent (GPT-4o, streaming SSE, temp=0.3)
ELSE (zero chunks):
    → External Search Agent (MCP: Semantic Scholar + arXiv)
    → Analysis Agent
    ↓
Storage Agent
  → ChromaDB answers collection (semantic cache)
  → research_results.jsonl (append-only)
  → pipeline_stats.json
```

---

## 4. Core Modules

### 4.1 Query Processor (`agents/query_processor.py`)

| Task | Detail |
|---|---|
| Text normalisation | Lowercase, strip whitespace |
| Dense embedding | `text-embedding-3-small` via OpenAI API (1536-dim) |
| HyDE embedding | Generates a hypothetical answer, embeds it alongside the query |

**State output:** `normalized_query`, `query_embedding`, `hyde_embedding`

---

### 4.2 Two-Layer Cache

#### Layer 1 — Exact-Match Cache (API layer, `api/research.py`)

- **Store:** Python `dict` in memory, seeded from JSONL results on startup
- **Key:** `question.strip().lower()`
- **Hit:** Returns instantly — zero OpenAI API calls
- **Invalidation:** Paper delete evicts all entries whose `citations` reference that paper
- **Anti-stale guard:** "No relevant papers" results are never cached

#### Layer 2 — Semantic Answer Cache (`tools/answer_cache.py`)

- **Store:** ChromaDB `answers` collection
- **Key:** Query embedding (cosine similarity ≥ **0.90**)
- **TTL:** 30 days — older entries treated as misses
- **Max size:** 1 000 entries; oldest pruned opportunistically on write
- **Checked before** query expansion so cache hits skip the GPT-4o-mini call
- **Invalidation:** Paper delete removes all `answers` docs whose `paper_ids` metadata includes the deleted ID

---

### 4.3 Local Knowledge Base (ChromaDB)

Three persistent collections:

#### `chunks` — primary retrieval target

```
chunk_id    (UUID)
paper_id    (parent paper slug)
text        (chunk content, ~512 tokens)
embedding   (1536-dim, text-embedding-3-small)
section     (optional heading)
title, authors, year, source, doi, url, date_added  (metadata)
```

#### `papers` — paper metadata registry

```
paper_id, title, authors, abstract, year, source, doi, url, date_added
```

#### `answers` — semantic cache

```
id          (UUID)
document    (normalised query text)
embedding   (query embedding)
answer_json (serialised JSON — metadata field)
stored_at   (ISO timestamp — metadata field)
paper_ids   (comma-separated IDs — for cache invalidation)
```

---

### 4.4 Ingestion Pipeline (`ingestion/pipeline.py`)

#### Input types

| Type | Endpoint | Parser |
|---|---|---|
| PDF upload | `POST /api/papers/upload` | `pypdf` |
| DOI or URL | `POST /api/papers/doi` | Semantic Scholar / arXiv API |
| External save (single) | `POST /api/papers/save-external` | Abstract text |
| Bulk import | `POST /api/papers/import` | Abstract text |
| Cited paper | `POST /api/papers/ingest-citation` | Semantic Scholar → arXiv → stub |

#### Processing steps

1. Extract text
2. Clean noise / remove artefacts
3. Split with `RecursiveCharacterTextSplitter` (512 tokens, 64 overlap)
4. Generate embeddings (`text-embedding-3-small`)
5. Upsert chunks into `chunks` collection
6. Register paper metadata in `papers` collection

#### Key rule

External papers are **never stored blindly**. Only abstracts / high-value sections of papers explicitly saved by the professor are ingested.

---

## 5. Retrieval System (`agents/retriever.py`)

### 5.1 Multi-Query Hybrid Search

For the original query **plus** each of the 3 expanded sub-queries:

| Track | Technology | Top-K |
|---|---|---|
| Dense vector | ChromaDB cosine similarity | 20 |
| Keyword | BM25 (`rank_bm25`, k1=1.5, b=0.75) | 20 |

### 5.2 Merge Strategy

**Reciprocal Rank Fusion (RRF)** merges all ranked lists from both tracks and all sub-queries. Results are deduplicated by `chunk_id`.

**Output:** top 20 unified chunks

---

## 6. Reranking Layer (`agents/reranker_agent.py`)

| Parameter | Value |
|---|---|
| Model | `cross-encoder/ms-marco-MiniLM-L-6-v2` (HuggingFace, runs locally) |
| Input | Top 20 merged chunks |
| Output | Top **8** chunks scored by relevance |
| Startup | Pre-warmed once at server start (avoids 100–500 ms cold-load per request) |
| Fallback | If reranker crashes → use vector + BM25 top 10 directly |

---

## 7. Confidence Scoring System (`agents/confidence_evaluator.py`)

```python
avg_similarity  = mean(1 - distance)   # cosine distance from ChromaDB
rerank_signal   = mean(sigmoid(score)) # cross-encoder scores
paper_diversity = min(unique_papers / 5, 1.0)

confidence = 0.40 * rerank_signal
           + 0.35 * avg_similarity
           + 0.25 * paper_diversity
```

| Score | Decision |
|---|---|
| `≥ 0.70` | `local_sufficient=True` → generate answer from local library |
| `< 0.70`, chunks exist | Still generate from local library (local-first principle) |
| `< 0.70`, zero chunks | Trigger external MCP search |

---

## 8. External Search (`agents/external_search_agent.py`)

**Triggered only when:** confidence below threshold **and** local library returned zero chunks.

### Sources (via MCP server tools)

- `search_semantic_scholar` — Semantic Scholar REST API
- `search_arxiv` — arXiv API

### Flow

1. Query both MCP tools in parallel
2. Fetch top 10–15 papers
3. Filter: must have abstract + pass relevance threshold
4. Ingest selected papers into ChromaDB (chunked + embedded)
5. Continue to Analysis Agent with the newly ingested chunks

---

## 9. Analysis Agent (`agents/analysis_agent.py`)

### Input

Reranked chunks (local library or freshly ingested external papers)

### Output format

```json
{
  "summary":        "...",
  "agreements":     ["..."],
  "contradictions": ["..."],
  "researchGaps":   ["..."],
  "citations": [
    {"title": "...", "authors": "...", "year": "...", "doi": "...", "paper_id": "..."}
  ]
}
```

- LLM: GPT-4o, temperature 0.3
- Streaming: token deltas forwarded to the browser via SSE for word-by-word output
- Citations are strictly grounded — only papers from retrieved chunks are cited

---

## 10. Storage Strategy (`agents/storage_agent.py`)

After each successful query:

| What | Where |
|---|---|
| Semantic cache entry | ChromaDB `answers` collection |
| Full result (all fields) | `research_results.jsonl` (append-only, O(1) write) |
| Pipeline counters | `pipeline_stats.json` (flat JSON, survives restarts) |
| Exact-match cache | In-memory `_exact_query_cache` dict |

**JSONL compaction:** on startup the file is rewritten with deduplicated entries to prevent stale lines from accumulating.

---

## 11. API Design (FastAPI)

### Research

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/research` | Run pipeline, return full JSON result |
| `POST` | `/api/research/stream` | Run pipeline, stream SSE events |
| `POST` | `/api/research/confirm` | Two-step: ingest selected external papers then generate answer |
| `GET` | `/api/research` | List all past results (most recent first) |
| `GET` | `/api/research/{id}` | Get a specific result |

#### SSE stream event types

```
{"stage": "processing_query"}
{"stage": "checking_cache"}
{"stage": "expanding_query"}
{"stage": "retrieving"}
{"stage": "reranking"}
{"stage": "evaluating"}
{"stage": "searching_external"}   # only when triggered
{"stage": "analyzing"}
{"stage": "token", "token": "…"} # one LLM text delta
{"stage": "storing"}
{"stage": "complete", "data": {…}}
{"stage": "error", "error": "…"}
```

### Papers

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/papers/upload` | Upload PDF(s) |
| `POST` | `/api/papers/doi` | Ingest by DOI or URL |
| `GET` | `/api/papers` | List papers (paginated) |
| `GET` | `/api/papers/{id}` | Paper detail |
| `DELETE` | `/api/papers/{id}` | Delete paper + invalidate cache |
| `GET` | `/api/papers/search` | Search external databases (no storage) |
| `POST` | `/api/papers/import` | Bulk import from external search results |
| `POST` | `/api/papers/save-external` | Save single external paper |
| `POST` | `/api/papers/ingest-citation` | Save a cited paper by DOI/URL/metadata |
| `GET` | `/api/papers/check` | Check if paper already exists in library |

### Stats & Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/stats` | Paper count, DB size, connection status |
| `GET` | `/api/cache/stats` | Cache hit rate, avg confidence, external usage ratio, total queries |
| `GET` | `/api/health` | Liveness check (ChromaDB + paper count) |

**All responses:** `{ "data": ..., "error": null, "status": 200 }`

---

## 12. LangGraph Supervisor (`agents/supervisor.py`)

```
query_processor
      ↓
cache_checker ─── cache_hit=True ───────────────────────────────────→ END
      ↓ miss
query_expander
      ↓
retriever
      ↓
reranker_agent
      ↓
confidence_evaluator
      ├── local_sufficient=True              → analyze → storage_agent → END
      ├── local_sufficient=False, chunks     → analyze → storage_agent → END
      └── local_sufficient=False, no chunks  → external_search
                                                     ↓
                                               analyze → storage_agent → END
```

The graph is **compiled once** at import time (`_compiled_graph = _build_graph().compile()`).

The `ResearchState` TypedDict is the shared mutable dict that flows through every node:

```python
class ResearchState(TypedDict):
    question: str
    error: str | None
    normalized_query: str
    query_embedding: list[float]
    hyde_embedding: list[float]
    sub_queries: list[str]
    cache_hit: bool
    cached_answer: dict
    retrieved_chunks: list[dict]
    reranked_chunks: list[dict]
    confidence_score: float
    local_sufficient: bool
    local_results: list[dict]
    external_papers: list[dict]
    sources_origin: list[str]
    chunks_stored: bool
    analysis: dict
    answer_stored: bool
```

---

## 13. Failure Handling

| Failure | Fallback |
|---|---|
| Reranker model crash | Use vector + BM25 top 10 directly |
| BM25 index empty | Vector search only |
| External MCP unavailable | Return best-effort local answer |
| No local chunks + MCP failure | Return "no relevant papers" response (never cached) |
| ChromaDB write error | Log warning, continue — answer still returned to user |

---

## 14. Performance Optimisations

### Token Usage

- Reranking reduces LLM context from 20 → 8 chunks
- No full-paper injection — only relevant excerpts
- Two-layer cache: identical or similar queries bypass the entire pipeline

### Latency

- Exact-match cache: O(1) dict lookup, zero API calls
- Semantic cache checked before query expansion (saves one LLM round-trip)
- Reranker pre-warmed at startup
- External MCP search fires only when strictly necessary (empty local library)

### Storage

- JSONL append-only: O(1) write per result regardless of library size
- Compaction on startup removes duplicate lines
- Cache entries pruned to ≤ 1 000 entries, TTL 30 days

---

## 15. Key Numerical Parameters

| Parameter | Value | Config location |
|---|---|---|
| Chunk size | 512 tokens | `config.py` |
| Chunk overlap | 64 tokens | `config.py` |
| Embedding model | `text-embedding-3-small` | `config.py` |
| Top-K retrieval | 20 chunks | `agents/retriever.py` |
| Reranker top-K | 8 chunks | `agents/reranker_agent.py` |
| Confidence threshold | 0.70 | `config.py` (`relevance_threshold`) |
| Confidence weights | 0.40 / 0.35 / 0.25 | `config.py` |
| Semantic cache threshold | 0.90 | `config.py` (`answer_cache_similarity_threshold`) |
| Cache TTL | 30 days | `tools/answer_cache.py` |
| Max cache entries | 1 000 | `tools/answer_cache.py` |
| BM25 k1 | 1.5 | `tools/bm25_search.py` |
| BM25 b | 0.75 | `tools/bm25_search.py` |
| LLM analysis | GPT-4o, temp 0.3 | `config.py`, `agents/analysis_agent.py` |
| LLM expansion | GPT-4o-mini, temp 0.1 | `agents/query_expander.py` |
| Max PDF upload | 50 MB | `config.py` |

---

## 16. Success Metrics

| Metric | Target |
|---|---|
| Cache hit rate | ≥ 30% |
| External search ratio | ≤ 20% (only empty-library queries) |
| Avg latency (local, cached) | < 1 s |
| Avg latency (local, fresh) | < 5 s |
| Token usage reduction via reranking | ≥ 40% |
| Citation accuracy | 100% grounded |

---

## 17. Future Upgrades

These can be added without breaking the current architecture:

- **Retrieval cache** — cache chunk sets per query embedding (low ROI currently)
- **Knowledge graph** — paper citation relationships for cross-paper navigation
- **Query expansion refinement** — more sub-queries, domain-specific expansion
- **Claim-level contradiction detection** — sentence-level disagreement extraction
- **Multi-user shared intelligence** — shared ChromaDB with per-user access control
- **Semantic deduplication** — merge near-duplicate chunks before storage

---

## 18. File Structure

```
research-paper-assistant-for-professors/
├── frontend/
│   └── src/
│       ├── app/                    # Next.js App Router pages
│       │   ├── page.tsx            # Dashboard
│       │   ├── upload/page.tsx     # PDF + DOI ingestion
│       │   ├── library/page.tsx    # Paper library browser
│       │   ├── library/[id]/page.tsx
│       │   ├── query/page.tsx      # SSE streaming query UI
│       │   └── results/[id]/page.tsx
│       ├── components/             # Shared UI components
│       └── lib/                    # API client, types, utils
├── backend/
│   └── app/
│       ├── agents/                 # LangGraph agent nodes
│       │   ├── supervisor.py       # StateGraph definition + entry point
│       │   ├── query_processor.py
│       │   ├── cache_checker.py
│       │   ├── query_expander.py
│       │   ├── retriever.py
│       │   ├── reranker_agent.py
│       │   ├── confidence_evaluator.py
│       │   ├── external_search_agent.py
│       │   ├── analysis_agent.py
│       │   ├── storage_agent.py
│       │   └── process_agent.py
│       ├── api/                    # FastAPI route handlers
│       │   ├── papers.py           # Paper CRUD + ingestion endpoints
│       │   └── research.py         # Query + streaming + confirm endpoints
│       ├── ingestion/              # Ingestion pipeline
│       │   ├── pipeline.py         # Chunk + embed + upsert
│       │   ├── pdf_ingester.py
│       │   └── url_ingester.py
│       ├── models/
│       │   └── schemas.py          # Pydantic request/response models
│       ├── tools/                  # Shared utilities
│       │   ├── vector_store.py     # ChromaDB collections
│       │   ├── answer_cache.py     # Semantic cache (AnswerCache class)
│       │   ├── bm25_search.py      # BM25 in-memory index
│       │   ├── reranker.py         # Cross-encoder wrapper
│       │   ├── openai_client.py    # OpenAI async client
│       │   ├── semantic_scholar.py # Semantic Scholar API helpers
│       │   └── arxiv_search.py     # arXiv API helpers
│       ├── config.py               # Settings (pydantic-settings, .env)
│       └── main.py                 # FastAPI app, lifespan, CORS, routers
└── docs/
    ├── PLAN.md
    └── Architecture.md
```
