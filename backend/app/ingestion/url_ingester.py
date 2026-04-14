# Phase 3 (backend agent): handle DOI/URL paper fetching → ingest pipeline

import os
import re
import tempfile
import uuid
from datetime import datetime, timezone

import httpx

from app.ingestion.pdf_ingester import ingest_pdf
from app.ingestion.pipeline import ingest_paper


def _strip_html_tags(html: str) -> str:
    """Remove HTML tags and decode common entities."""
    # Remove script/style blocks entirely
    html = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove all remaining tags
    html = re.sub(r"<[^>]+>", " ", html)
    # Decode common entities
    html = html.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    html = html.replace("&nbsp;", " ").replace("&quot;", '"').replace("&#39;", "'")
    # Collapse whitespace
    html = re.sub(r"[ \t]{2,}", " ", html)
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()


async def ingest_url(url: str, metadata: dict) -> int:
    """Fetch content from a URL and ingest it into ChromaDB.

    If the URL returns a PDF (by Content-Type), it is saved to a temp file
    and processed via the PDF ingester. Otherwise the content is treated as
    HTML/text, stripped of tags, and passed directly to the ingestion pipeline.

    Args:
        url: The HTTP/HTTPS URL to fetch.
        metadata: dict with at least paper_id, title, authors, year, source.

    Returns:
        Number of chunks stored.
    """
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "").lower()

        if "application/pdf" in content_type or url.lower().endswith(".pdf"):
            # Save to a temporary file and use the PDF ingester
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(response.content)
                tmp_path = tmp.name

            try:
                return await ingest_pdf(tmp_path, metadata)
            finally:
                os.unlink(tmp_path)
        else:
            # Treat as HTML or plain text
            raw_text = response.text
            if "text/html" in content_type or "<html" in raw_text[:500].lower():
                text = _strip_html_tags(raw_text)
            else:
                text = raw_text

            return await ingest_paper(text, metadata)


async def ingest_by_doi_or_url(doi_or_url: str) -> dict:
    """Fetch paper metadata from Semantic Scholar by DOI or URL and ingest it.

    Accepts a DOI (e.g. "10.1234/example") or a full URL.

    Returns:
        dict with paper metadata and chunk_count.
    """
    # Determine if this looks like a bare DOI or a full URL
    if doi_or_url.startswith("http://") or doi_or_url.startswith("https://"):
        url = doi_or_url
        doi = ""
    else:
        # Assume it is a DOI
        doi = doi_or_url
        url = f"https://doi.org/{doi}"

    # Try to fetch metadata from Semantic Scholar
    ss_url = f"https://api.semanticscholar.org/graph/v1/paper/{doi or url}"
    ss_fields = "title,authors,year,abstract,externalIds"

    title = ""
    authors = ""
    year = ""
    abstract = ""
    paper_id = str(uuid.uuid4())

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            ss_resp = await client.get(ss_url, params={"fields": ss_fields})
            if ss_resp.status_code == 200:
                ss_data = ss_resp.json()
                title = ss_data.get("title", "")
                author_list = [a.get("name", "") for a in ss_data.get("authors", [])]
                authors = ", ".join(author_list)
                year = str(ss_data.get("year", ""))
                abstract = ss_data.get("abstract", "") or ""
                paper_id = ss_data.get("paperId", paper_id)
        except httpx.HTTPError:
            pass

    metadata: dict = {
        "paper_id": paper_id,
        "title": title or doi_or_url,
        "authors": authors,
        "year": year,
        "source": "external",
        "doi": doi,
        "abstract": abstract,
        "date_added": datetime.now(timezone.utc).isoformat(),
    }

    chunk_count = await ingest_url(url, metadata)

    return {**metadata, "chunk_count": chunk_count}
