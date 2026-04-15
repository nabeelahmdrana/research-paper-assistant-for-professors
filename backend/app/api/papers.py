import asyncio
import logging
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

import httpx

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agents.external_search_agent import _call_mcp_tool
from app.config import settings
from app.ingestion.pdf_ingester import ingest_pdf_file
from app.ingestion.pipeline import ingest_paper
from app.ingestion.url_ingester import ingest_by_doi_or_url
from app.models.schemas import SaveExternalPaperRequest
from app.tools import vector_store
from app.tools import pdf_storage
from app.tools import sqlite_store

router = APIRouter()


def _make_paper_id(title: str) -> str:
    """Derive a stable paper_id slug from a title when no API id is available."""
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower())[:40]
    return f"ext_{slug}"


def _build_paper_response(raw: dict, *, has_pdf: bool = False) -> dict:
    """Normalise a raw vector-store paper dict into the API Paper shape."""
    authors_raw = raw.get("authors", "")
    if isinstance(authors_raw, list):
        authors = authors_raw
    else:
        authors = [a.strip() for a in str(authors_raw).split(",") if a.strip()]

    year_raw = raw.get("year", "")
    try:
        year = int(year_raw)
    except (ValueError, TypeError):
        year = year_raw or 0

    return {
        "id": raw.get("paper_id", ""),
        "title": raw.get("title", ""),
        "authors": authors,
        "year": year,
        "source": raw.get("source", "local"),
        "abstract": raw.get("abstract", ""),
        "doi": raw.get("doi") or None,
        "url": raw.get("url") or None,
        "dateAdded": raw.get("date_added", datetime.now(timezone.utc).isoformat()),
        "hasPdf": has_pdf,
    }


# ---------------------------------------------------------------------------
# SQLite persistence helper
# ---------------------------------------------------------------------------

async def _save_paper_to_sqlite(raw: dict, chunk_count: int = 0) -> None:
    """Persist paper metadata to the SQLite papers table.

    Errors are swallowed so a SQLite failure never blocks the upload response.
    After saving, the pipeline_stats paper count is refreshed from ChromaDB.
    """
    try:
        paper_id = raw.get("paper_id") or raw.get("id", "")
        if not paper_id:
            return

        authors_raw = raw.get("authors", "")
        if isinstance(authors_raw, list):
            authors = authors_raw
        else:
            authors = [a.strip() for a in str(authors_raw).split(",") if a.strip()]

        await sqlite_store.save_paper(
            paper_id=paper_id,
            title=raw.get("title", ""),
            authors=authors,
            abstract=raw.get("abstract", ""),
            source=raw.get("source", ""),
            file_name=raw.get("filename") or raw.get("file_name"),
            url=raw.get("url"),
            doi=raw.get("doi"),
            chunk_count=chunk_count,
            created_at=raw.get("date_added", datetime.now(timezone.utc).isoformat()),
        )
    except Exception as exc:
        logger.warning("_save_paper_to_sqlite: save_paper failed (non-fatal): %s", exc)

    # Refresh paper count in pipeline_stats
    try:
        total_papers = await vector_store.paper_count()
        stats = await sqlite_store.fetch_pipeline_stats()
        await sqlite_store.upsert_pipeline_stats(
            total_papers=total_papers,
            total_queries=stats.get("total_queries", 0),
            avg_processing_time=stats.get("avg_processing_time", 0.0),
        )
    except Exception as exc:
        logger.warning("_save_paper_to_sqlite: upsert_pipeline_stats failed (non-fatal): %s", exc)


# ---------------------------------------------------------------------------
# POST /api/papers/upload
# ---------------------------------------------------------------------------

class UploadFileSizeError(Exception):
    pass


