"""Storage Agent — Phase B.

After the analysis agent completes, stores the answer in the semantic cache
so that sufficiently similar future queries can be answered without re-running
the full pipeline.

Reads:
    state["question"]         — original research question
    state["query_embedding"]  — embedding produced by query_processor
    state["analysis"]         — structured answer dict from analysis_agent

Populates:
    state["answer_stored"]    — True once the cache write completes (or fails
                                gracefully)
"""

from __future__ import annotations

import logging

from app.tools.answer_cache import answer_cache

logger = logging.getLogger(__name__)


async def storage_agent(state: dict) -> dict:
    """Store the pipeline answer in the semantic answer cache.

    Args:
        state: Pipeline state dict; must contain ``question``,
               ``query_embedding``, and ``analysis``.

    Returns:
        Updated state with ``answer_stored`` set to True.
    """
    question: str = state.get("question", "")
    query_embedding: list[float] = state.get("query_embedding", [])
    analysis: dict = state.get("analysis", {})

    if not query_embedding:
        logger.warning("StorageAgent: query_embedding is empty — skipping cache store")
        return {**state, "answer_stored": False}

    if not analysis:
        logger.warning("StorageAgent: analysis is empty — skipping cache store")
        return {**state, "answer_stored": False}

    try:
        await answer_cache.store(question, query_embedding, analysis)
        logger.info("StorageAgent: answer cached for query '%s…'", question[:60])
        stored = True
    except Exception as exc:
        logger.error("StorageAgent: failed to cache answer — %s", exc)
        stored = False

    return {
        **state,
        "answer_stored": stored,
    }
