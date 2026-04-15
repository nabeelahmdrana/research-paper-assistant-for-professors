# All ChromaDB access in the project goes through this module only.
#
# Three collections are used:
#   papers_meta  — one document per paper (title, authors, year, abstract, …)
#   chunks       — chunked text used for retrieval / RAG
#   answers      — cached query embeddings + structured answers (semantic cache)
#
# MIGRATION NOTE:
#   The embedding model was changed from all-MiniLM-L6-v2 (dim=384) to
#   text-embedding-3-small (dim=1536).  Any existing ChromaDB data built with
#   the old model MUST be cleared before starting with the new model.
#   The startup check below logs a WARNING if a dimension mismatch is detected.

import logging
import time

import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

from app.config import settings

logger = logging.getLogger(__name__)

# Known embedding dimensions for the startup compatibility check.
_KNOWN_DIMS: dict[str, int] = {
    "all-MiniLM-L6-v2": 384,
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}

# ---------------------------------------------------------------------------
# Shared ChromaDB client (singleton)
# ---------------------------------------------------------------------------

_client: chromadb.ClientAPI | None = None
_embedding_fn: OpenAIEmbeddingFunction | None = None

# Per-collection singletons
_chunks_collection: chromadb.Collection | None = None
_papers_meta_collection: chromadb.Collection | None = None
_answers_collection: chromadb.Collection | None = None


def _get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.chroma_db_path)
    return _client


def _get_embedding_fn() -> OpenAIEmbeddingFunction:
    global _embedding_fn
    if _embedding_fn is None:
        kwargs: dict = {
            "api_key": settings.openai_api_key,
            "model_name": settings.embedding_model,
        }
        # Route through the configured base URL (e.g. a custom OpenAI-compatible
        # endpoint) so the same API key works for both the LLM and embeddings.
        if settings.openai_base_url and settings.openai_base_url != "https://api.openai.com/v1":
            kwargs["api_base"] = settings.openai_base_url
        _embedding_fn = OpenAIEmbeddingFunction(**kwargs)
    return _embedding_fn


def _check_embedding_dimension_compat(collection: chromadb.Collection) -> None:
    """Log a warning if the collection was built with a different embedding model.

    ChromaDB does not store the model name, but we can detect a mismatch by
    sampling one stored embedding and comparing its dimension to what the
    currently configured model would produce.
    """
    try:
        if collection.count() == 0:
            return
        sample = collection.get(limit=1, include=["embeddings"])
        embeddings = sample.get("embeddings") or []
        if not embeddings or not embeddings[0]:
            return
        stored_dim = len(embeddings[0])
        expected_dim = _KNOWN_DIMS.get(settings.embedding_model)
        if expected_dim is not None and stored_dim != expected_dim:
            logger.warning(
                "EMBEDDING DIMENSION MISMATCH: collection '%s' has stored vectors of "
                "dim=%d but current model '%s' produces dim=%d.  "
                "Clear the ChromaDB collections (chroma_db/) and re-ingest all papers "
                "before running queries.",
                collection.name,
                stored_dim,
                settings.embedding_model,
                expected_dim,
            )
    except Exception:
        pass  # non-fatal — just a diagnostic check


# ---------------------------------------------------------------------------
# Collection accessors
# ---------------------------------------------------------------------------

def get_chunks_collection() -> chromadb.Collection:
    """Return the 'chunks' collection (chunked paper text for retrieval)."""
    global _chunks_collection
    if _chunks_collection is None:
        _chunks_collection = _get_client().get_or_create_collection(
            name="chunks",
            embedding_function=_get_embedding_fn(),
            metadata={"hnsw:space": "cosine"},
        )
        _check_embedding_dimension_compat(_chunks_collection)
    return _chunks_collection


def get_papers_meta_collection() -> chromadb.Collection:
    """Return the 'papers_meta' collection (one doc per paper)."""
    global _papers_meta_collection
    if _papers_meta_collection is None:
        _papers_meta_collection = _get_client().get_or_create_collection(
            name="papers_meta",
            embedding_function=_get_embedding_fn(),
            metadata={"hnsw:space": "cosine"},
        )
    return _papers_meta_collection


def get_answers_collection() -> chromadb.Collection:
    """Return the 'answers' collection (semantic answer cache)."""
    global _answers_collection
    if _answers_collection is None:
        _answers_collection = _get_client().get_or_create_collection(
            name="answers",
            embedding_function=_get_embedding_fn(),
            metadata={"hnsw:space": "cosine"},
        )
    return _answers_collection


# ---------------------------------------------------------------------------
# Legacy accessor kept for backward compatibility with existing callers
# (papers.py API routes use get_collection() directly)
# ---------------------------------------------------------------------------

def get_collection() -> chromadb.Collection:
    """Return the chunks collection (backward-compatible alias)."""
    return get_chunks_collection()


