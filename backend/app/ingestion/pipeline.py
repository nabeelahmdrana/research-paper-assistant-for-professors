# Unified ingestion pipeline: clean → chunk → embed → store
# This is the ONLY place that does chunking and storing. Agents must call this.
#
# All chunks are stored in the 'chunks' ChromaDB collection via
# vector_store.add_documents().  The BM25 index is rebuilt after every
# successful ingestion so hybrid search stays current.

import re

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings
from app.tools import vector_store


def _clean_text(text: str) -> str:
    """Clean extracted text by removing noise and normalizing whitespace.

    Removes:
    - Page number patterns like "Page 1 of 10" or "Page 1"
    - Lines that contain only digits (lone page numbers)
    - Excessive whitespace and blank lines
    """
    # Remove "Page N of M" and "Page N" patterns
    text = re.sub(r"Page\s+\d+\s+of\s+\d+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Page\s+\d+", "", text, flags=re.IGNORECASE)

    # Remove lines that consist solely of digits (lone page numbers)
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)

    # Collapse multiple consecutive blank lines into one
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Collapse multiple spaces/tabs into a single space
    text = re.sub(r"[ \t]{2,}", " ", text)

    return text.strip()


async def ingest_paper(
    text: str,
    metadata: dict,
) -> int:
    """Ingest a paper into ChromaDB.

    Args:
        text: Full extracted text of the paper.
        metadata: dict with at least: title, authors, year, source, doi (optional),
                  and paper_id (required for chunk IDs).

    Returns:
        Number of chunks stored.
    """
    # 1. Clean text
    cleaned = _clean_text(text)

    # 2. Chunk with RecursiveCharacterTextSplitter
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    raw_chunks: list[str] = splitter.split_text(cleaned)

    if not raw_chunks:
        return 0

    paper_id: str = metadata.get("paper_id", "unknown")

    # 3. Build chunk dicts
    chunks: list[dict] = []
    for i, chunk_text in enumerate(raw_chunks):
        chunks.append(
            {
                "id": f"{paper_id}_chunk_{i}",
                "text": chunk_text,
                "metadata": {**metadata, "chunk_index": i},
            }
        )

    # 4. Store in ChromaDB ('chunks' collection)
    await vector_store.add_documents(chunks)

    # 5. Rebuild BM25 index so hybrid search reflects the new content
    try:
        from app.tools.bm25_search import bm25_index  # noqa: PLC0415

        await bm25_index.build_index()
    except Exception:
        # Non-fatal: hybrid search will fall back to vector-only on next query
        pass

    return len(chunks)
