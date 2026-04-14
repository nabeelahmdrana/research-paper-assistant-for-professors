"""Research query API endpoints.

Phase 4 / Phase C: accepts queries and returns results from the RAG pipeline.

Two-step external flow (Phase C):
  POST /api/research
    - Runs the pipeline.
    - If local confidence is sufficient, returns the final analysis immediately.
    - If local confidence < 0.70, returns candidate external papers with
      status "needs_external_selection" and a result_id so the frontend can
      let the professor choose which papers to ingest.

  POST /api/research/confirm
    - Accepts {result_id, selected_paper_ids}.
    - Ingests the selected external papers via process_agent logic.
    - Runs analysis_agent + storage_agent and returns the final answer.

Results are persisted to a JSON file so they survive server restarts.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.analysis_agent import analysis_agent
from app.agents.process_agent import process_agent
from app.agents.storage_agent import storage_agent
from app.agents.supervisor import run_research_pipeline
from app.config import settings
from app.models.schemas import ConfirmSelectionRequest

router = APIRouter()


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------

class ResearchQueryRequest(BaseModel):
    question: str
    mode: Literal["auto", "local", "external"] = "auto"


# ---------------------------------------------------------------------------
# In-memory query statistics counters
# These are module-level and safe for single-worker asyncio FastAPI.
# ---------------------------------------------------------------------------

_stats: dict[str, float] = {
    "total_queries": 0,
    "cache_hits": 0,
    "external_queries": 0,
    "confidence_sum": 0.0,  # running total for avg calculation
}


def _record_query(cache_hit: bool, external_used: bool, confidence: float) -> None:
    """Update in-memory stats after a pipeline run."""
    _stats["total_queries"] += 1
    if cache_hit:
        _stats["cache_hits"] += 1
    if external_used:
        _stats["external_queries"] += 1
    _stats["confidence_sum"] += confidence


# ---------------------------------------------------------------------------
# Pending results store — holds pipeline state for two-step external flow
# ---------------------------------------------------------------------------

# In-memory map: result_id → pipeline final_state dict
# Only populated when local_sufficient=False and external papers are available.
_pending_states: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Persistent result store backed by a JSON file
# ---------------------------------------------------------------------------

def _results_file() -> Path:
    return Path(settings.results_store_path)


def _load_results() -> dict[str, dict]:
    f = _results_file()
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_results(results: dict[str, dict]) -> None:
    f = _results_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")


# Load existing results at module import so GET endpoints work immediately
_results_store: dict[str, dict] = _load_results()


# ---------------------------------------------------------------------------
# Helper — assemble final API result dict from pipeline state
# ---------------------------------------------------------------------------

def _assemble_result(result_id: str, question: str, final_state: dict) -> dict:
    """Build the frontend-compatible result dict from a completed pipeline state."""
    analysis = final_state.get("analysis", {})
    external_papers = final_state.get("external_papers", [])
    external_papers_fetched = (
        not final_state.get("local_sufficient", True) and len(external_papers) > 0
    )
    new_papers_count = len([p for p in external_papers if p.get("abstract")])

    return {
        "id": result_id,
        "question": question,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "summary": analysis.get("summary", ""),
        "agreements": analysis.get("agreements", []),
        "contradictions": analysis.get("contradictions", []),
        "researchGaps": analysis.get("researchGaps", []),
        "citations": analysis.get("citations", []),
        "externalPapersFetched": external_papers_fetched,
        "newPapersCount": new_papers_count,
        "confidenceScore": final_state.get("confidence_score", 0.0),
        "cacheHit": final_state.get("cache_hit", False),
    }


# ---------------------------------------------------------------------------
# POST /api/research
# ---------------------------------------------------------------------------

@router.post("/research")
async def run_research(body: ResearchQueryRequest) -> dict:
    """Run a research query through the RAG pipeline.

    Returns either:
    - A final analysis result (status "complete") when local content is
      sufficient or a cached answer is available.
    - A candidate list of external papers (status "needs_external_selection")
      when local confidence < 0.70. The frontend should present these papers
      to the professor and call POST /api/research/confirm with the chosen
      paper IDs.
    """
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        result = await run_research_pipeline(body.question)
    except NotImplementedError:
        raise HTTPException(
            status_code=503,
            detail="RAG pipeline not yet implemented.",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    confidence: float = result.get("confidenceScore", 0.0)
    cache_hit: bool = result.get("cacheHit", False)

    # Determine whether the pipeline found external papers but didn't ingest them
    # The supervisor returns external_papers in the result when local_sufficient=False.
    external_papers: list[dict] = result.get("external_papers", [])
    local_sufficient: bool = result.get("local_sufficient", True)

    # Update in-memory stats
    _record_query(
        cache_hit=cache_hit,
        external_used=bool(external_papers) and not local_sufficient,
        confidence=confidence,
    )

    # ------------------------------------------------------------------
    # Two-step flow: if external candidates exist and we are not forcing
    # local-only mode, park the state and ask the frontend to confirm.
    # ------------------------------------------------------------------
    if (
        external_papers
        and not local_sufficient
        and body.mode != "local"
    ):
        result_id = str(uuid.uuid4())

        # Store the pipeline result state for the /confirm step.
        # We carry the external_papers list and current pipeline state
        # so process_agent can ingest the user-selected subset.
        _pending_states[result_id] = {
            "question": body.question,
            "external_papers": external_papers,
            "pipeline_result": result,
        }

        return {
            "data": {
                "status": "needs_external_selection",
                "result_id": result_id,
                "external_papers": external_papers,
                "confidence_score": confidence,
                "message": (
                    "Local knowledge base has insufficient coverage "
                    "(confidence={:.2f}). Select papers to ingest and confirm.".format(
                        confidence
                    )
                ),
            },
            "error": None,
            "status": 200,
        }

    # ------------------------------------------------------------------
    # Normal path: return the final analysis directly
    # ------------------------------------------------------------------
    # Persist result
    _results_store[result["id"]] = result
    _save_results(_results_store)

    return {"data": result, "error": None, "status": 200}


# ---------------------------------------------------------------------------
# POST /api/research/confirm
# ---------------------------------------------------------------------------

@router.post("/research/confirm")
async def confirm_research(body: ConfirmSelectionRequest) -> dict:
    """Ingest selected external papers and produce the final research answer.

    The frontend calls this after the user selects which externally found
    papers to include. This endpoint:
      1. Retrieves the pending pipeline state by result_id.
      2. Filters external_papers down to the selected IDs.
      3. Runs process_agent to ingest them into ChromaDB.
      4. Runs analysis_agent and storage_agent on the enriched DB.
      5. Returns the final structured analysis.
    """
    pending = _pending_states.get(body.result_id)
    if pending is None:
        raise HTTPException(
            status_code=404,
            detail=f"Pending result '{body.result_id}' not found or already consumed.",
        )

    question: str = pending["question"]
    all_external: list[dict] = pending.get("external_papers", [])

    # Filter to only the papers the professor selected
    if body.selected_paper_ids:
        selected = [
            p for p in all_external
            if p.get("paper_id", "") in body.selected_paper_ids
        ]
    else:
        # Empty selection — proceed with no external papers
        selected = []

    # Build a minimal pipeline state for process_agent → analysis_agent → storage_agent
    pipeline_state: dict = {
        "question": question,
        "external_papers": selected,
        "chunks_stored": False,
        "analysis": {},
        # Carry over any existing state fields from the original pipeline run
        "reranked_chunks": [],
        "retrieved_chunks": [],
        "query_embedding": pending.get("pipeline_result", {}).get("query_embedding", []),
        "confidence_score": pending.get("pipeline_result", {}).get("confidenceScore", 0.0),
        "local_sufficient": False,
        "local_results": [],
        "sources_origin": [],
        "normalized_query": question,
        "cache_hit": False,
        "cached_answer": {},
        "answer_stored": False,
        "error": None,
    }

    try:
        if selected:
            pipeline_state = await process_agent(pipeline_state)
        pipeline_state = await analysis_agent(pipeline_state)
        pipeline_state = await storage_agent(pipeline_state)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline completion failed: {exc}",
        )

    # Remove from pending store — one-time use
    _pending_states.pop(body.result_id, None)

    result_id = str(uuid.uuid4())
    result = _assemble_result(result_id, question, pipeline_state)

    # Override: these papers were explicitly ingested
    result["externalPapersFetched"] = bool(selected)
    result["newPapersCount"] = len(selected)

    # Persist
    _results_store[result_id] = result
    _save_results(_results_store)

    return {"data": result, "error": None, "status": 200}


# ---------------------------------------------------------------------------
# GET /api/research/{result_id}
# ---------------------------------------------------------------------------

@router.get("/research/{result_id}")
async def get_research_result(result_id: str) -> dict:
    """Retrieve a previously computed research result by ID."""
    result = _results_store.get(result_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Result '{result_id}' not found")

    return {"data": result, "error": None, "status": 200}


# ---------------------------------------------------------------------------
# GET /api/research
# ---------------------------------------------------------------------------

@router.get("/research")
async def list_research_results() -> dict:
    """List all persisted research results (most recent first)."""
    results = list(_results_store.values())
    results.sort(key=lambda r: r.get("createdAt", ""), reverse=True)

    return {
        "data": {"results": results, "total": len(results)},
        "error": None,
        "status": 200,
    }


# ---------------------------------------------------------------------------
# Accessor for cache stats (used by the cache router in main.py)
# ---------------------------------------------------------------------------

def get_query_stats() -> dict:
    """Return current in-memory query statistics.

    Returns:
        dict with total_queries, cache_hits, external_queries, avg_confidence.
    """
    total = _stats["total_queries"]
    avg_confidence = (_stats["confidence_sum"] / total) if total > 0 else 0.0
    return {
        "total_queries": int(total),
        "cache_hits": int(_stats["cache_hits"]),
        "external_queries": int(_stats["external_queries"]),
        "avg_confidence": round(avg_confidence, 4),
    }
