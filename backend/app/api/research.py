"""Research query API endpoints.

Phase 4: accepts queries and returns results from the RAG pipeline.
The pipeline is imported from app.agents.supervisor; Phase 5 implements it.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.supervisor import run_research_pipeline

router = APIRouter()

# In-memory store for query results keyed by result id.
# Survives for the lifetime of the server process.
_results_store: dict[str, dict] = {}


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

    # Cache result for retrieval
    _results_store[result["id"]] = result

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
    """List all cached research results (most recent first)."""
    results = list(_results_store.values())
    # Sort by createdAt descending if present
    results.sort(key=lambda r: r.get("createdAt", ""), reverse=True)

    return {
        "data": {"results": results, "total": len(results)},
        "error": None,
        "status": 200,
    }
