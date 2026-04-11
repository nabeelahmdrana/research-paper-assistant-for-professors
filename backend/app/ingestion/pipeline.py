# Phase 3 (backend agent): implement the unified ingestion pipeline
# clean → chunk → embed → store
# This is the ONLY place that does chunking and storing. Agents must call this.


async def ingest_paper(
    text: str,
    metadata: dict,
) -> int:
    """Ingest a paper into ChromaDB.

    Args:
        text: Full extracted text of the paper
        metadata: dict with at least: title, authors, year, source, doi (optional)

    Returns:
        Number of chunks stored
    """
    # TODO (backend agent): implement
    # 1. Clean text (remove excessive whitespace, page numbers)
    # 2. Chunk with RecursiveCharacterTextSplitter
    # 3. Generate embeddings with SentenceTransformer
    # 4. Store in ChromaDB via vector_store.add_documents()
    raise NotImplementedError("backend agent: implement ingest_paper()")
