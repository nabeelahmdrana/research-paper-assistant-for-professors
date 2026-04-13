"""Research query API endpoints.

Phase 4: accepts queries and returns results from the RAG pipeline.
Results are persisted to a JSON file so they survive server restarts.
"""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.supervisor import run_research_pipeline
from app.config import settings

router = APIRouter()


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


class ResearchQueryRequest(BaseModel):
    question: str


# ---------------------------------------------------------------------------
# POST /api/research
# ---------------------------------------------------------------------------

@router.post("/research")
async def run_research(body: ResearchQueryRequest) -> dict:
    """Run a research query through the RAG pipeline."""
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        result = await run_research_pipeline(body.question)
    except NotImplementedError:
        raise HTTPException(
            status_code=503,
            detail="RAG pipeline not yet implemented (Phase 5).",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # Persist result
    _results_store[result["id"]] = result
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
