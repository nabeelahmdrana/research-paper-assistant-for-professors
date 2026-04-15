"""Research query API endpoints.

Phase 4 / Phase C: accepts queries and returns results from the RAG pipeline.

POST /api/research runs the LangGraph supervisor (cache → retrieve → rerank →
confidence → optional MCP discovery when the library has no chunks → analysis).

POST /api/research/confirm completes the two-step flow when a pending result_id
exists: ingests selected external papers, then runs analysis + storage.

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
from app.tools import sqlite_store

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------

class ResearchQueryRequest(BaseModel):
    question: str
    mode: Literal["auto", "local", "external"] = "auto"


# ---------------------------------------------------------------------------
# Persistent pipeline statistics — backed by a JSON file so counts survive
# server restarts.  Same load/save pattern as _results_store below.
# ---------------------------------------------------------------------------

_STATS_DEFAULTS: dict[str, float] = {
    "total_queries": 0,
    "cache_hits": 0,
    "external_queries": 0,
    "confidence_sum": 0.0,  # running total for avg calculation
}


def _stats_file() -> Path:
    return Path(settings.stats_store_path)


def _load_stats() -> dict[str, float]:
    f = _stats_file()
    if f.exists():
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            # Merge with defaults so new keys added in future are always present
            return {**_STATS_DEFAULTS, **data}
        except Exception:
            pass
    return dict(_STATS_DEFAULTS)


def _save_stats(stats: dict[str, float]) -> None:
    f = _stats_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(stats, indent=2, default=str), encoding="utf-8")


# Load from disk at import time so counts are correct from the first request
_stats: dict[str, float] = _load_stats()


# ---------------------------------------------------------------------------
# In-memory exact-match query cache (normalized question → last result)
# Bypasses ALL pipeline stages including OpenAI API calls for identical queries.
# Seeded from _results_store at startup so cache survives server restarts.
# ---------------------------------------------------------------------------

_exact_query_cache: dict[str, dict] = {}


def _seed_exact_cache(results: dict[str, dict]) -> None:
    """Populate _exact_query_cache from persisted results at startup."""
    for result in results.values():
        question = result.get("question", "")
        if not question:
            continue
        # Never seed "no relevant papers" entries — they become stale the moment
        # new papers are uploaded and would keep blocking future queries.
        if _is_no_result_response(result):
            continue
        key = question.strip().lower()
        # Keep the most recent result for each normalized question
        existing = _exact_query_cache.get(key)
        if existing is None or result.get("createdAt", "") > existing.get("createdAt", ""):
            _exact_query_cache[key] = result


def _record_query(cache_hit: bool, external_used: bool, confidence: float) -> None:
    """Update persistent stats after a pipeline run."""
    _stats["total_queries"] += 1
    if cache_hit:
        _stats["cache_hits"] += 1
    if external_used:
        _stats["external_queries"] += 1
    _stats["confidence_sum"] += confidence
    _save_stats(_stats)


async def _persist_result_to_sqlite(result: dict) -> None:
    """Save a completed research result to the SQLite recent_queries table.

    Also refreshes the pipeline_stats row so the dashboard always shows
    up-to-date totals.  Errors are swallowed so a SQLite failure never
    breaks the API response.
    """
    try:
        await sqlite_store.save_query(
            query_id=result.get("id", ""),
            question=result.get("question", ""),
            summary=result.get("summary", ""),
            agreements=result.get("agreements", []),
            contradictions=result.get("contradictions", []),
            gaps=result.get("researchGaps", []),
            citations=result.get("citations", []),
            created_at=result.get("createdAt", ""),
        )
    except Exception as exc:
        logger.warning("_persist_result_to_sqlite: save_query failed (non-fatal): %s", exc)

    # Keep pipeline_stats in sync
    try:
        total = int(_stats["total_queries"])
        avg_confidence = (
            _stats["confidence_sum"] / total if total > 0 else 0.0
        )
        await sqlite_store.upsert_pipeline_stats(
            total_papers=0,   # updated by papers.py; use 0 here to avoid overwriting
            total_queries=total,
            avg_processing_time=round(avg_confidence, 4),
        )
    except Exception as exc:
        logger.warning("_persist_result_to_sqlite: upsert_pipeline_stats failed (non-fatal): %s", exc)


def _external_discovery_used(local_sufficient: bool, external_papers: list) -> bool:
    """True when MCP returned candidates (library had no chunks to analyze)."""
    return (not local_sufficient) and len(external_papers) > 0


_NO_RESULT_MARKERS = (
    "no relevant papers",
    "do not contain information relevant",
    "papers in your library do not",
)


def _is_no_result_response(result: dict) -> bool:
    """Return True when the result is a 'no relevant papers found' placeholder.

    These should never be stored in any cache — new papers may be uploaded
    between queries and the negative answer would become stale immediately.
    """
    summary: str = (result.get("summary") or "").lower()
    return any(marker in summary for marker in _NO_RESULT_MARKERS)


# ---------------------------------------------------------------------------
# Pending results store — holds pipeline state for two-step external flow
# ---------------------------------------------------------------------------

# In-memory map: result_id → pipeline final_state dict
# Only populated when local_sufficient=False and external papers are available.
_pending_states: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Persistent result store — JSONL append-only format (O(1) write per result)
#
# Each line is a JSON object: {"id": "...", ...full result...}
# _load_results() reads all lines and builds an id→result dict.
# _save_results(result) appends a single JSON line (not the full dict).
# On startup, a compaction step rewrites the file with the deduped contents
# so deleted / updated entries don't accumulate forever.
# ---------------------------------------------------------------------------

def _results_file() -> Path:
    return Path(settings.results_store_path)


def _load_results() -> dict[str, dict]:
    """Read all JSONL lines and return an id→result dict.

    Also handles the legacy flat-JSON format (migration path): if the file
    starts with '{', it is parsed as a JSON object and rewritten as JSONL.
    """
    f = _results_file()
    if not f.exists():
        # Also check legacy .json path during migration
        legacy = f.with_suffix(".json")
        if legacy.exists():
            try:
                data: dict[str, dict] = json.loads(legacy.read_text(encoding="utf-8"))
                # Migrate to JSONL in-place
                _compact_results(data, f)
                logger.info("Migrated results from %s to %s", legacy, f)
                return data
            except Exception:
                pass
        return {}

    try:
        raw = f.read_text(encoding="utf-8").strip()
        if not raw:
            return {}
        # Legacy flat-JSON format detection
        if raw.startswith("{"):
            data = json.loads(raw)
            _compact_results(data, f)
            return data
        # Normal JSONL — last entry wins for duplicate ids
        results: dict[str, dict] = {}
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                rid = obj.get("id")
                if rid:
                    results[rid] = obj
            except Exception:
                pass
        return results
    except Exception:
        return {}


def _compact_results(results: dict[str, dict], path: Path) -> None:
    """Rewrite the JSONL file with the current deduplicated results dict."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(v, default=str) for v in results.values()]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _save_results(results: dict[str, dict]) -> None:
    """Append the most-recently-added result as a single JSONL line.

    ``results`` is always ``_results_store``; we take the last-inserted entry
    by iterating to the end.  This is O(1) I/O regardless of library size.
    """
    if not results:
        return
    # The caller always adds the new entry to _results_store before calling us,
    # so the last value in insertion order is the one to append.
    last_result = next(reversed(results.values()))
    f = _results_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    with f.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(last_result, default=str) + "\n")