@router.post("/papers/upload")
async def upload_papers(files: list[UploadFile] = File(...)) -> dict:
    """Upload one or more PDF files and ingest them into ChromaDB."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    uploaded: list[dict] = []
    errors: list[str] = []

    for upload in files:
        filename = upload.filename or "unknown.pdf"

        if not filename.lower().endswith(".pdf"):
            errors.append(f"{filename}: only PDF files are supported")
            continue

        content = await upload.read()

        max_bytes = settings.max_file_size_mb * 1024 * 1024
        if len(content) > max_bytes:
            errors.append(
                f"{filename}: file exceeds {settings.max_file_size_mb} MB limit"
            )
            continue

        # Write to a temp file so the PDF parser can seek
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            result = await ingest_pdf_file(tmp_path, filename)
            paper_id = result.get("paper_id", "")
            # Persist the original PDF bytes so users can retrieve the file later
            if paper_id:
                await pdf_storage.store_pdf(paper_id, filename, content)
            uploaded.append(_build_paper_response(result, has_pdf=bool(paper_id)))
            # Persist metadata to SQLite
            result_with_filename = {**result, "filename": filename}
            await _save_paper_to_sqlite(result_with_filename)
        except Exception as exc:
            errors.append(f"{filename}: {exc}")
        finally:
            os.unlink(tmp_path)

    return {
        "data": {"uploaded": len(uploaded), "papers": uploaded, "errors": errors},
        "error": None,
        "status": 200,
    }


# ---------------------------------------------------------------------------
# POST /api/papers/doi
# ---------------------------------------------------------------------------

class DoiRequest(BaseModel):
    dois: list[str]


@router.post("/papers/doi")
async def fetch_papers_by_doi(body: DoiRequest) -> dict:
    """Fetch papers by DOI or URL and ingest them into ChromaDB."""
    if not body.dois:
        raise HTTPException(status_code=400, detail="No DOIs provided")

    fetched: list[dict] = []
    errors: list[str] = []

    for doi_or_url in body.dois:
        doi_or_url = doi_or_url.strip()
        if not doi_or_url:
            continue
        try:
            result = await ingest_by_doi_or_url(doi_or_url)
            fetched.append(_build_paper_response(result))
            await _save_paper_to_sqlite(result)
        except Exception as exc:
            errors.append(f"{doi_or_url}: {exc}")

    return {
        "data": {"fetched": len(fetched), "papers": fetched, "errors": errors},
        "error": None,
        "status": 200,
    }


# ---------------------------------------------------------------------------
# GET /api/papers
# ---------------------------------------------------------------------------

@router.get("/papers")
async def list_papers(page: int = 1, page_size: int = 20) -> dict:
    """List all papers in ChromaDB with optional pagination."""
    papers_raw, pdf_ids = await asyncio.gather(
        vector_store.list_papers(),
        pdf_storage.list_paper_ids(),
    )

    # Sort by paper_id for stable ordering
    papers_raw.sort(key=lambda p: p.get("paper_id", ""))

    total = len(papers_raw)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = papers_raw[start:end]

    papers = [
        _build_paper_response(p, has_pdf=p.get("paper_id", "") in pdf_ids)
        for p in page_items
    ]

    return {
        "data": {"papers": papers, "total": total, "page": page, "page_size": page_size},
        "error": None,
        "status": 200,
    }


# ---------------------------------------------------------------------------
# GET /api/papers/search  — search external databases via MCP (no storage)
# ---------------------------------------------------------------------------

@router.get("/papers/search")
async def search_external_papers(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(default=10, ge=1, le=50),
) -> dict:
    """Search Semantic Scholar + arXiv via the MCP server.

    Returns matching papers for preview. Nothing is stored until the user
    explicitly calls POST /api/papers/import.
    """
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    per_source_args = {"query": q, "max_results": 2}
    arxiv_papers, pubmed_papers = await asyncio.gather(
        _call_mcp_tool("search_arxiv", per_source_args),
        _call_mcp_tool("search_pubmed", per_source_args),
    )

    def _parse_year(published_date: str) -> str:
        if published_date and len(published_date) >= 4:
            candidate = published_date[:4]
            if candidate.isdigit():
                return candidate
        return str(published_date) if published_date else ""

    def _parse_authors(authors_raw) -> list[str]:
        if isinstance(authors_raw, list):
            return [str(a).strip() for a in authors_raw if str(a).strip()]
        if isinstance(authors_raw, str):
            return [a.strip() for a in authors_raw.split(";") if a.strip()]
        return []

    # Normalise to unified structure
    combined: list[dict] = []
    for paper in arxiv_papers + pubmed_papers:
        combined.append({
            "paper_id": (paper.get("paper_id") or "").strip(),
            "title": (paper.get("title") or "").strip(),
            "authors": _parse_authors(paper.get("authors", "")),
            "year": _parse_year(paper.get("published_date", "") or str(paper.get("year", ""))),
            "abstract": (paper.get("abstract") or "").strip(),
            "doi": (paper.get("doi") or "").strip(),
            "url": (paper.get("url") or paper.get("pdf_url") or "").strip(),
            "source": "external",
        })

    # Deduplicate by lowercased title and cap at 8
    seen: set[str] = set()
    deduped: list[dict] = []
    for paper in combined:
        if len(deduped) >= 8:
            break
        key = paper["title"].lower().strip()
        if key and key not in seen:
            seen.add(key)
            deduped.append(paper)

    return {
        "data": {"papers": deduped, "total": len(deduped)},
        "error": None,
        "status": 200,
    }


# ---------------------------------------------------------------------------
# POST /api/papers/import  — ingest selected external papers into ChromaDB
# ---------------------------------------------------------------------------

class ImportPapersRequest(BaseModel):
    papers: list[dict]


@router.post("/papers/import")
async def import_external_papers(body: ImportPapersRequest) -> dict:
    """Ingest a list of external papers (from search results) into ChromaDB.

    Only papers with a non-empty abstract are stored.
    Returns the count of papers imported and total chunks stored.
    """
    if not body.papers:
        raise HTTPException(status_code=400, detail="No papers provided")

    errors: list[str] = []

    async def _ingest_one(paper: dict) -> int:
        """Ingest a single paper; return chunk count or 0 on skip/error."""
        abstract = (paper.get("abstract") or "").strip()
        title = (paper.get("title") or "").strip()
        if not abstract:
            errors.append(f'"{title}": skipped (no abstract)')
            return 0

        authors_raw = paper.get("authors", [])
        authors_str = (
            ", ".join(authors_raw) if isinstance(authors_raw, list) else str(authors_raw)
        )

        paper_id = (paper.get("paper_id") or "").strip()
        if not paper_id:
            paper_id = _make_paper_id(title)

        metadata = {
            "paper_id": paper_id,
            "title": title,
            "authors": authors_str,
            "year": str(paper.get("year", "")),
            "source": "external",
            "doi": paper.get("doi", "") or "",
            "url": paper.get("url", "") or "",
            "abstract": abstract,
            "date_added": datetime.now(timezone.utc).isoformat(),
        }

        try:
            chunks = await ingest_paper(abstract, metadata)
            await _save_paper_to_sqlite(metadata, chunk_count=chunks)
            return chunks
        except Exception as exc:
            errors.append(f'"{title}": {exc}')
            return 0

    chunk_counts: list[int] = await asyncio.gather(*[_ingest_one(p) for p in body.papers])

    total_chunks = sum(chunk_counts)
    imported = sum(1 for c in chunk_counts if c > 0)

    return {
        "data": {
            "imported": imported,
            "chunks": total_chunks,
            "errors": errors,
        },
        "error": None,
        "status": 200,
    }


# ---------------------------------------------------------------------------
# POST /api/papers/save-external  — ingest a single external paper directly
# ---------------------------------------------------------------------------

@router.post("/papers/save-external")
async def save_external_paper(body: SaveExternalPaperRequest) -> dict:
    """Ingest a single external paper (e.g. from an external search result) into ChromaDB.

    Useful when the frontend wants to save a paper the professor has explicitly
    chosen, without going through the bulk import flow.

    Returns the number of chunks stored.
    """
    abstract = body.abstract.strip()
    if not abstract:
        raise HTTPException(status_code=400, detail="abstract is required and cannot be empty")

    title = body.title.strip()

    authors_str = ", ".join(body.authors) if body.authors else ""

    paper_id = body.paper_id.strip()
    if not paper_id:
        paper_id = _make_paper_id(title)

    metadata: dict = {
        "paper_id": paper_id,
        "title": title,
        "authors": authors_str,
        "year": str(body.year),
        "source": "external",
        "doi": body.doi or "",
        "url": body.url or "",
        "abstract": abstract,
        "date_added": datetime.now(timezone.utc).isoformat(),
    }

    try:
        chunks_stored = await ingest_paper(abstract, metadata)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}")

    await _save_paper_to_sqlite(metadata, chunk_count=chunks_stored)

    return {
        "data": {"chunks_stored": chunks_stored, "paper_id": paper_id},
        "error": None,
        "status": 200,
    }


# ---------------------------------------------------------------------------
# GET /api/papers/{paper_id}
# ---------------------------------------------------------------------------

@router.get("/papers/{paper_id}")
async def get_paper(paper_id: str) -> dict:
    """Fetch a single paper by paper_id from ChromaDB."""
    collection = vector_store.get_collection()
    results = collection.get(
        where={"paper_id": paper_id},
        include=["metadatas", "documents"],
    )
    metadatas = results.get("metadatas") or []
    if not metadatas:
        raise HTTPException(status_code=404, detail=f"Paper '{paper_id}' not found")

    meta = metadatas[0]

    # If abstract is missing from metadata, reconstruct from chunk documents
    if not meta.get("abstract"):
        documents = results.get("documents") or []
        if documents:
            meta["abstract"] = " ".join(documents)

    paper = _build_paper_response(meta, has_pdf=await pdf_storage.has_pdf(paper_id))
    return {"data": paper, "error": None, "status": 200}


# ---------------------------------------------------------------------------
# GET /api/papers/{paper_id}/pdf  — stream stored PDF back to the browser
# ---------------------------------------------------------------------------

@router.get("/papers/{paper_id}/pdf")
async def get_paper_pdf(paper_id: str) -> StreamingResponse:
    """Stream the original uploaded PDF file for the given paper_id.

    Returns the raw PDF bytes with ``Content-Type: application/pdf`` and
    ``Content-Disposition: inline`` so the browser opens it in a viewer tab.
    Raises 404 if no PDF was stored for this paper (e.g. URL-ingested papers).
    """
    result = await pdf_storage.get_pdf(paper_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No stored PDF found for paper '{paper_id}'",
        )

    content_bytes, filename = result

    # Sanitise the filename so it is safe for a Content-Disposition header
    safe_filename = re.sub(r'[^\w\-. ]', '_', filename) or f"{paper_id}.pdf"
    if not safe_filename.lower().endswith(".pdf"):
        safe_filename += ".pdf"

    def _iter():
        yield content_bytes

    return StreamingResponse(
        _iter(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{safe_filename}"',
            "Content-Length": str(len(content_bytes)),
        },
    )


# ---------------------------------------------------------------------------
# DELETE /api/papers/{paper_id}
# ---------------------------------------------------------------------------

@router.delete("/papers/{paper_id}")
async def delete_paper(paper_id: str) -> dict:
    """Delete a paper and all its chunks from ChromaDB, and remove its stored PDF."""
    deleted = await vector_store.delete_paper(paper_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Paper '{paper_id}' not found")

    # Remove the stored PDF file (non-fatal if it never had one)
    await pdf_storage.delete_pdf(paper_id)

    # Remove paper metadata from SQLite
    await sqlite_store.delete_paper_record(paper_id)

    # Refresh paper count in pipeline_stats
    try:
        total_papers = await vector_store.paper_count()
        stats = await sqlite_store.fetch_pipeline_stats()
        await sqlite_store.upsert_pipeline_stats(
            total_papers=total_papers,
            total_queries=stats.get("total_queries", 0),
            avg_processing_time=stats.get("avg_processing_time", 0.0),
        )
    except Exception as exc:
        logger.warning("delete_paper: upsert_pipeline_stats failed (non-fatal): %s", exc)

    # Evict cached answers that cite this paper so professors never see stale results
    try:
        from app.api.research import invalidate_cache_for_paper  # avoid circular import
        invalidate_cache_for_paper(paper_id)
    except Exception as exc:
        logger.warning("delete_paper: cache invalidation failed (non-fatal): %s", exc)

    return {
        "data": {"deleted": True, "paper_id": paper_id},
        "error": None,
        "status": 200,
    }


# ---------------------------------------------------------------------------
# GET /api/papers/check  — does this paper already exist in the library?
# ---------------------------------------------------------------------------

@router.get("/papers/check")
async def check_paper_exists(
    doi: str | None = Query(default=None),
    title: str | None = Query(default=None),
) -> dict:
    """Return whether a paper is already stored in ChromaDB.

    Matches by DOI first (exact), then by normalised title.  At least one of
    ``doi`` or ``title`` must be provided.
    """
    if not doi and not title:
        raise HTTPException(
            status_code=400, detail="Provide at least one of: doi, title"
        )

    collection = vector_store.get_chunks_collection()

    # 1. Try exact DOI match
    if doi:
        try:
            results = collection.get(where={"doi": doi.strip()}, limit=1, include=["metadatas"])
            if results.get("metadatas"):
                meta = results["metadatas"][0]
                return {
                    "data": {"exists": True, "paper_id": meta.get("paper_id")},
                    "error": None,
                    "status": 200,
                }
        except Exception:
            pass

    # 2. Fall back to normalised title match
    if title:
        normalised = title.strip().lower()
        try:
            results = collection.get(where={"title": title.strip()}, limit=1, include=["metadatas"])
            if results.get("metadatas"):
                meta = results["metadatas"][0]
                return {
                    "data": {"exists": True, "paper_id": meta.get("paper_id")},
                    "error": None,
                    "status": 200,
                }
        except Exception:
            pass

        # ChromaDB WHERE is case-sensitive; do a broader scan for a normalised match
        try:
            all_results = collection.get(limit=5000, include=["metadatas"])
            for meta in (all_results.get("metadatas") or []):
                stored_title = str(meta.get("title", "")).strip().lower()
                if stored_title == normalised:
                    return {
                        "data": {"exists": True, "paper_id": meta.get("paper_id")},
                        "error": None,
                        "status": 200,
                    }
        except Exception:
            pass

    return {"data": {"exists": False, "paper_id": None}, "error": None, "status": 200}


# ---------------------------------------------------------------------------
# POST /api/papers/ingest-citation  — save a cited paper into the local library
# ---------------------------------------------------------------------------

class IngestCitationRequest(BaseModel):
    title: str
    authors: list[str] = []
    year: int = 0
    doi: str | None = None
    url: str | None = None


async def _fetch_abstract_from_semantic_scholar(doi: str) -> tuple[str, str, str, str, str]:
    """Query Semantic Scholar for a paper's abstract by DOI.

    Returns (paper_id, title, authors_str, year_str, abstract).
    All strings are empty if the lookup fails.
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(
                f"https://api.semanticscholar.org/graph/v1/paper/{doi}",
                params={"fields": "paperId,title,authors,year,abstract"},
            )
            if resp.status_code == 200:
                data = resp.json()
                paper_id = data.get("paperId", "")
                title = data.get("title", "")
                authors = ", ".join(a.get("name", "") for a in data.get("authors", []))
                year = str(data.get("year", ""))
                abstract = data.get("abstract", "") or ""
                return paper_id, title, authors, year, abstract
        except Exception:
            pass
    return "", "", "", "", ""


