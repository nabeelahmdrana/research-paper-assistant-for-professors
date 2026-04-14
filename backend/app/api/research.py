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
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agents.analysis_agent import analysis_agent, stream_analysis
from app.agents.cache_checker import cache_checker
from app.agents.confidence_evaluator import confidence_evaluator
from app.agents.external_search_agent import external_search_agent
from app.agents.process_agent import process_agent
from app.agents.query_expander import query_expander
from app.agents.query_processor import query_processor
from app.agents.reranker_agent import reranker_agent
from app.agents.retriever import retriever
from app.agents.storage_agent import storage_agent
from app.agents.supervisor import ResearchState, run_research_pipeline
from app.config import settings
from app.models.schemas import ConfirmSelectionRequest

logger = logging.getLogger(__name__)

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
    external_papers: list[dict] = result.get("external_papers", [])
    local_sufficient: bool = result.get("local_sufficient", True)

    if cache_hit:
        logger.info("POST /research: CACHE HIT for '%s…' — returning instantly", body.question[:60])
    else:
        logger.info(
            "POST /research: cache MISS — confidence=%.2f local_sufficient=%s external=%d",
            confidence, local_sufficient, len(external_papers),
        )

    _record_query(
        cache_hit=cache_hit,
        external_used=bool(external_papers) and not local_sufficient,
        confidence=confidence,
    )

    # The pipeline always produces a complete analysis (external_search now
    # feeds directly into analysis_agent). Persist and return immediately.
    _results_store[result["id"]] = result
    _save_results(_results_store)

    return {"data": result, "error": None, "status": 200}


# ---------------------------------------------------------------------------
# POST /api/research/stream  — SSE streaming endpoint
# ---------------------------------------------------------------------------


def _sse_event(data: dict) -> str:
    """Format a dict as a single SSE data frame."""
    return f"data: {json.dumps(data)}\n\n"


async def _stream_research_pipeline(question: str) -> AsyncGenerator[str, None]:
    """Run the research pipeline and emit SSE events at each stage.

    Each agent is called directly and in sequence so we have full control
    over when events are emitted.  The analysis step uses stream_analysis()
    to forward individual LLM token deltas to the browser as they arrive,
    giving word-by-word output like ChatGPT/Gemini.

    SSE event types:
        {"stage": "<name>"}                 — pipeline stage milestone
        {"stage": "token", "token": "..."}  — one LLM text delta
        {"stage": "complete", "data": ...}  — final result payload
        {"stage": "error", "error": "..."}  — fatal error
    """
    state: ResearchState = {
        "question": question,
        "error": None,
        "normalized_query": "",
        "query_embedding": [],
        "hyde_embedding": [],
        "cache_hit": False,
        "cached_answer": {},
        "retrieved_chunks": [],
        "reranked_chunks": [],
        "confidence_score": 0.0,
        "answer_stored": False,
        "sub_queries": [],
        "local_results": [],
        "local_sufficient": False,
        "external_papers": [],
        "sources_origin": [],
        "chunks_stored": False,
        "analysis": {},
    }

    try:
        # --- Query processing ---
        state = await query_processor(state)  # type: ignore[assignment]
        yield _sse_event({"stage": "processing_query"})

        state = await query_expander(state)  # type: ignore[assignment]
        yield _sse_event({"stage": "expanding_query"})

        state = await cache_checker(state)  # type: ignore[assignment]
        yield _sse_event({"stage": "checking_cache"})

        # --- Cache hit: return immediately without running retrieval/LLM ---
        if state.get("cache_hit", False):
            cached = state.get("cached_answer", {})
            result = {
                "id": str(uuid.uuid4()),
                "question": question,
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "summary": cached.get("summary", ""),
                "agreements": cached.get("agreements", []),
                "contradictions": cached.get("contradictions", []),
                "researchGaps": cached.get("researchGaps", []),
                "citations": cached.get("citations", []),
                "externalPapersFetched": False,
                "newPapersCount": 0,
                "confidenceScore": state.get("confidence_score", 0.0),
                "cacheHit": True,
                "query_embedding": state.get("query_embedding", []),
            }
            _results_store[result["id"]] = result
            _save_results(_results_store)
            _record_query(cache_hit=True, external_used=False, confidence=result["confidenceScore"])
            yield _sse_event({"stage": "complete", "data": result})
            return

        # --- Retrieval + reranking ---
        state = await retriever(state)  # type: ignore[assignment]
        yield _sse_event({"stage": "retrieving"})

        state = await reranker_agent(state)  # type: ignore[assignment]
        yield _sse_event({"stage": "reranking"})

        state = await confidence_evaluator(state)  # type: ignore[assignment]
        yield _sse_event({"stage": "evaluating"})

        # --- External search when local coverage is insufficient ---
        if not state.get("local_sufficient", False):
            state = await external_search_agent(state)  # type: ignore[assignment]
            yield _sse_event({"stage": "searching_external"})

        # --- Streaming analysis — tokens forwarded to browser in real time ---
        yield _sse_event({"stage": "analyzing"})
        async for event_type, event_data in stream_analysis(state):
            if event_type == "token":
                yield _sse_event({"stage": "token", "token": event_data})
            elif event_type == "done":
                state = event_data  # type: ignore[assignment]

        # --- Persist answer to cache ---
        state = await storage_agent(state)  # type: ignore[assignment]
        yield _sse_event({"stage": "storing"})

    except Exception as exc:
        logger.error("SSE stream: pipeline error — %s", exc)
        yield _sse_event({"stage": "error", "error": str(exc)})
        return

    # --- Assemble and emit final result ---
    external_papers = state.get("external_papers", [])
    analysis = state.get("analysis", {})
    result = {
        "id": str(uuid.uuid4()),
        "question": question,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "summary": analysis.get("summary", ""),
        "agreements": analysis.get("agreements", []),
        "contradictions": analysis.get("contradictions", []),
        "researchGaps": analysis.get("researchGaps", []),
        "citations": analysis.get("citations", []),
        "externalPapersFetched": not state.get("local_sufficient", True) and len(external_papers) > 0,
        "newPapersCount": len([p for p in external_papers if p.get("abstract")]),
        "confidenceScore": state.get("confidence_score", 0.0),
        "cacheHit": False,
        "query_embedding": state.get("query_embedding", []),
        "external_papers": external_papers,
        "local_sufficient": state.get("local_sufficient", True),
    }

    _results_store[result["id"]] = result
    _save_results(_results_store)
    _record_query(
        cache_hit=False,
        external_used=not state.get("local_sufficient", True),
        confidence=result["confidenceScore"],
    )

    yield _sse_event({"stage": "complete", "data": result})