# Load existing results at module import so GET endpoints work immediately
_results_store: dict[str, dict] = _load_results()
# Compact on startup to remove any duplicate lines from previous runs
if _results_store:
    try:
        _compact_results(_results_store, _results_file())
    except Exception:
        pass
# Seed exact-match cache from persisted results
_seed_exact_cache(_results_store)


# ---------------------------------------------------------------------------
# Cache invalidation — called when a paper is deleted so stale answers are
# removed from both the in-memory exact-match cache and the ChromaDB semantic
# answer cache.
# ---------------------------------------------------------------------------

def invalidate_cache_for_paper(paper_id: str) -> None:
    """Remove cached answers that cite the given paper.

    Scans ``_exact_query_cache`` for entries whose ``citations`` list contains
    a paper matching ``paper_id``, and removes matching docs from the ChromaDB
    ``answers`` collection (matched by the ``paper_ids`` metadata field written
    by storage_agent).
    """
    from app.tools import vector_store  # avoid circular import at module level

    # 1. Purge from in-memory exact-match cache
    keys_to_delete = []
    for key, result in _exact_query_cache.items():
        citations = result.get("citations") or []
        ids_in_result = {c.get("paper_id", "") for c in citations}
        if paper_id in ids_in_result:
            keys_to_delete.append(key)
    for key in keys_to_delete:
        del _exact_query_cache[key]

    # 2. Purge from ChromaDB answers collection
    try:
        answers_col = vector_store.get_answers_collection()
        if answers_col.count() > 0:
            all_entries = answers_col.get(include=["metadatas"])
            ids = all_entries.get("ids") or []
            metadatas_list = all_entries.get("metadatas") or []
            expired_ids = []
            for entry_id, meta in zip(ids, metadatas_list):
                paper_ids_str = meta.get("paper_ids", "")
                if paper_id in paper_ids_str.split(","):
                    expired_ids.append(entry_id)
            if expired_ids:
                answers_col.delete(ids=expired_ids)
                logger.info(
                    "invalidate_cache_for_paper: removed %d cached answers citing paper %s",
                    len(expired_ids),
                    paper_id,
                )
    except Exception as exc:
        logger.warning("invalidate_cache_for_paper: answers collection cleanup failed: %s", exc)

    if keys_to_delete:
        logger.info(
            "invalidate_cache_for_paper: evicted %d exact-cache entries citing paper %s",
            len(keys_to_delete),
            paper_id,
        )


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

    Returns a structured analysis (and metadata such as ``externalPapersFetched``
    when MCP discovery ran because the vector store had no relevant chunks).
    """
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # --- Exact-match cache: zero API calls for identical repeated questions ---
    normalized_question = body.question.strip().lower()
    exact_hit = _exact_query_cache.get(normalized_question)
    if exact_hit is not None:
        logger.info(
            "POST /research: EXACT CACHE HIT for '%s…' — returning instantly (0 API calls)",
            body.question[:60],
        )
        instant_result = {**exact_hit, "id": str(uuid.uuid4()), "cacheHit": True}
        _record_query(
            cache_hit=True,
            external_used=False,
            confidence=instant_result.get("confidenceScore", 0.0),
        )
        return {"data": instant_result, "error": None, "status": 200}

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
        logger.info("POST /research: SEMANTIC CACHE HIT for '%s…'", body.question[:60])
    else:
        logger.info(
            "POST /research: cache MISS — confidence=%.2f local_sufficient=%s external=%d",
            confidence, local_sufficient, len(external_papers),
        )

    _record_query(
        cache_hit=cache_hit,
        external_used=_external_discovery_used(local_sufficient, external_papers),
        confidence=confidence,
    )

    # Persist result; only update exact-match cache for meaningful answers
    _results_store[result["id"]] = result
    _save_results(_results_store)
    if not _is_no_result_response(result):
        _exact_query_cache[normalized_question] = result
    await _persist_result_to_sqlite(result)

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

    # --- Exact-match cache: zero API calls for identical repeated questions ---
    exact_hit = _exact_query_cache.get(question.strip().lower())
    if exact_hit is not None:
        logger.info(
            "SSE stream: EXACT CACHE HIT for '%s…' — returning instantly", question[:60]
        )
        result = {
            **exact_hit,
            "id": str(uuid.uuid4()),
            "cacheHit": True,
        }
        _results_store[result["id"]] = result
        _save_results(_results_store)
        _record_query(cache_hit=True, external_used=False, confidence=result.get("confidenceScore", 0.0))
        yield _sse_event({"stage": "checking_cache"})
        yield _sse_event({"stage": "complete", "data": result})
        return

    try:
        # --- Query processing ---
        state = await query_processor(state)  # type: ignore[assignment]
        yield _sse_event({"stage": "processing_query"})

        # --- Cache check BEFORE query expansion to skip the LLM call on hits ---
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
                "confidenceScore": cached.get("confidenceScore", 0.0),
                "cacheHit": True,
                "query_embedding": state.get("query_embedding", []),
            }
            _results_store[result["id"]] = result
            _save_results(_results_store)
            _record_query(cache_hit=True, external_used=False, confidence=result["confidenceScore"])
            yield _sse_event({"stage": "complete", "data": result})
            return

        # --- Query expansion (only on cache miss) ---
        state = await query_expander(state)  # type: ignore[assignment]
        yield _sse_event({"stage": "expanding_query"})

        # --- Retrieval + reranking ---
        state = await retriever(state)  # type: ignore[assignment]
        yield _sse_event({"stage": "retrieving"})

        state = await reranker_agent(state)  # type: ignore[assignment]
        yield _sse_event({"stage": "reranking"})

        state = await confidence_evaluator(state)  # type: ignore[assignment]
        yield _sse_event({"stage": "evaluating"})

        # --- External discovery only when the library returned no chunks (matches supervisor) ---
        reranked_for_external = state.get("reranked_chunks") or []
        if not state.get("local_sufficient", False) and not reranked_for_external:
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
    if not _is_no_result_response(result):
        _exact_query_cache[question.strip().lower()] = result
    _record_query(
        cache_hit=False,
        external_used=_external_discovery_used(
            state.get("local_sufficient", True),
            state.get("external_papers") or [],
        ),
        confidence=result["confidenceScore"],
    )
    await _persist_result_to_sqlite(result)

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
    await _persist_result_to_sqlite(result)

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
async def list_research_results(limit: int | None = None) -> dict:
    """List persisted research results (most recent first).

    Args:
        limit: Optional maximum number of results to return.  Omit for all.
    """
    results = list(_results_store.values())
    results.sort(key=lambda r: r.get("createdAt", ""), reverse=True)
    total = len(results)
    if limit is not None and limit > 0:
        results = results[:limit]

    return {
        "data": {"results": results, "total": total},
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
