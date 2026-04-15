"""Cross-encoder reranker for reducing retrieved chunks before LLM synthesis.

Uses sentence-transformers' CrossEncoder with the model configured via
settings.reranker_model (default: BAAI/bge-reranker-large) to score
(query, passage) pairs.

The model is loaded once at startup and reused for every request.

Usage:
    from app.tools.reranker import reranker
    top_chunks = reranker.rerank(query, chunks, top_k=20)
"""

from __future__ import annotations

import logging

from app.config import settings

logger = logging.getLogger(__name__)


class Reranker:
    """Wraps a CrossEncoder to rerank retrieved chunks by relevance.

    The model is loaded lazily on the first call to rerank() so that
    import time stays fast even if the model weights need to be downloaded.

    The model name is read from settings.reranker_model so it can be
    overridden via the RERANKER_MODEL environment variable without code changes.
    """

    def __init__(self) -> None:
        self._model_name: str | None = None  # resolved lazily from settings
        self._model = None  # loaded on first use

    def _load(self) -> None:
        if self._model is not None:
            return
        # Resolve model name from settings at load time (supports env override)
        model_name = settings.reranker_model
        self._model_name = model_name
        try:
            from sentence_transformers import CrossEncoder  # noqa: PLC0415

            self._model = CrossEncoder(model_name)
            logger.info("Reranker: loaded model '%s'", model_name)
        except Exception as exc:
            logger.error("Reranker: failed to load model — %s", exc)
            self._model = None

    def rerank(
        self,
        query: str,
        chunks: list[dict],
        top_k: int = 12,
    ) -> list[dict]:
        """Score each (query, chunk_text) pair and return the top_k by score.

        Args:
            query:  The research question / query string.
            chunks: List of chunk dicts, each with at least a 'text' key.
                    Additional keys (id, metadata, distance, score, …) are
                    preserved in the output.
            top_k:  Maximum number of chunks to return after reranking.

        Returns:
            List of chunk dicts (same shape as input) sorted by cross-encoder
            score descending, truncated to top_k.  Each dict gains a
            'rerank_score' float key.

        Falls back to returning the first top_k chunks unchanged if the model
        could not be loaded.
        """
        if not chunks:
            return []

        self._load()

        if self._model is None:
            # Model unavailable — mark all chunks as irrelevant (score=-10.0) so
            # the reranker_agent's relevance filter drops them and the pipeline
            # falls through to external search.  Never assign a neutral 0.0 here
            # because 0.0 > _MIN_RERANK_SCORE (-3.0) and would let stale, off-topic
            # library chunks pass through to the analysis agent.
            logger.warning(
                "Reranker: model unavailable — marking all chunks as irrelevant (score=-10.0)"
            )
            return [dict(c, rerank_score=-10.0) for c in chunks[:top_k]]

        pairs = [(query, c["text"]) for c in chunks]
        try:
            scores: list[float] = self._model.predict(pairs).tolist()
        except Exception as exc:
            logger.error("Reranker: prediction error — %s", exc)
            # Same reasoning as model-unavailable path: irrelevant score so
            # off-topic library chunks don't silently pass the relevance filter.
            return [dict(c, rerank_score=-10.0) for c in chunks[:top_k]]

        scored_chunks = sorted(
            [dict(chunk, rerank_score=score) for chunk, score in zip(chunks, scores)],
            key=lambda x: x["rerank_score"],
            reverse=True,
        )

        return scored_chunks[:top_k]


# Module-level singleton — agents import this directly.
# Model name is resolved from settings.reranker_model on first use.
reranker = Reranker()
