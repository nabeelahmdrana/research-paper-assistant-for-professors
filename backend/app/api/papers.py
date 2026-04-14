import asyncio
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from app.agents.external_search_agent import _call_mcp_tool
from app.config import settings
from app.ingestion.pdf_ingester import ingest_pdf_file
from app.ingestion.pipeline import ingest_paper
from app.ingestion.url_ingester import ingest_by_doi_or_url
from app.models.schemas import SaveExternalPaperRequest
from app.tools import vector_store

router = APIRouter()


def _make_paper_id(title: str) -> str:
    """Derive a stable paper_id slug from a title when no API id is available."""
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower())[:40]
    return f"ext_{slug}"


def _build_paper_response(raw: dict) -> dict:
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
    }


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
            uploaded.append(_build_paper_response(result))
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
    papers_raw = await vector_store.list_papers()

    # Sort by paper_id for stable ordering
    papers_raw.sort(key=lambda p: p.get("paper_id", ""))

    total = len(papers_raw)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = papers_raw[start:end]

    papers = [_build_paper_response(p) for p in page_items]

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

    ss_papers, arxiv_papers = await asyncio.gather(
        _call_mcp_tool("search_papers", {"query": q, "limit": limit}),
        _call_mcp_tool("search_arxiv_papers", {"query": q, "limit": limit}),
    )

    # Normalise to unified structure
    combined: list[dict] = []
    for paper in ss_papers:
        combined.append({
            "paper_id": paper.get("paperId") or "",
            "title": paper.get("title", ""),
            "authors": paper.get("authors", []),
            "year": paper.get("year", ""),
            "abstract": paper.get("abstract", ""),
            "doi": paper.get("doi", ""),
            "url": paper.get("url", ""),
            "source": "external",
        })
    for paper in arxiv_papers:
        combined.append({
            "paper_id": paper.get("arxiv_id") or "",
            "title": paper.get("title", ""),
            "authors": paper.get("authors", []),
            "year": paper.get("year", ""),
            "abstract": paper.get("abstract", ""),
            "doi": paper.get("doi", ""),
            "url": paper.get("url", ""),
            "source": "external",
        })

    # Deduplicate by lowercased title
    seen: set[str] = set()
    deduped: list[dict] = []
    for paper in combined:
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

    imported = 0
    total_chunks = 0
    errors: list[str] = []

    for paper in body.papers:
        abstract = (paper.get("abstract") or "").strip()
        title = (paper.get("title") or "").strip()
        if not abstract:
            errors.append(f'"{title}": skipped (no abstract)')
            continue

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
            "date_added": datetime.now(timezone.utc).isoformat(),
        }

        try:
            chunks = await ingest_paper(abstract, metadata)
            total_chunks += chunks
            imported += 1
        except Exception as exc:
            errors.append(f'"{title}": {exc}')

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
        "date_added": datetime.now(timezone.utc).isoformat(),
    }

    try:
        chunks_stored = await ingest_paper(abstract, metadata)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}")

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
    results = collection.get(where={"paper_id": paper_id})
    metadatas = results.get("metadatas") or []
    if not metadatas:
        raise HTTPException(status_code=404, detail=f"Paper '{paper_id}' not found")

    paper = _build_paper_response(metadatas[0])
    return {"data": paper, "error": None, "status": 200}


# ---------------------------------------------------------------------------
# DELETE /api/papers/{paper_id}
# ---------------------------------------------------------------------------

@router.delete("/papers/{paper_id}")
async def delete_paper(paper_id: str) -> dict:
    """Delete a paper and all its chunks from ChromaDB."""
    deleted = await vector_store.delete_paper(paper_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Paper '{paper_id}' not found")

    return {
        "data": {"deleted": True, "paper_id": paper_id},
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
    """Return DB statistics: paper count, DB size, connection status."""
    paper_count = 0
    is_connected = False
    try:
        paper_count = await vector_store.paper_count()
        is_connected = True
    except Exception:
        pass

    return {
        "data": {
            "paperCount": paper_count,
            "dbSizeMB": _get_db_size_mb(),
            "isConnected": is_connected,
        },
        "error": None,
        "status": 200,
    }
