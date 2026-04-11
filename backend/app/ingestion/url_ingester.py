# Phase 3 (backend agent): handle DOI/URL paper fetching → ingest pipeline


async def ingest_by_doi_or_url(doi_or_url: str) -> dict:
    """Fetch paper metadata from Semantic Scholar by DOI or URL and ingest it.

    Returns:
        dict with paper metadata and chunk count
    """
    # TODO (backend agent): implement
    # 1. Detect if input is DOI or URL
    # 2. Fetch from Semantic Scholar API
    # 3. Build metadata dict
    # 4. Call pipeline.ingest_paper(abstract_text, metadata)
    raise NotImplementedError("backend agent: implement ingest_by_doi_or_url()")
