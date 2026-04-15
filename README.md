# Research Paper Assistant for Professors

A **local-first AI research assistant** that lets professors build a private library of academic papers and generate grounded literature reviews using a multi-agent RAG pipeline.

---

## What It Does

1. **Ingest** papers — upload PDFs or paste URLs/DOIs; they're chunked, embedded, and stored in a local ChromaDB vector database.
2. **Query** — ask a research question in plain English.
3. **Retrieve** — the system searches the local library using hybrid dense + BM25 retrieval, reranks results with a cross-encoder, and evaluates local confidence.
4. **Generate** — a LangGraph agent synthesizes a literature review with inline citations, streamed token-by-token to the browser.
5. **Discover** — only when the local library has zero relevant chunks does the system reach out to Semantic Scholar / arXiv (via MCP), ingest those papers, and then answer.

---

## App Workflow

```
                         ┌─────────────────────────────────────────────────┐
                         │               FRONTEND (Next.js)                │
                         │  /upload   /library   /query   /results/[id]    │
                         └─────────────────┬───────────────────────────────┘
                                           │ HTTP / SSE
                         ┌─────────────────▼───────────────────────────────┐
                         │               FASTAPI BACKEND                   │
                         │  POST /api/research/query  →  LangGraph Graph   │
                         └─────────────────┬───────────────────────────────┘
                                           │
          ┌────────────────────────────────▼────────────────────────────────┐
          │                    LANGGRAPH STATE MACHINE                       │
          │                                                                  │
          │  ┌──────────────────┐                                            │
          │  │  query_processor │  Normalize + embed (dense + HyDE)          │
          │  └────────┬─────────┘                                            │
          │           ▼                                                       │
          │  ┌──────────────────┐   cache hit?                               │
          │  │  cache_checker   ├─────────────────────────────→ RETURN       │
          │  └────────┬─────────┘   miss                        (instant)    │
          │           ▼                                                       │
          │  ┌──────────────────┐                                            │
          │  │  query_expander  │  LLM generates 3 sub-queries               │
          │  └────────┬─────────┘                                            │
          │           ▼                                                       │
          │  ┌──────────────────┐                                            │
          │  │    retriever     │  ChromaDB vector + BM25 → RRF fusion       │
          │  └────────┬─────────┘                                            │
          │           ▼                                                       │
          │  ┌──────────────────┐                                            │
          │  │  reranker_agent  │  cross-encoder rescores, prunes to top-8   │
          │  └────────┬─────────┘                                            │
          │           ▼                                                       │
          │  ┌──────────────────────┐                                        │
          │  │ confidence_evaluator │  score ≥ 0.65 → local sufficient       │
          │  └───┬──────────────────┘                                        │
          │      │ sufficient OR chunks exist                                 │
          │      ▼                                                            │
          │  ┌──────────────────┐   NO chunks at all                         │
          │  │ (external_search)│ ←─────────────────── external_search_agent │
          │  └────────┬─────────┘   fetches Semantic Scholar + arXiv (MCP)   │
          │           ▼                                                       │
          │  ┌──────────────────┐                                            │
          │  │  analysis_agent  │  Synthesizes literature review (streaming) │
          │  └────────┬─────────┘                                            │
          │           ▼                                                       │
          │  ┌──────────────────┐                                            │
          │  │  storage_agent   │  Persists result to cache + DB             │
          │  └──────────────────┘                                            │
          └──────────────────────────────────────────────────────────────────┘
                                           │
                         ┌─────────────────▼───────────────────────────────┐
                         │            CHROMADB (local)                     │
                         │   Chunks + embeddings persisted on disk         │
                         └─────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 14, TypeScript, Tailwind CSS |
| **Backend** | FastAPI (Python 3.11+), async/await |
| **Orchestration** | LangGraph `StateGraph`, LangChain |
| **Vector Store** | ChromaDB (local persistent) |
| **Embeddings** | `text-embedding-3-small` (OpenAI, 1536-dim) |
| **LLM** | GPT-4o / GPT-4o-mini (OpenAI API) |
| **Reranker** | `cross-encoder/ms-marco-MiniLM-L-6-v2` (local) |
| **BM25** | `rank_bm25` (in-memory, per-session) |
| **External APIs** | Semantic Scholar, arXiv |
| **MCP** | `paper-search-mcp` (tools for external discovery) |

---

## Project Structure

```
research-paper-assistant-for-professors/
├── .claude/
│   ├── agents/           # Claude Code subagent definitions
│   └── skills/           # Slash-command skills (/smoke, /lint, etc.)
├── frontend/
│   └── src/
│       ├── app/          # Next.js App Router pages
│       ├── components/   # Navbar, StatusBadge, etc.
│       └── lib/          # API client, TypeScript types
├── backend/
│   └── app/
│       ├── agents/       # LangGraph agent nodes
│       ├── api/          # FastAPI route handlers
│       ├── ingestion/    # PDF + URL ingestion pipeline
│       ├── models/       # Pydantic request/response schemas
│       └── tools/        # Vector store, BM25, reranker, answer cache
├── mcp-server/           # MCP server configuration
└── docs/                 # Architecture, wireframes, workflow docs
```

---

## Quick Start

### Prerequisites

- Node.js 18+
- Python 3.11+
- OpenAI API key

### Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # add your OPENAI_API_KEY
uvicorn app.main:app --reload
# → http://localhost:8000
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/papers/upload` | Upload a PDF |
| `POST` | `/api/papers/url` | Ingest paper by URL/DOI |
| `GET` | `/api/papers/` | List all papers in the library |
| `DELETE` | `/api/papers/{id}` | Remove a paper |
| `POST` | `/api/research/query` | Submit a question (SSE streaming) |
| `GET` | `/api/research/results` | List past research results |
| `GET` | `/api/research/results/{id}` | Get a specific result |

---

## Available Claude Code Agents

Start with the `team-lead` agent to coordinate phases:

| Agent | Role |
|---|---|
| `team-lead` | Supervises all phases, assigns tasks |
| `ui-ux` | Wireframes and design system (Phase 1) |
| `frontend` | Next.js UI (Phase 2) |
| `backend` | FastAPI + ChromaDB (Phase 3) |
| `api-developer` | API endpoints (Phase 4) |
| `rag-specialist` | LangGraph + RAG pipeline (Phase 5) |
| `code-reviewer` | Reviews code after each phase |

---

## Available Skills

| Skill | What It Does |
|---|---|
| `/smoke` | Quick end-to-end smoke test — frontend build, backend health check, and a sample query |
| `/run-tests` | Full test suite (Jest + pytest) |
| `/lint` | ESLint + Ruff linting |
| `/type-check` | TypeScript compiler check |
| `/push-phase` | Commit, tag, and push a completed phase |

---

## Development Phases

| Phase | Deliverable | Status |
|---|---|---|
| 1 | UI/UX wireframes & design system | Complete |
| 2 | Next.js frontend (all pages) | Complete |
| 3 | FastAPI backend + ChromaDB + ingestion | Complete |
| 4 | API layer (frontend ↔ backend connected) | Complete |
| 5 | LangGraph multi-agent RAG pipeline | Complete |
