# Phase 3 (backend agent): handle PDF file uploads → ingest pipeline


async def ingest_pdf_file(pdf_path: str, original_filename: str) -> dict:
    """Parse a PDF file and ingest it into ChromaDB.

    Returns:
        dict with paper metadata and chunk count
    """
    # TODO (backend agent): implement
    # 1. Call pdf_parser.extract_text_from_pdf(pdf_path)
    # 2. Build metadata dict
    # 3. Call pipeline.ingest_paper(text, metadata)
    raise NotImplementedError("backend agent: implement ingest_pdf_file()")
