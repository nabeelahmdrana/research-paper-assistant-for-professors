# Research Paper Assistant — Project Context for Claude

## Project Overview

A **local-first Research Paper Assistant** built for professors. Professors pre-load academic papers (PDFs + URLs/DOIs) into a local ChromaDB vector database. When a research question is submitted:

1. The system first checks an in-memory **answer cache** to avoid redundant LLM calls.
2. On a cache miss, a **LangGraph multi-agent pipeline** expands the query, retrieves semantically relevant chunks from ChromaDB using **hybrid search** (dense vector + BM25 keyword), reranks results with a cross-encoder, evaluates local confidence, and — only when the local library is empty — fetches papers from **Semantic Scholar** and **arXiv** via an MCP server.
3. An **analysis agent** synthesizes the retrieved chunks into a grounded literature review with inline citations.
4. The final answer is stored in the cache and persisted to the database for future retrieval.

The system is entirely local-first: external API calls happen only when the local ChromaDB has no matching chunks at all.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 14, TypeScript (strict mode), Tailwind CSS |
| **Backend** | FastAPI (Python 3.11+), async/await throughout |
| **Orchestration** | LangGraph `StateGraph`, LangChain |
| **Vector Store** | ChromaDB (local persistent) |
| **Embeddings** | `text-embedding-3-small` (OpenAI) |
| **LLM** | GPT-4o / GPT-4o-mini (OpenAI API) |
| **Reranker** | `cross-encoder/ms-marco-MiniLM-L-6-v2` (local HuggingFace) |
| **BM25 Search** | `rank_bm25` (in-memory index per session) |
| **External APIs** | Semantic Scholar REST API, arXiv API |
| **MCP Server** | `paper-search-mcp` — wraps external APIs as LangGraph tools |
| **PDF Parsing** | `pypdf` with recursive character text splitting |

---

## Agent Pipeline (LangGraph StateGraph)

The core of the system is a **directed acyclic graph** of agents sharing a `ResearchState` TypedDict:

```
query_processor
      ↓
cache_checker ──── cache hit? ──→ END (return cached answer instantly)
      ↓ miss
query_expander   (generates 3 sub-queries via LLM for multi-query retrieval)
      ↓
retriever        (hybrid: dense embedding + BM25, merges & deduplicates chunks)
      ↓
reranker_agent   (cross-encoder scores each chunk, keeps top-K)
      ↓
confidence_evaluator ──── local_sufficient=True ──→ analysis_agent → storage_agent → END
      │                                                               ↑
      └──── local_sufficient=False, chunks exist ──────────────────→ ┘
      │
      └──── local_sufficient=False, NO chunks ──→ external_search_agent
                                                         ↓
                                                   analysis_agent → storage_agent → END
```

### Agent Responsibilities

| Agent | File | What It Does |
|---|---|---|
| `query_processor` | `agents/query_processor.py` | Normalizes the raw question, generates dense embedding + HyDE embedding |
| `cache_checker` | `agents/cache_checker.py` | Computes a cache key, checks in-memory store; short-circuits the graph on hit |
| `query_expander` | `agents/query_expander.py` | Uses the LLM to produce 3 semantically varied sub-queries |
| `retriever` | `agents/retriever.py` | Runs hybrid search (ChromaDB vector + BM25), merges by RRF, deduplicates |
| `reranker_agent` | `agents/reranker_agent.py` | Cross-encoder rescores chunks; prunes below threshold |
| `confidence_evaluator` | `agents/confidence_evaluator.py` | Scores local coverage; decides local-only vs external fetch |
| `external_search_agent` | `agents/external_search_agent.py` | Calls MCP tools to fetch from Semantic Scholar / arXiv; ingests new papers |
| `analysis_agent` | `agents/analysis_agent.py` | Synthesizes chunks into a literature review with citations, streaming |
| `storage_agent` | `agents/storage_agent.py` | Persists the final answer + metadata to the answer cache and DB |

---

## Retrieval Strategy

