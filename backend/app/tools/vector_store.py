# Phase 3 (backend agent): implement ChromaDB operations here
# All ChromaDB access in the project goes through this file only

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from app.config import settings


def get_collection() -> chromadb.Collection:
    """Initialize and return the ChromaDB collection."""
    embedding_fn = SentenceTransformerEmbeddingFunction(
        model_name=settings.embedding_model
    )
    client = chromadb.PersistentClient(path=settings.chroma_db_path)
    return client.get_or_create_collection(
        name=settings.chroma_collection_name,
        embedding_function=embedding_fn,
    )


async def add_documents(chunks: list[dict]) -> None:
    """Add document chunks to ChromaDB.

    Each chunk must have keys: id, text, metadata.
    metadata should include: title, authors, year, source, doi, paper_id, chunk_index.
    """
    if not chunks:
        return

    collection = get_collection()
    ids = [chunk["id"] for chunk in chunks]
    documents = [chunk["text"] for chunk in chunks]
    metadatas = [chunk["metadata"] for chunk in chunks]

    collection.add(ids=ids, documents=documents, metadatas=metadatas)


async def query(text: str, n_results: int = 10) -> list[dict]:
    """Query ChromaDB for relevant chunks.

    Returns a list of dicts with keys: id, text, metadata, distance.
    """
    collection = get_collection()
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


async def list_papers() -> list[dict]:
    """List all unique papers stored in ChromaDB.

    Deduplicates by paper_id in metadata and returns one record per paper.
    """
    collection = get_collection()
    if collection.count() == 0:
        return []

    all_docs = collection.get()
    seen_paper_ids: set[str] = set()
    papers: list[dict] = []

    metadatas = all_docs.get("metadatas") or []
    for meta in metadatas:
        paper_id = meta.get("paper_id", "")
        if paper_id and paper_id not in seen_paper_ids:
            seen_paper_ids.add(paper_id)
            papers.append(
                {
                    "paper_id": paper_id,
                    "title": meta.get("title", ""),
                    "authors": meta.get("authors", ""),
                    "year": meta.get("year", ""),
                    "source": meta.get("source", ""),
                    "doi": meta.get("doi", ""),
                }
            )

    return papers


async def delete_paper(paper_id: str) -> bool:
    """Delete all chunks for a given paper.

    Returns True if deletion was attempted, False if paper not found.
    """
    collection = get_collection()
    results = collection.get(where={"paper_id": paper_id})
    ids_to_delete = results.get("ids", [])

    if not ids_to_delete:
        return False

    collection.delete(ids=ids_to_delete)
    return True


async def paper_count() -> int:
    """Return the number of unique papers stored."""
    collection = get_collection()
    if collection.count() == 0:
        return 0

    all_docs = collection.get()
    metadatas = all_docs.get("metadatas") or []
    paper_ids = {meta.get("paper_id", "") for meta in metadatas if meta.get("paper_id")}
    return len(paper_ids)
