"""Query Processor Agent — Phase B.

Normalises the incoming query and generates its embedding so that all
downstream agents work from a consistent representation.

Populates:
    state["normalized_query"]  — stripped and lowercased query text
    state["query_embedding"]   — float list from all-MiniLM-L6-v2
"""

from __future__ import annotations

import logging

from sentence_transformers import SentenceTransformer

from app.config import settings

logger = logging.getLogger(__name__)

# Singleton model — loaded once per worker process
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model)
        logger.info("QueryProcessor: loaded embedding model '%s'", settings.embedding_model)
    return _model


async def query_processor(state: dict) -> dict:
    """Normalise the query and compute its embedding.

    Args:
        state: Pipeline state dict; must contain ``question`` key.

    Returns:
        Updated state with ``normalized_query`` and ``query_embedding`` added.
    """
    question: str = state.get("question", "")

    # Normalise: strip whitespace and lowercase for cache / BM25 matching
    normalized_query: str = question.strip().lower()

    # Generate embedding via the same model used for chunk indexing
    try:
        model = _get_model()
        embedding: list[float] = model.encode(normalized_query).tolist()
    except Exception as exc:
        logger.error("QueryProcessor: embedding failed — %s", exc)
        embedding = []

    return {
        **state,
        "normalized_query": normalized_query,
        "query_embedding": embedding,
    }
