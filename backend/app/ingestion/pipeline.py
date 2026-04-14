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

# ---------------------------------------------------------------------------
# Section-header detection
# ---------------------------------------------------------------------------

SECTION_PATTERN = re.compile(
    r"^(abstract|introduction|related work|background|methodology|methods|"
    r"results|experiments|discussion|conclusion|conclusions|references|"
    r"acknowledgments?|appendix)\b",
    re.IGNORECASE | re.MULTILINE,
)


def _detect_section(text: str, current_section: str) -> str:
    """Return the section label for a chunk of text.

    Scans the chunk for the first matching section header.  If found, that
    section label is returned; otherwise the current_section is preserved.

    Args:
        text: The chunk text to inspect.
        current_section: The section label active before this chunk.

    Returns:
        Updated section label string (lowercased, spaces replaced with
        underscores for consistent metadata values).
    """
    match = SECTION_PATTERN.search(text)
    if match:
        return match.group(1).lower().replace(" ", "_")
    return current_section


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

    # 2. Chunk using token-aware splitter (cl100k_base tokenizer, 512 tokens per chunk)
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    raw_chunks: list[str] = splitter.split_text(cleaned)

    if not raw_chunks:
        return 0

    paper_id: str = metadata.get("paper_id", "unknown")

    # 3. Build chunk dicts, tracking active section header as we walk the chunks
    chunks: list[dict] = []
    current_section: str = "body"  # default before any header is detected
    for i, chunk_text in enumerate(raw_chunks):
        current_section = _detect_section(chunk_text, current_section)
        chunks.append(
            {
                "id": f"{paper_id}_chunk_{i}",
                "text": chunk_text,
                "metadata": {**metadata, "chunk_index": i, "section_type": current_section},
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
