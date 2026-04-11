import os
import tempfile
from datetime import datetime, timezone

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.config import settings
from app.ingestion.pdf_ingester import ingest_pdf_file
from app.ingestion.url_ingester import ingest_by_doi_or_url
from app.tools import vector_store

router = APIRouter()


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

@router.get("/stats")
async def get_stats() -> dict:
    """Return DB statistics: paper count, connection status."""
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
            "dbSizeMB": 0,
            "isConnected": is_connected,
        },
        "error": None,
        "status": 200,
    }