async def _fetch_arxiv_abstract(arxiv_url: str) -> str:
    """Fetch the abstract text from an arXiv abstract page (open access)."""
    # Convert /pdf/ links to /abs/ so we get the HTML abstract page
    abs_url = re.sub(r"/pdf/", "/abs/", arxiv_url)
    abs_url = re.sub(r"\.pdf$", "", abs_url)
    async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
        try:
            resp = await client.get(abs_url, headers={"User-Agent": "research-assistant/1.0"})
            resp.raise_for_status()
            # Pull the abstract text out of the blockquote.abstract element
            match = re.search(
                r'<blockquote[^>]*class="[^"]*abstract[^"]*"[^>]*>(.*?)</blockquote>',
                resp.text,
                re.DOTALL | re.IGNORECASE,
            )
            if match:
                raw = match.group(1)
                # Strip inner tags and the "Abstract:" label
                text = re.sub(r"<[^>]+>", " ", raw)
                text = re.sub(r"^\s*abstract\s*[:\-]?\s*", "", text, flags=re.IGNORECASE)
                return " ".join(text.split())
        except Exception:
            pass
    return ""


@router.post("/papers/ingest-citation")
async def ingest_citation(body: IngestCitationRequest) -> dict:
    """Save an external cited paper into the local ChromaDB library.

    Strategy (no paywall hits):
    1. DOI present  → query Semantic Scholar for the abstract; ingest abstract text.
    2. arXiv URL    → fetch the open-access abstract page; ingest abstract text.
    3. Fallback     → build a searchable stub from title + authors + year.

    The function never tries to fetch a publisher DOI URL directly, which avoids
    the 403 / paywall errors that ``ingest_by_doi_or_url`` can hit.
    """
    doi = (body.doi or "").strip()
    url = (body.url or "").strip()

    paper_id = ""
    title = body.title
    authors_str = ", ".join(body.authors)
    year_str = str(body.year)
    abstract = ""

    # 1. Try Semantic Scholar lookup by DOI
    if doi:
        ss_id, ss_title, ss_authors, ss_year, ss_abstract = (
            await _fetch_abstract_from_semantic_scholar(doi)
        )
        if ss_abstract:
            paper_id = ss_id or ""
            title = ss_title or title
            authors_str = ss_authors or authors_str
            year_str = ss_year or year_str
            abstract = ss_abstract

    # 2. Try arXiv open-access abstract if we still have no abstract
    if not abstract and url and "arxiv.org" in url:
        abstract = await _fetch_arxiv_abstract(url)

    # 3. Build a searchable stub from the citation metadata as last resort
    if not abstract:
        abstract = f"{title}. {authors_str} ({year_str})."

    # Derive a stable paper_id slug if Semantic Scholar didn't give us one
    if not paper_id:
        slug = re.sub(r"[^a-z0-9]+", "_", title.lower())[:40]
        paper_id = f"cit_{slug}"

    metadata: dict = {
        "paper_id": paper_id,
        "title": title,
        "authors": authors_str,
        "year": year_str,
        "source": "external",
        "doi": doi,
        "url": url,
        "abstract": abstract,
        "date_added": datetime.now(timezone.utc).isoformat(),
    }

    try:
        chunks_stored = await ingest_paper(abstract, metadata)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}")

    await _save_paper_to_sqlite(metadata, chunk_count=chunks_stored)

    return {
        "data": {"paper_id": paper_id, "chunks_stored": chunks_stored},
        "error": None,
        "status": 200,
    }


