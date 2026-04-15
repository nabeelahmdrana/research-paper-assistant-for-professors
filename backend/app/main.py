import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import papers, research
from app.config import settings
from app.tools import vector_store

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-warm the embedding model and ChromaDB on startup."""
    # Ensure the PDF SQLite store table exists before accepting requests
    try:
        from app.tools import pdf_storage as _pdf_storage  # noqa: PLC0415
        await _pdf_storage.init_db()
        logger.info("PDF storage (SQLite) initialised.")
    except Exception as exc:
        logger.warning("PDF storage init failed (non-fatal): %s", exc)

    # Initialise the extended SQLite tables (recent_queries, papers, pipeline_stats)
    try:
        from app.tools import sqlite_store as _sqlite_store  # noqa: PLC0415
        await _sqlite_store.init_sqlite_store()
        logger.info("SQLite store (queries/papers/stats) initialised.")
    except Exception as exc:
        logger.warning("SQLite store init failed (non-fatal): %s", exc)

    try:
        logger.info("Pre-loading embedding model and ChromaDB collection...")
        vector_store.get_collection()
        logger.info("Embedding model and ChromaDB ready.")
    except Exception as exc:
        logger.warning("Startup pre-warm failed (non-fatal): %s", exc)

    # Pre-warm the cross-encoder reranker so the first query doesn't pay the
    # model-load penalty (100–500 ms for CrossEncoder from disk).
    try:
        from app.tools.reranker import reranker as _reranker  # noqa: PLC0415
        _reranker._load()
        logger.info("Reranker model pre-warmed.")
    except Exception as exc:
        logger.warning("Reranker pre-warm failed (non-fatal): %s", exc)

    # Prune expired answer-cache entries (older than 30 days) on startup
    try:
        from datetime import datetime, timedelta, timezone  # noqa: PLC0415

        answers_col = vector_store.get_answers_collection()
        if answers_col.count() > 0:
            all_entries = answers_col.get(include=["metadatas"])
            ids = all_entries.get("ids") or []
            metadatas_list = all_entries.get("metadatas") or []
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            expired_ids: list[str] = []
            for entry_id, meta in zip(ids, metadatas_list):
                stored_at_str = meta.get("stored_at", "")
                if stored_at_str:
                    try:
                        stored_at = datetime.fromisoformat(stored_at_str)
                        if stored_at < cutoff:
                            expired_ids.append(entry_id)
                    except (ValueError, TypeError):
                        pass
            if expired_ids:
                answers_col.delete(ids=expired_ids)
                logger.info("Startup: pruned %d expired cache entries", len(expired_ids))
    except Exception as exc:
        logger.warning("Startup: cache pruning failed (non-fatal): %s", exc)

    yield


app = FastAPI(title="Research Paper Assistant API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(papers.router, prefix="/api")
app.include_router(research.router, prefix="/api")

# ---------------------------------------------------------------------------
# Cache stats router — mounted at /api (not /api/papers) so the route is
# reachable at GET /api/cache/stats as required.
# ---------------------------------------------------------------------------

_cache_router = APIRouter()


@_cache_router.get("/cache/stats")
async def get_cache_stats() -> dict:
    """Return query cache statistics.

    Combines in-memory query counters (from the research module) with the
    ChromaDB answers collection count so the caller gets a unified view.

    Returns:
        cache_hit_rate        — fraction of queries served from cache
        avg_confidence        — mean confidence score across all queries
        external_usage_ratio  — fraction of queries where MCP discovery ran (empty library chunks)
        total_queries         — total queries processed since server start
        cached_answers        — number of answers stored in the ChromaDB cache
    """
    from app.api.research import get_query_stats  # avoid circular import at module level

    query_stats = get_query_stats()
    total = query_stats["total_queries"]

    cache_hit_rate = (
        query_stats["cache_hits"] / total if total > 0 else 0.0
    )
    external_usage_ratio = (
        query_stats["external_queries"] / total if total > 0 else 0.0
    )

    # Count stored answers in ChromaDB answers collection
    cached_answers = 0
    try:
        answers_col = vector_store.get_answers_collection()
        cached_answers = answers_col.count()
    except Exception:
        pass

    return {
        "data": {
            "cache_hit_rate": round(cache_hit_rate, 4),
            "avg_confidence": query_stats["avg_confidence"],
            "external_usage_ratio": round(external_usage_ratio, 4),
            "total_queries": total,
            "cached_answers": cached_answers,
        },
        "error": None,
        "status": 200,
    }


app.include_router(_cache_router, prefix="/api")


@app.get("/api/health")
async def health() -> dict:
    chroma_ok = False
    count = 0
    try:
        count = await vector_store.paper_count()
        chroma_ok = True
    except Exception:
        pass
    return {"status": "ok", "chromadb": chroma_ok, "paper_count": count}
