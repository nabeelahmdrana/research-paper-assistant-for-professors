# Research Paper Assistant for Professors

Local-first research paper assistant. Pre-load papers into ChromaDB, then ask research questions — the system generates grounded literature reviews using RAG + multi-agent AI pipeline.

## Tech Stack
- **Frontend:** Next.js 14, TypeScript, Tailwind CSS
- **Backend:** FastAPI, LangChain, LangGraph, ChromaDB
- **Embeddings:** all-MiniLM-L6-v2 (local, no API key needed)
- **LLM:** Claude (Anthropic API)
- **External APIs:** Semantic Scholar, arXiv

## Project Structure
```
├── .claude/           # Claude Code agents, skills, hooks
├── frontend/          # Next.js app
├── backend/           # FastAPI app
├── mcp-server/        # MCP server config
└── docs/              # Architecture and workflow docs
```

## Development Phases
See `docs/AGENT_WORKFLOW.md` for the sequential phase plan.

| Phase | What gets built |
|-------|----------------|
| 1 | UI/UX wireframes |
| 2 | Next.js frontend (mock data) |
| 3 | FastAPI backend + ChromaDB |
| 4 | API endpoints (connect frontend ↔ backend) |
| 5 | RAG + LangGraph multi-agent pipeline |

## Quick Start

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in ANTHROPIC_API_KEY
uvicorn app.main:app --reload
```

## Available Claude Agents
Start with the `team-lead` agent to coordinate development:
- `team-lead` — supervises all phases, assigns tasks
- `ui-ux` — wireframes and design system (Phase 1)
- `frontend` — Next.js UI (Phase 2)
- `backend` — FastAPI + ChromaDB (Phase 3)
- `api-developer` — API endpoints (Phase 4)
- `rag-specialist` — LangGraph + RAG pipeline (Phase 5)
- `code-reviewer` — reviews code after each phase

## Available Skills
- `/run-tests` — run all test suites
- `/lint` — run ESLint + Ruff
- `/type-check` — TypeScript compiler check
- `/push-phase` — commit, tag, and push a completed phase