@router.post("/research/stream")
async def stream_research(body: ResearchQueryRequest) -> StreamingResponse:
    """Run a research query and stream progress events via Server-Sent Events.

    The existing POST /api/research endpoint is unchanged (backward compatible).
    This endpoint emits one SSE event per pipeline stage so the frontend can
    update progress indicators in real time.

    SSE event format:
        data: {"stage": "<stage_name>"}\n\n
        ...
        data: {"stage": "complete", "data": <result_json>}\n\n

    Stage names: processing_query, expanding_query, checking_cache, retrieving,
                 reranking, evaluating, analyzing, searching_external, storing, complete
    """
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    return StreamingResponse(
        _stream_research_pipeline(body.question),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


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

    # Recover query_embedding from the original pipeline run
    query_embedding: list[float] = pending.get("pipeline_result", {}).get("query_embedding", [])

    # Re-compute if the original run didn't pass it through
    if not query_embedding:
        try:
            from openai import AsyncOpenAI  # noqa: PLC0415
            from app.config import settings as _settings  # noqa: PLC0415

            _client = AsyncOpenAI(
                api_key=_settings.openai_api_key,
                base_url=_settings.openai_base_url,
            )
            resp = await _client.embeddings.create(
                model=_settings.embedding_model,
                input=question.strip().lower(),
            )
            query_embedding = resp.data[0].embedding
            logger.info("confirm_research: re-computed query_embedding via OpenAI API")
        except Exception as exc:
            logger.warning("confirm_research: could not compute embedding — %s", exc)

    # Build a minimal pipeline state for process_agent → analysis_agent → storage_agent
    pipeline_state: dict = {
        "question": question,
        "external_papers": selected,
        "chunks_stored": False,
        "analysis": {},
        "reranked_chunks": [],
        "retrieved_chunks": [],
        "query_embedding": query_embedding,
        "confidence_score": pending.get("pipeline_result", {}).get("confidenceScore", 0.0),
        "local_sufficient": False,
        "local_results": [],
        "sources_origin": [],
        "normalized_query": question.strip().lower(),
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