def reset_collection_singletons() -> None:
    """Drop all cached collection references so they are re-opened on next access.

    Call this after the ChromaDB directory has been wiped so stale collection
    objects are not reused.
    """
    global _client, _chunks_collection, _papers_meta_collection, _answers_collection
    _client = None
    _chunks_collection = None
    _papers_meta_collection = None
    _answers_collection = None
    logger.info("vector_store: collection singletons reset")


# ---------------------------------------------------------------------------
# Chunk CRUD — operates on the 'chunks' collection
# ---------------------------------------------------------------------------

async def add_documents(chunks: list[dict]) -> None:
    """Add document chunks to the 'chunks' collection.

    Each chunk must have keys: id, text, metadata.
    metadata should include: title, authors, year, source, doi, paper_id, chunk_index.
    """
    if not chunks:
        return

    collection = get_chunks_collection()
    ids = [chunk["id"] for chunk in chunks]
    documents = [chunk["text"] for chunk in chunks]
    metadatas = [chunk["metadata"] for chunk in chunks]

    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    _invalidate_paper_count_cache()


async def query(text: str, n_results: int = 10) -> list[dict]:
    """Vector-similarity query against the 'chunks' collection.

    Returns a list of dicts with keys: id, text, metadata, distance.
    """
    collection = get_chunks_collection()
    count = collection.count()
    if count == 0:
        return []

    actual_n = min(n_results, count)
    results = collection.query(query_texts=[text], n_results=actual_n)

    output: list[dict] = []
    ids = results["ids"][0]
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for doc_id, doc_text, meta, dist in zip(ids, documents, metadatas, distances):
        output.append(
            {
                "id": doc_id,
                "text": doc_text,
                "metadata": meta,
                "distance": dist,
            }
        )

    return output


async def query_by_embedding(embedding: list[float], n_results: int = 10) -> list[dict]:
    """Vector-similarity query using a pre-computed embedding vector.

    Unlike query(), this does NOT re-embed the input — it uses the provided
    vector directly.  Used by HyDE retrieval where the hypothetical document
    has already been embedded by the query processor.

    Returns a list of dicts with keys: id, text, metadata, distance.
    """
    collection = get_chunks_collection()
    count = collection.count()
    if count == 0:
        return []

    actual_n = min(n_results, count)
    results = collection.query(query_embeddings=[embedding], n_results=actual_n)

    output: list[dict] = []
    ids = results["ids"][0]
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for doc_id, doc_text, meta, dist in zip(ids, documents, metadatas, distances):
        output.append(
            {
                "id": doc_id,
                "text": doc_text,
                "metadata": meta,
                "distance": dist,
            }
        )

    return output


async def query_with_embeddings(
    text: str,
    n_results: int = 10,
) -> tuple[list[dict], list[list[float]]]:
    """Like query() but also returns the raw embedding vectors for each result.

    Returns:
        (chunks, embeddings) where embeddings[i] corresponds to chunks[i].
    """
    collection = get_chunks_collection()
    count = collection.count()
    if count == 0:
        return [], []

    actual_n = min(n_results, count)
    results = collection.query(
        query_texts=[text],
        n_results=actual_n,
        include=["documents", "metadatas", "distances", "embeddings"],
    )

    chunks: list[dict] = []
    raw_embeddings: list[list[float]] = []

    ids = results["ids"][0]
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]
    embeddings = (results.get("embeddings") or [[]])[0]

    for i, (doc_id, doc_text, meta, dist) in enumerate(
        zip(ids, documents, metadatas, distances)
    ):
        chunks.append(
            {
                "id": doc_id,
                "text": doc_text,
                "metadata": meta,
                "distance": dist,
            }
        )
        raw_embeddings.append(embeddings[i] if i < len(embeddings) else [])

    return chunks, raw_embeddings


async def get_all_chunks() -> list[dict]:
    """Return all chunks stored in the 'chunks' collection.

    Used by the BM25 index builder at startup.
    """
    collection = get_chunks_collection()
    if collection.count() == 0:
        return []

    all_docs = collection.get()
    ids = all_docs.get("ids") or []
    documents = all_docs.get("documents") or []
    metadatas = all_docs.get("metadatas") or []

    output: list[dict] = []
    for doc_id, doc_text, meta in zip(ids, documents, metadatas):
        output.append(
            {
                "id": doc_id,
                "text": doc_text or "",
                "metadata": meta or {},
            }
        )
    return output


# ---------------------------------------------------------------------------
# Paper metadata CRUD — operates on 'papers_meta' collection
# ---------------------------------------------------------------------------

async def upsert_paper_meta(paper_id: str, text: str, metadata: dict) -> None:
    """Insert or update a paper's metadata entry in 'papers_meta'."""
    collection = get_papers_meta_collection()
    # ChromaDB upsert: add if missing, update if present
    collection.upsert(
        ids=[paper_id],
        documents=[text],
        metadatas=[metadata],
    )


