# Agent Workflow — Step-by-Step Development Plan

## How to Invoke Agents (Read This First)

Type these commands directly in the Claude Code chat to control the build:

| What you want | What to type |
|---|---|
| Start Phase 1 | `Use the team-lead agent. Start Phase 1, assign ui-ux agent.` |
| Approve a phase | `Phase N approved. Proceed to Phase N+1, assign [agent-name].` |
| Request a fix | `Ask [agent-name] to fix: [describe the issue]. Re-run code-reviewer after.` |
| Run quality checks | `/run-tests` then `/lint` then `/type-check` |
| Commit + push | `/push-phase` |
| Check status | `Use the team-lead agent. What is the current phase status?` |

**Before your first `/push-phase`:** Create a GitHub repo and run:
```bash
git remote add origin https://github.com/YOUR_USERNAME/research-paper-assistant.git
```

---

## Overview
Development is **strictly sequential** by phase. Each phase must be tested, reviewed, and pushed to GitHub before the next phase starts. No phase skipping.

---

## Phase Status Tracker

| Phase | Agent(s) | Status | GitHub Tag |
|-------|----------|--------|------------|
| 1 — UI/UX Wireframes | ui-ux | complete | — |
| 2 — Frontend UI | frontend | pending | — |
| 3 — Backend Core | backend | pending | — |
| 4 — API Layer | api-developer | pending | — |
| 5 — RAG Pipeline | rag-specialist | pending | — |
| Review (after each phase) | code-reviewer | — | — |

---

## Detailed Phase Plan

---

### Phase 1 — UI/UX Wireframes
**Agent:** `ui-ux`
**Runs:** Before any code is written
**Parallel with:** Nothing — this is the first step

**What the agent does:**
- Defines layout and component hierarchy for both pages
- Documents the design system (colors, typography, components)
- Writes `docs/WIREFRAMES.md`

**Acceptance criteria:**
- `docs/WIREFRAMES.md` exists and describes both pages in enough detail for frontend agent to implement without guessing

**Completion step:**
- No code to test — just review `WIREFRAMES.md` for completeness
- Commit: `docs: add UI/UX wireframes for both pages`

---

### Phase 2 — Frontend UI
**Agent:** `frontend`
**Depends on:** Phase 1 (wireframes must exist)
**Parallel with:** Phase 3 (backend can start once frontend structure is clear)

**What the agent does:**
- Initializes Next.js 14 project with TypeScript + Tailwind
- Builds all pages and components from the wireframes
- Uses mock data — no real API calls yet
- Sets up `lib/api.ts` with mock implementations

**Acceptance criteria:**
- `npm run build` succeeds
- Both pages render correctly with mock data
- All components display loading and error states
- `npm run lint` → 0 errors
- `npm run type-check` → 0 errors

**Completion steps:**
1. `/run-tests` — pass
2. `/lint` — pass
3. `/type-check` — pass
4. `code-reviewer` reviews frontend code
5. Fix any BLOCKERs
6. `/push-phase` with tag `phase-2-frontend`

---

### Phase 3 — Backend Core
**Agent:** `backend`
**Depends on:** Phase 1 (project structure is defined)
**Parallel with:** Phase 2 (frontend and backend can be built simultaneously)

**What the agent does:**
- Initializes FastAPI project
- Sets up ChromaDB with persistent storage
- Builds PDF parsing, text cleaning, chunking, embedding pipeline
- Writes Pydantic schemas for all data models
- Writes `requirements.txt` and `.env.example`

**Acceptance criteria:**
- FastAPI starts: `uvicorn app.main:app` runs without errors
- ChromaDB initializes and persists to `./chroma_db`
- Can ingest a PDF file end-to-end (parse → chunk → embed → store)
- `ruff check app/` → 0 issues
- `pytest tests/test_ingestion.py` → all pass

**Completion steps:**
1. `/run-tests` (backend tests) — pass
2. `/lint` (backend) — pass
3. `code-reviewer` reviews backend code
4. Fix any BLOCKERs
5. `/push-phase` with tag `phase-3-backend`

---

### Phase 4 — API Layer
**Agent:** `api-developer`
**Depends on:** Phase 2 AND Phase 3 (both must be complete)
**Parallel with:** Nothing — connects the two completed pieces

**What the agent does:**
- Writes all FastAPI endpoint handlers in `backend/app/api/`
- Updates `frontend/src/lib/api.ts` to call real endpoints (remove mocks)
- Ensures response shapes match TypeScript interfaces
- Registers routers in `main.py`

**Acceptance criteria:**
- `GET /api/health` → `{ status: "ok" }`
- `POST /api/papers/upload` → uploads a PDF, stores in ChromaDB, returns paper metadata
- `GET /api/papers` → lists stored papers
- `POST /api/research` → accepts a question, returns placeholder response (RAG not yet wired)
- Frontend paper upload page works end-to-end
- `pytest tests/test_api.py` → all pass
- `npm run type-check` → 0 errors

**Completion steps:**
1. Manual test: upload a PDF via the browser → appears in paper library
2. `/run-tests` — pass
3. `/lint` — pass
4. `/type-check` — pass
5. `code-reviewer` reviews API code
6. Fix any BLOCKERs
7. `/push-phase` with tag `phase-4-api`

---

### Phase 5 — RAG Pipeline
**Agent:** `rag-specialist`
**Depends on:** Phase 4 (full working API layer)
**Parallel with:** Nothing — builds on the complete system

**What the agent does:**
- Implements LangGraph state graph with all 4 agents
- Wires Local Search Agent → conditional edge → Analysis or External path
- Implements Analysis Agent with RAG (retrieve chunks → Claude LLM → structured response)
- Connects the pipeline to `POST /api/research` endpoint
- Adds MCP server config

**Acceptance criteria:**
- Full end-to-end research query works in the browser
- Local path tested: upload papers first, query about those papers → gets a response without external search
- External path tested: query about a topic not in local DB → triggers external search, stores results, then answers
- Citations in the response trace back to real stored papers
- `pytest tests/test_agents.py` → all pass

**Completion steps:**
1. Manual end-to-end test (upload papers → ask question → get literature review)
2. `/run-tests` — pass
3. `/lint` — pass
4. `/type-check` — pass
5. `code-reviewer` reviews agent code
6. Fix any BLOCKERs
7. `/push-phase` with tag `phase-5-rag`

---

## Parallel Work Rules

```
Phase 1 (ui-ux)
      |
      v
Phase 2 (frontend) ←── starts here
Phase 3 (backend)  ←── can start in parallel with Phase 2
      |
      | (both must finish)
      v
Phase 4 (api-developer)
      |
      v
Phase 5 (rag-specialist)
```

- **Phases 2 and 3 CAN run in parallel** — they do not depend on each other
- **Phase 4 MUST wait** for both Phase 2 and Phase 3 to be complete
- **Phase 5 MUST wait** for Phase 4 to be complete
- **code-reviewer runs after each phase** — not in parallel with the building agent

---

## Testing & GitHub Push After Each Phase

After every phase:
1. Run tests for that phase's scope
2. Run lint and type-check
3. Get code-reviewer approval
4. Commit with a descriptive message
5. Push and tag: `git tag phase-N-<name> && git push origin --tags`

This ensures you can test each module independently and track progress in GitHub.
