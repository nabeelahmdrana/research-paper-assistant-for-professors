"""Cache Checker Agent — Phase B.

Checks the semantic answer cache before running the full retrieval pipeline.
If a sufficiently similar query has been answered before, the cached answer is
returned directly, short-circuiting all downstream agents.

Reads:
    state["query_embedding"] — the embedding produced by query_processor

Populates:
    state["cache_hit"]      — True if a cached answer was found
    state["cached_answer"]  — the cached answer dict (only when cache_hit=True)
"""

from __future__ import annotations

import logging

from app.config import settings
from app.tools.answer_cache import answer_cache

logger = logging.getLogger(__name__)


async def cache_checker(state: dict) -> dict:
    """Look up the answer cache using the pre-computed query embedding.

    Args:
        state: Pipeline state dict; must contain ``query_embedding``.

    Returns:
        Updated state with ``cache_hit`` and, on a hit, ``cached_answer``.
    """
    query_embedding: list[float] = state.get("query_embedding", [])

    if not query_embedding:
        logger.warning("CacheChecker: query_embedding is empty — skipping cache lookup")
        return {
            **state,
            "cache_hit": False,
            "cached_answer": {},
        }

    try:
        cached = await answer_cache.lookup(
            query_embedding,
            threshold=settings.answer_cache_similarity_threshold,
        )
    except Exception as exc:
        logger.error("CacheChecker: lookup error — %s", exc)
        cached = None

    if cached is not None:
        logger.info("CacheChecker: cache HIT — returning cached answer")
        return {
            **state,
            "cache_hit": True,
            "cached_answer": cached,
        }

    logger.debug("CacheChecker: cache MISS — proceeding to retrieval")
    return {
        **state,
        "cache_hit": False,
        "cached_answer": {},
    }