# ---------------------------------------------------------------------------
# Shared list / delete helpers — operate on 'chunks' for backward compat
# ---------------------------------------------------------------------------

async def list_papers() -> list[dict]:
    """List all unique papers stored in the 'chunks' collection.

    Deduplicates by paper_id in metadata and returns one record per paper.
    Falls back to the legacy 'research_papers' collection if the 'chunks'
    collection is empty (migration path for existing data).
    """
    collection = get_chunks_collection()

    # Fallback: check the legacy collection if chunks is empty
    if collection.count() == 0:
        try:
            legacy = _get_client().get_collection(
                name=settings.chroma_collection_name,
                embedding_function=_get_embedding_fn(),
            )
            if legacy.count() > 0:
                collection = legacy
        except Exception:
            pass

    if collection.count() == 0:
        return []

    all_docs = collection.get(include=["metadatas", "documents"])
    seen_paper_ids: set[str] = set()
    paper_chunks: dict[str, list[str]] = {}
    papers: list[dict] = []

    metadatas = all_docs.get("metadatas") or []
    documents = all_docs.get("documents") or []

    for i, meta in enumerate(metadatas):
        paper_id = meta.get("paper_id", "")
        if not paper_id:
            continue

        doc_text = documents[i] if i < len(documents) else ""

        if paper_id not in seen_paper_ids:
            seen_paper_ids.add(paper_id)
            paper_chunks[paper_id] = []
            papers.append(
                {
                    "paper_id": paper_id,
                    "title": meta.get("title", ""),
                    "authors": meta.get("authors", ""),
                    "year": meta.get("year", ""),
                    "source": meta.get("source", ""),
                    "doi": meta.get("doi", ""),
                    "abstract": meta.get("abstract", ""),
                    "url": meta.get("url", ""),
                    "date_added": meta.get("date_added", ""),
                }
            )

        if doc_text:
            paper_chunks[paper_id].append(doc_text)

    # Fill in missing abstracts from chunk document text
    for paper in papers:
        if not paper["abstract"] and paper["paper_id"] in paper_chunks:
            chunks = paper_chunks[paper["paper_id"]]
            if chunks:
                paper["abstract"] = chunks[0]

    return papers


async def delete_paper(paper_id: str) -> bool:
    """Delete all chunks for a given paper from 'chunks' (and papers_meta if present).

    Returns True if any deletion was performed, False if the paper was not found.
    """
    chunks_col = get_chunks_collection()
    results = chunks_col.get(where={"paper_id": paper_id})
    ids_to_delete = results.get("ids", [])

    deleted = False
    if ids_to_delete:
        chunks_col.delete(ids=ids_to_delete)
        deleted = True
        _invalidate_paper_count_cache()

    # Also clean up papers_meta entry if present
    meta_col = get_papers_meta_collection()
    try:
        meta_col.delete(ids=[paper_id])
    except Exception:
        pass

    # Also attempt removal from legacy collection (migration path)
    try:
        legacy = _get_client().get_collection(
            name=settings.chroma_collection_name,
            embedding_function=_get_embedding_fn(),
        )
        legacy_results = legacy.get(where={"paper_id": paper_id})
        legacy_ids = legacy_results.get("ids", [])
        if legacy_ids:
            legacy.delete(ids=legacy_ids)
            deleted = True
    except Exception:
        pass

    return deleted


# ---------------------------------------------------------------------------
# paper_count cache (30-second TTL)
# Avoids a full ChromaDB scan on every /api/health and /api/stats request.
# Invalidated by add_documents() and delete_paper().
# ---------------------------------------------------------------------------
_paper_count_cache: tuple[int, float] | None = None  # (count, timestamp)
_PAPER_COUNT_TTL = 30.0  # seconds


def _invalidate_paper_count_cache() -> None:
    global _paper_count_cache
    _paper_count_cache = None


async def paper_count() -> int:
    """Return the number of unique papers, using a 30-second in-memory cache."""
    global _paper_count_cache
    now = time.monotonic()
    if _paper_count_cache is not None:
        count, ts = _paper_count_cache
        if now - ts < _PAPER_COUNT_TTL:
            return count

    chunks_col = get_chunks_collection()
    paper_ids: set[str] = set()

    if chunks_col.count() > 0:
        all_docs = chunks_col.get()
        metadatas = all_docs.get("metadatas") or []
        for meta in metadatas:
            pid = meta.get("paper_id", "")
            if pid:
                paper_ids.add(pid)

    # Include legacy collection if it exists
    try:
        legacy = _get_client().get_collection(
            name=settings.chroma_collection_name,
            embedding_function=_get_embedding_fn(),
        )
        if legacy.count() > 0:
            all_docs = legacy.get()
            metadatas = all_docs.get("metadatas") or []
            for meta in metadatas:
                pid = meta.get("paper_id", "")
                if pid:
                    paper_ids.add(pid)
    except Exception:
        pass

    result = len(paper_ids)
    _paper_count_cache = (result, now)
    return result
