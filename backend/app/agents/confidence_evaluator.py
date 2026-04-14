"""Confidence Evaluator Agent — Phase B.

Computes a 0.0–1.0 confidence score from the reranked chunks and decides
whether local content is sufficient to generate a quality answer without
triggering external search.

Score formula:
    avg_similarity  = mean(1 - distance) for each chunk
                      (uses 'distance' key from vector search, or 0.5 default)
    paper_diversity = min(unique_paper_count / 3, 1.0)   (saturates at 3 papers)
    confidence      = 0.6 * avg_similarity + 0.4 * paper_diversity

A confidence score >= settings.relevance_threshold (default 0.7) is treated
as sufficient local coverage.

Reads:
    state["reranked_chunks"]  — top chunks after cross-encoder reranking

Populates:
    state["confidence_score"]  — float in [0, 1]
    state["local_sufficient"]  — True if confidence >= threshold
"""

from __future__ import annotations

import logging

from app.config import settings

logger = logging.getLogger(__name__)


async def confidence_evaluator(state: dict) -> dict:
    """Evaluate confidence from the reranked chunk set.

    Args:
        state: Pipeline state dict; must contain ``reranked_chunks``.

    Returns:
        Updated state with ``confidence_score`` and ``local_sufficient``.
    """
    reranked_chunks: list[dict] = state.get("reranked_chunks", [])

    if not reranked_chunks:
        logger.info("ConfidenceEvaluator: no reranked chunks — confidence=0.0")
        return {
            **state,
            "confidence_score": 0.0,
            "local_sufficient": False,
        }

    # avg_similarity: 1 - cosine_distance (distance from ChromaDB is in [0, 2],
    # but vector search returns values roughly in [0, 1] for cosine space).
    # For BM25/RRF chunks without a distance key, default to 0.5.
    similarities: list[float] = []
    for chunk in reranked_chunks:
        dist = chunk.get("distance")
        if dist is not None:
            # Clamp to [0, 1] — cosine distance is typically in [0, 1] for
            # normalised vectors, but ChromaDB may return up to 2.
            similarity = max(0.0, 1.0 - float(dist))
        else:
            similarity = 0.5  # no distance info — assume moderate relevance
        similarities.append(similarity)

    avg_similarity: float = sum(similarities) / len(similarities)

    # paper_diversity: saturates at 3 unique papers
    unique_paper_ids: set[str] = set()
    for chunk in reranked_chunks:
        pid = chunk.get("metadata", {}).get("paper_id", "")
        if pid:
            unique_paper_ids.add(pid)

    paper_diversity: float = min(len(unique_paper_ids) / 3.0, 1.0)

    confidence: float = 0.6 * avg_similarity + 0.4 * paper_diversity
    local_sufficient: bool = confidence >= settings.relevance_threshold

    logger.info(
        "ConfidenceEvaluator: avg_sim=%.4f diversity=%.4f confidence=%.4f sufficient=%s",
        avg_similarity,
        paper_diversity,
        confidence,
        local_sufficient,
    )

    return {
        **state,
        "confidence_score": confidence,
        "local_sufficient": local_sufficient,
    }
