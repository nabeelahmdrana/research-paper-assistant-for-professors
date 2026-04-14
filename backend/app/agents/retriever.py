"""Retriever Agent — Phase B.

Performs hybrid retrieval by combining vector search (ChromaDB) and BM25
keyword search, then fusing the ranked lists using Reciprocal Rank Fusion.

Algorithm:
    1. Vector search  — top 30 chunks from ChromaDB cosine similarity
    2. BM25 search    — top 30 chunks from in-memory BM25Okapi index
                        (index is rebuilt from ChromaDB if empty)
    3. RRF merge      — score = sum(1 / (k + rank)) for k=60
    4. Return top 30 unique chunks ordered by RRF score

Populates:
    state["retrieved_chunks"] — list of up to 30 merged chunk dicts
"""

from __future__ import annotations

import asyncio
import logging

from app.tools import vector_store
from app.tools.bm25_search import bm25_index

logger = logging.getLogger(__name__)

_RRF_K = 60
_TOP_N = 30


def _rrf_merge(
    vector_chunks: list[dict],
    bm25_chunks: list[dict],
    k: int = _RRF_K,
    top_n: int = _TOP_N,
) -> list[dict]:
    """Reciprocal Rank Fusion of two ranked chunk lists.

    Each unique chunk (keyed by its ``id``) accumulates a score:
        score += 1 / (k + rank)     (rank is 1-based)

    Args:
        vector_chunks: Chunks ranked by vector similarity (best first).
        bm25_chunks:   Chunks ranked by BM25 score (best first).
        k:             RRF constant (default 60).
        top_n:         Maximum number of results to return.

    Returns:
        List of chunk dicts sorted by descending RRF score, length <= top_n.
    """
    scores: dict[str, float] = {}
    chunk_by_id: dict[str, dict] = {}

    for rank, chunk in enumerate(vector_chunks, start=1):
        cid = chunk.get("id", "")
        if not cid:
            continue
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
        chunk_by_id[cid] = chunk

    for rank, chunk in enumerate(bm25_chunks, start=1):
        cid = chunk.get("id", "")
        if not cid:
            continue
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
        if cid not in chunk_by_id:
            chunk_by_id[cid] = chunk

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    result: list[dict] = []
    for cid, rrf_score in ranked[:top_n]:
        entry = dict(chunk_by_id[cid])
        entry["rrf_score"] = rrf_score
        result.append(entry)

    return result


async def retriever(state: dict) -> dict:
    """Run hybrid retrieval and merge results with RRF.

    Args:
        state: Pipeline state dict; must contain ``question``.

    Returns:
        Updated state with ``retrieved_chunks`` populated.
    """
    question: str = state.get("question", "")
    sub_queries: list[str] = state.get("sub_queries", [])
    hyde_embedding: list[float] = state.get("hyde_embedding", [])

    # Ensure BM25 index is ready before launching parallel searches.
    # Index build is async so it must complete before asyncio.gather.
    if not bm25_index.is_ready:
        logger.info("Retriever: BM25 index is empty — rebuilding from ChromaDB")
        try:
            await bm25_index.build_index()
        except Exception as exc:
            logger.error("Retriever: BM25 index build failed — %s", exc)

    async def _hybrid_search(q: str) -> list[dict]:
        """Run vector + BM25 search concurrently for a single query string."""
        async def _vec() -> list[dict]:
            try:
                return await vector_store.query(q, n_results=_TOP_N)
            except Exception as exc:
                logger.error("Retriever: vector search failed ('%s…') — %s", q[:40], exc)
                return []

        async def _bm25() -> list[dict]:
            try:
                return bm25_index.search(q, n=_TOP_N)
            except Exception as exc:
                logger.error("Retriever: BM25 search failed ('%s…') — %s", q[:40], exc)
                return []

        vec_chunks, b25_chunks = await asyncio.gather(_vec(), _bm25())
        return _rrf_merge(vec_chunks, b25_chunks, k=_RRF_K, top_n=_TOP_N)

    # Collect all queries: original + any sub-queries from the expander
    all_queries = [question] + sub_queries

    # Build the list of coroutines to run concurrently:
    #   - hybrid search (text + BM25) for each query variant
    #   - HyDE vector search using the pre-computed hypothetical doc embedding
    coros = [_hybrid_search(q) for q in all_queries]

    async def _hyde_vector_search() -> list[dict]:
        """Vector-only search using the HyDE hypothetical document embedding."""
        try:
            return await vector_store.query_by_embedding(hyde_embedding, n_results=_TOP_N)
        except Exception as exc:
            logger.warning("Retriever: HyDE vector search failed — %s", exc)
            return []

    if hyde_embedding:
        coros.append(_hyde_vector_search())

    per_query_results: list[list[dict]] = await asyncio.gather(*coros)

    # Merge all result lists iteratively via RRF
    merged: list[dict] = per_query_results[0]
    for extra_list in per_query_results[1:]:
        merged = _rrf_merge(merged, extra_list, k=_RRF_K, top_n=_TOP_N)

    logger.info(
        "Retriever: queries=%d hyde=%s merged=%d",
        len(all_queries),
        bool(hyde_embedding),
        len(merged),
    )

    return {
        **state,
        "retrieved_chunks": merged,
    }