- **Chunking:** Recursive character splitting — 512 tokens, 50-token overlap
- **Embeddings:** `text-embedding-3-small` (1536 dimensions) via OpenAI
- **HyDE:** A hypothetical answer is generated and embedded alongside the original query to improve semantic match
- **BM25:** Keyword-based sparse retrieval runs in parallel on the same corpus
- **Fusion:** Reciprocal Rank Fusion (RRF) merges dense and BM25 ranked lists
- **Reranking:** `cross-encoder/ms-marco-MiniLM-L-6-v2` provides a final relevance score
- **Confidence Threshold:** `0.65` — if average reranker score falls below this, external search is considered (but only triggered if there are zero local chunks)

---

## Key Numerical Parameters

| Parameter | Value | Location |
|---|---|---|
| Chunk size | 512 tokens | `tools/vector_store.py` |
| Chunk overlap | 50 tokens | `tools/vector_store.py` |
| Top-K retrieval | 20 chunks (before rerank) | `agents/retriever.py` |
| Reranker top-K | 8 chunks (after rerank) | `agents/reranker_agent.py` |
| Confidence threshold | 0.65 | `agents/confidence_evaluator.py` |
| LLM temperature | 0.3 (analysis), 0.1 (query expansion) | `agents/analysis_agent.py` |
| Cache TTL | Session-scoped (in-memory) | `tools/answer_cache.py` |
| BM25 k1 | 1.5 | `tools/bm25_search.py` |
| BM25 b | 0.75 | `tools/bm25_search.py` |

---

## Ingestion Pipeline

Papers enter the system through two paths:

1. **PDF Upload** (`ingestion/pdf_ingester.py`) — parses with `pypdf`, splits into chunks, embeds, stores in ChromaDB
2. **URL / DOI** (`ingestion/url_ingester.py`) — fetches metadata + abstract from Semantic Scholar or arXiv, chunks, embeds, stores

Both paths go through `ingestion/pipeline.py` which handles deduplication (by DOI / URL hash), metadata normalization, and ChromaDB upsert.

---

## API Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/papers/upload` | Upload a PDF |
| `POST` | `/api/papers/url` | Ingest a paper by URL/DOI |
| `GET` | `/api/papers/` | List all ingested papers |
| `DELETE` | `/api/papers/{id}` | Remove a paper from the library |
| `POST` | `/api/research/query` | Submit a research question (returns streaming SSE) |
| `GET` | `/api/research/results` | List past research results |
| `GET` | `/api/research/results/{id}` | Get a specific result |

All responses use `{ data, error, status }` envelope.

---

## Frontend Pages

| Route | Purpose |
|---|---|
| `/` | Dashboard — stats, recent results, quick-start |
| `/upload` | Upload PDFs or ingest by URL/DOI |
| `/library` | Browse and manage ingested papers |
| `/query` | Submit research questions, live streaming output |
| `/results/[id]` | Full literature review with citations |

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

## Code Conventions

- **Python:** PEP8, type hints on every function, `async/await` for all I/O
- **TypeScript:** strict mode, no `any`, named exports only
- **API responses:** always `{ data, error, status }` envelope
- **Secrets:** never hardcoded — loaded from `.env` via `python-dotenv` / `next/env`
- **Error handling:** agents catch exceptions and set `state["error"]`; the graph routes to `END` gracefully

---

## Testing

```bash
# Backend
cd backend && python -m pytest tests/ -v --tb=short

# Frontend
cd frontend && npm test -- --watchAll=false

# TypeScript check
cd frontend && npm run type-check

# Linting
cd frontend && npm run lint
cd backend && ruff check app/
```

---

## File Structure

```
research-paper-assistant-for-professors/
├── .claude/
│   ├── agents/           # Specialized Claude Code subagent definitions
│   └── skills/           # Reusable slash-command skills
├── frontend/
│   └── src/
│       ├── app/          # Next.js pages (App Router)
│       ├── components/   # Shared UI components
│       └── lib/          # API client, types, utils
├── backend/
│   └── app/
│       ├── agents/       # LangGraph agent nodes
│       ├── api/          # FastAPI route handlers
│       ├── ingestion/    # PDF + URL ingestion pipeline
│       ├── models/       # Pydantic schemas
│       └── tools/        # Vector store, BM25, reranker, cache
├── mcp-server/           # MCP server config (paper-search-mcp)
└── docs/                 # Architecture, wireframes, workflow docs
```

---

## Environment Variables

```env
# backend/.env
OPENAI_API_KEY=sk-...
CHROMA_PERSIST_DIR=./chroma_db
MCP_SERVER_URL=http://localhost:3001
```
