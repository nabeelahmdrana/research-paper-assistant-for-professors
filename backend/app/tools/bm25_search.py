"""BM25 in-memory index for hybrid retrieval.

The BM25Index is built from all chunks currently stored in ChromaDB.
It is rebuilt lazily on first use and can be explicitly refreshed when
new papers are ingested (call build_index() after ingestion).

Usage:
    from app.tools.bm25_search import bm25_index
    results = await bm25_index.search(query, n=30)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rank_bm25 import BM25Okapi

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Common English stopwords — hardcoded to avoid adding nltk as a dependency.
_STOPWORDS: frozenset[str] = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "of", "in", "to", "for",
    "on", "at", "by", "with", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "out", "off", "over",
    "under", "and", "but", "or", "nor", "so", "yet", "both", "either",
    "neither", "not", "only", "own", "same", "than", "too", "very",
    "just", "this", "that", "these", "those", "it", "its",
})


def _tokenize(text: str) -> list[str]:
    """Lowercase whitespace tokenizer with English stopword removal."""
    return [w for w in text.lower().split() if w not in _STOPWORDS]


class BM25Index:
    """In-memory BM25 index wrapping rank_bm25.BM25Okapi.

    The index is keyed by chunk id so results carry the same structure
    as ChromaDB query results (id, text, metadata, score).
    """

    def __init__(self) -> None:
        self._index: BM25Okapi | None = None
        self._chunks: list[dict] = []  # ordered list matching index rows

    async def build_index(self) -> None:
        """(Re)build the BM25 index from all chunks in ChromaDB.

        This is an async method because it needs to call the async
        vector_store.get_all_chunks() helper.
        """
        # Import here to avoid circular imports at module load time
        from app.tools import vector_store  # noqa: PLC0415

        chunks = await vector_store.get_all_chunks()
        if not chunks:
            logger.warning("BM25: no chunks found in ChromaDB — index is empty")
            self._index = None
            self._chunks = []
            return

        tokenized_corpus = [_tokenize(c["text"]) for c in chunks]
        self._index = BM25Okapi(tokenized_corpus)
        self._chunks = chunks
        logger.info("BM25: built index with %d chunks", len(chunks))

    def search(self, query: str, n: int = 30) -> list[dict]:
        """Return the top-n chunks by BM25 score.

        Returns a list of dicts with keys: id, text, metadata, score.
        Score is the raw BM25 score (higher is better).
        Returns an empty list if the index has not been built yet.
        """
        if self._index is None or not self._chunks:
            return []

        tokenized_query = _tokenize(query)
        scores: list[float] = self._index.get_scores(tokenized_query).tolist()

        # Pair each chunk with its score and sort descending
        scored: list[tuple[float, dict]] = sorted(
            zip(scores, self._chunks), key=lambda x: x[0], reverse=True
        )

        results: list[dict] = []
        for score, chunk in scored[:n]:
            if score <= 0:
                break  # BM25 returns 0 for non-matching chunks; skip trailing zeros
            results.append(
                {
                    "id": chunk["id"],
                    "text": chunk["text"],
                    "metadata": chunk["metadata"],
                    "score": score,
                }
            )

        return results

    def add_chunks(self, new_chunks: list[dict]) -> None:
        """Incrementally add new chunks and rebuild the index in-memory.

        Unlike ``build_index()``, this does NOT fetch all chunks from ChromaDB.
        It appends the already-available ``new_chunks`` to ``self._chunks`` and
        rebuilds ``BM25Okapi`` from the combined in-memory list.  This eliminates
        the O(n) ChromaDB scan that ``build_index()`` performs on every ingestion.

        The cold-start full rebuild path in the retriever (``build_index()``)
        is preserved and remains the correct path after a server restart.

        Args:
            new_chunks: List of chunk dicts (id, text, metadata) just ingested.
        """
        if not new_chunks:
            return
        self._chunks.extend(new_chunks)
        tokenized_corpus = [_tokenize(c["text"]) for c in self._chunks]
        self._index = BM25Okapi(tokenized_corpus)
        logger.info(
            "BM25: incremental update — added %d chunks, total=%d",
            len(new_chunks),
            len(self._chunks),
        )

    def reset(self) -> None:
        """Clear the in-memory index (called when ChromaDB is wiped)."""
        self._index = None
        self._chunks = []
        logger.info("BM25: index cleared")

    @property
    def chunk_count(self) -> int:
        """Number of chunks currently in the index."""
        return len(self._chunks)

    @property
    def is_ready(self) -> bool:
        """True if the index has been built and contains at least one chunk."""
        return self._index is not None and len(self._chunks) > 0


# Module-level singleton — agents import this directly
bm25_index = BM25Index()
