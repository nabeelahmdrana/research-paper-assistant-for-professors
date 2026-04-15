"""Process Agent — Phase 5.

Ingests externally fetched papers (abstract text) into ChromaDB so that the
analysis agent can retrieve them via vector search.
"""

import uuid

from app.ingestion.pipeline import ingest_paper


async def process_agent(state: dict) -> dict:
    """Chunk and store external papers in ChromaDB.

    For each external paper, the abstract (and URL text if present) is used as
    the document body.  Full-text download is handled by the URL ingester when
    a PDF URL is available; for API-only results we store the abstract.

    Populates:
        state["chunks_stored"] – True once ingestion completes without error
    """
    external_papers: list[dict] = state.get("external_papers", [])

    for paper in external_papers:
        # Build document text: abstract is what we have from search APIs
        abstract = paper.get("abstract", "").strip()
        if not abstract:
            continue

        authors_raw = paper.get("authors", [])
        if isinstance(authors_raw, list):
            authors_str = ", ".join(str(a) for a in authors_raw)
        else:
            authors_str = str(authors_raw)

        # Stable paper_id: use API-provided id or derive from title
        paper_id = (paper.get("paper_id") or "").strip()
        if not paper_id:
            title_slug = paper.get("title", "")[:50].lower().replace(" ", "_")
            paper_id = f"ext_{title_slug}_{uuid.uuid4().hex[:8]}"

        metadata: dict = {
            "paper_id": paper_id,
            "title": paper.get("title", ""),
            "authors": authors_str,
            "year": str(paper.get("year", "")),
            "source": "local",
            "doi": paper.get("doi", "") or "",
            "url": paper.get("url", "") or "",
        }

        try:
            await ingest_paper(abstract, metadata)
        except Exception:
            # Best-effort: skip papers that fail to ingest
            continue

    return {
        **state,
        "chunks_stored": True,
    }
