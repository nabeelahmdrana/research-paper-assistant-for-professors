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

_RERANK_TOP_K = 12


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
        logger.error("RerankerAgent: reranking failed — %s; falling back to top_k slice", exc)
        reranked = [dict(c, rerank_score=0.0) for c in retrieved_chunks[:_RERANK_TOP_K]]

    logger.info(
        "RerankerAgent: reranked %d → %d chunks",
        len(retrieved_chunks),
        len(reranked),
    )

    return {
        **state,
        "reranked_chunks": reranked,
    }
