"""Reranker Agent — Phase B.

Takes the top-30 hybrid-retrieved chunks and uses a cross-encoder to select
the 10–12 most relevant chunks for the LLM synthesis step.

Reads:
    state["question"]          — original research question
    state["retrieved_chunks"]  — up to 30 chunks from the retriever

Populates:
    state["reranked_chunks"]   — top 10–12 chunks ordered by cross-encoder score
"""

from __future__ import annotations

import logging

from app.tools.reranker import reranker

logger = logging.getLogger(__name__)

_RERANK_TOP_K = 20
# Cross-encoder scores below this are considered irrelevant to the query.
# ms-marco-MiniLM-L-6-v2 gives negative scores for non-relevant (query, passage) pairs.
# -3.0 means clearly off-topic; anything above this is kept for analysis.
_MIN_RERANK_SCORE = -3.0


async def reranker_agent(state: dict) -> dict:
    """Rerank retrieved chunks using the cross-encoder model.

    Args:
        state: Pipeline state dict; must contain ``question`` and
               ``retrieved_chunks``.

    Returns:
        Updated state with ``reranked_chunks`` populated.
    """
    question: str = state.get("question", "")
    retrieved_chunks: list[dict] = state.get("retrieved_chunks", [])

    if not retrieved_chunks:
        logger.info("RerankerAgent: no retrieved chunks to rerank")
        return {
            **state,
            "reranked_chunks": [],
        }

    try:
        reranked: list[dict] = reranker.rerank(
            question,
            retrieved_chunks,
            top_k=_RERANK_TOP_K,
        )
    except Exception as exc:
        logger.error("RerankerAgent: reranking failed — %s; marking all chunks as irrelevant", exc)
        # Assign score below _MIN_RERANK_SCORE so the relevance filter drops them
        # and external search fires instead of passing stale off-topic chunks through.
        reranked = [dict(c, rerank_score=-10.0) for c in retrieved_chunks[:_RERANK_TOP_K]]

    # Drop chunks that are clearly irrelevant (very negative cross-encoder scores).
    # This prevents the analysis agent from receiving off-topic content and
    # hallucinating an answer that has nothing to do with the query.
    relevant = [c for c in reranked if c.get("rerank_score", 0.0) >= _MIN_RERANK_SCORE]

    logger.info(
        "RerankerAgent: reranked %d → %d chunks, %d passed relevance filter (threshold=%.1f)",
        len(retrieved_chunks),
        len(reranked),
        len(relevant),
        _MIN_RERANK_SCORE,
    )

    return {
        **state,
        "reranked_chunks": relevant,
    }
