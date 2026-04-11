# Phase 3 (backend agent): implement PDF text extraction here

from pypdf import PdfReader


def parse_pdf(file_path: str) -> str:
    """Extract text from a PDF file.

    Reads all pages and joins them with newlines.

    Args:
        file_path: Absolute or relative path to the PDF file.

    Returns:
        Full extracted text as a single string.
    """
    reader = PdfReader(file_path)
    pages_text: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages_text.append(text)
    return "\n".join(pages_text)


def extract_text_from_pdf(pdf_path: str) -> dict:
    """Extract text and metadata from a PDF file.

    Returns:
        dict with keys: title, text, page_count
    """
    reader = PdfReader(pdf_path)
    pages_text: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages_text.append(text)

    full_text = "\n".join(pages_text)

    # Attempt to get title from PDF metadata
    meta = reader.metadata or {}
    title: str = meta.get("/Title", "") or ""

    return {
        "title": title,
        "text": full_text,
        "page_count": len(reader.pages),
    }
