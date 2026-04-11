# Research Paper Assistant — Project Context for Claude

## Project Overview
A local-first Research Paper Assistant for professors. Professors pre-load papers (PDFs + URLs/DOIs) into ChromaDB. Queries check local DB first; if insufficient, the system fetches from public APIs (Semantic Scholar, arXiv) via MCP server, stores them locally, then uses RAG + LLM to generate grounded literature reviews.

## Tech Stack
- **Frontend:** Next.js 14, TypeScript, Tailwind CSS
- **Backend:** FastAPI (Python), LangChain, LangGraph, ChromaDB
- **Embeddings:** all-MiniLM-L6-v2 (sentence-transformers)
- **LLM:** Claude (Anthropic API)
- **External APIs:** Semantic Scholar, arXiv
- **MCP:** paper-search-mcp server

## Development Phases (Sequential)
1. Frontend UI (Next.js pages and components)
2. Backend core (FastAPI, models, ChromaDB setup)
3. API layer (endpoints connecting frontend ↔ backend)
4. RAG + LangGraph multi-agent pipeline

## Agent Workflow
See `docs/AGENT_WORKFLOW.md` for the step-by-step agent execution plan.

## Code Conventions
- Python: PEP8, type hints everywhere, async/await for I/O
- TypeScript: strict mode, no `any`, named exports
- All API responses use consistent `{ data, error, status }` envelope
- Environment variables via `.env` files — never hardcode secrets

## Testing
- After each phase: run `npm test` (frontend) or `pytest` (backend)
- TypeScript check: `npm run type-check`
- Lint: `npm run lint` (frontend) / `ruff check .` (backend)
- Push to GitHub after each phase passes tests

## File Structure
```
research-paper-assistant-for-professors/
├── .claude/           # Claude Code agents, skills, hooks
├── frontend/          # Next.js app
├── backend/           # FastAPI app
├── mcp-server/        # MCP server config
└── docs/              # Architecture and workflow docs
```
