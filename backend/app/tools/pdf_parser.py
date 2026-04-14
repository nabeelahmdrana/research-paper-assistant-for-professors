"""PDF text extraction using PyMuPDF (fitz).

PyMuPDF extracts text blocks in reading order (sorted by vertical then
horizontal position), which produces better-quality text than pypdf's
character-level extraction, especially for multi-column layouts.

Both public functions keep the same signatures as the previous pypdf
implementation so that all callers are unaffected.
"""

import fitz  # pymupdf


def _extract_text_blocks_in_order(page: fitz.Page) -> str:  # type: ignore[name-defined]
    """Extract text from a single page, sorted in reading order.

    PyMuPDF returns raw blocks; we sort by (y0, x0) to approximate
    top-to-bottom, left-to-right reading order before joining.

    Args:
        page: A fitz.Page object.

    Returns:
        Page text as a single string.
    """
    blocks = page.get_text("blocks")  # list of (x0, y0, x1, y1, text, block_no, block_type)
    # Filter to text blocks only (block_type == 0) and sort by position
    text_blocks = [b for b in blocks if b[6] == 0]
    text_blocks.sort(key=lambda b: (b[1], b[0]))  # sort by (y0, x0)
    return "\n".join(b[4].strip() for b in text_blocks if b[4].strip())


def parse_pdf(file_path: str) -> str:
    """Extract text from a PDF file.

    Reads all pages in reading order and joins them with newlines.

    Args:
        file_path: Absolute or relative path to the PDF file.

    Returns:
        Full extracted text as a single string.
    """
    doc = fitz.open(file_path)
    pages_text: list[str] = []
    for page in doc:
        pages_text.append(_extract_text_blocks_in_order(page))
    doc.close()
    return "\n".join(pages_text)


def extract_text_from_pdf(pdf_path: str) -> dict:
    """Extract text and metadata from a PDF file.

    Returns:
        dict with keys: title, text, page_count
    """
    doc = fitz.open(pdf_path)
    pages_text: list[str] = []
    for page in doc:
        pages_text.append(_extract_text_blocks_in_order(page))

    full_text = "\n".join(pages_text)

    # Attempt to get title from PDF metadata
    meta = doc.metadata or {}
    title: str = meta.get("title", "") or ""

    page_count = doc.page_count
    doc.close()

    return {
        "title": title,
        "text": full_text,
        "page_count": page_count,
    }
