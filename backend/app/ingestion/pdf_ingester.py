# Phase 3 (backend agent): handle PDF file uploads → ingest pipeline

import os
import re
import uuid
from datetime import datetime, timezone

from app.ingestion.pipeline import ingest_paper
from app.tools.pdf_parser import extract_text_from_pdf, parse_pdf


async def ingest_pdf(file_path: str, metadata: dict) -> int:
    """Parse a PDF file and ingest it into ChromaDB using provided metadata.

    Args:
        file_path: Path to the PDF file on disk.
        metadata: dict with at least paper_id, title, authors, year, source.

    Returns:
        Number of chunks stored.
    """
    text = parse_pdf(file_path)
    return await ingest_paper(text, metadata)


async def ingest_pdf_file(pdf_path: str, original_filename: str) -> dict:
    """Parse a PDF file and ingest it into ChromaDB.

    Extracts metadata from the PDF itself (title, page count) and generates
    a paper_id from the filename.

    Args:
        pdf_path: Path to the PDF file on disk.
        original_filename: The original upload filename (used to derive paper_id).

    Returns:
        dict with paper metadata and chunk_count.
    """
    extracted = extract_text_from_pdf(pdf_path)

    # Derive a stable paper_id from the filename (strip extension, sanitize)
    base_name = os.path.splitext(original_filename)[0]
    if base_name:
        paper_id = re.sub(r"[^a-zA-Z0-9_-]", "_", base_name)
    else:
        paper_id = str(uuid.uuid4())

    metadata: dict = {
        "paper_id": paper_id,
        "title": extracted.get("title") or original_filename,
        "authors": "",
        "year": "",
        "source": "local",
        "doi": "",
        "date_added": datetime.now(timezone.utc).isoformat(),
    }

    chunk_count = await ingest_paper(extracted["text"], metadata)

    return {
        **metadata,
        "page_count": extracted["page_count"],
        "chunk_count": chunk_count,
    }