# ---------------------------------------------------------------------------
# GET /api/stats
# ---------------------------------------------------------------------------

def _get_db_size_mb() -> float:
    """Calculate the total size of the ChromaDB directory in megabytes."""
    db_path = Path(settings.chroma_db_path)
    if not db_path.exists():
        return 0.0
    total = sum(f.stat().st_size for f in db_path.rglob("*") if f.is_file())
    return round(total / (1024 * 1024), 2)


@router.get("/stats")
async def get_stats() -> dict:
    """Return DB statistics: paper count, DB size, connection status, and pipeline stats."""
    paper_count = 0
    is_connected = False
    try:
        paper_count = await vector_store.paper_count()
        is_connected = True
    except Exception:
        pass

    # No ingested papers → report 0 MB so the UI does not show Chroma's empty
    # on-disk footprint (sqlite, etc.) as if it were library data.
    db_size_mb = 0.0 if paper_count == 0 else _get_db_size_mb()

    pipeline_stats: dict = {}
    try:
        pipeline_stats = await sqlite_store.fetch_pipeline_stats()
    except Exception:
        pass

    return {
        "data": {
            "paperCount": paper_count,
            "dbSizeMB": db_size_mb,
            "isConnected": is_connected,
            "totalQueries": pipeline_stats.get("total_queries", 0),
            "avgProcessingTime": pipeline_stats.get("avg_processing_time", 0.0),
            "statsLastUpdated": pipeline_stats.get("last_updated", ""),
        },
        "error": None,
        "status": 200,
    }
