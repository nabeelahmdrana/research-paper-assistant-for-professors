"""SQLite-backed storage for original PDF files.

PDFs are stored as BLOB data in a local SQLite database so uploaded papers
can be retrieved and served back to users at any time.

The DB is created automatically on first use.  The default path is
``./pdf_store.db`` (relative to the working directory of the FastAPI process).
"""

import asyncio
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# SQLite database file path — sits alongside chroma_db/
_DB_PATH = Path("./pdf_store.db")

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS pdf_files (
    paper_id   TEXT PRIMARY KEY,
    filename   TEXT NOT NULL,
    content    BLOB NOT NULL,
    file_size  INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
"""


# ---------------------------------------------------------------------------
# Internal sync helpers (run in a thread-pool executor to avoid blocking)
# ---------------------------------------------------------------------------

def _init_db_sync() -> None:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    try:
        conn.execute(_CREATE_TABLE_SQL)
        conn.commit()
    finally:
        conn.close()


def _store_pdf_sync(paper_id: str, filename: str, content: bytes) -> None:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    try:
        conn.execute(
            """
            INSERT INTO pdf_files (paper_id, filename, content, file_size, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(paper_id) DO UPDATE SET
                filename   = excluded.filename,
                content    = excluded.content,
                file_size  = excluded.file_size,
                created_at = excluded.created_at
            """,
            (paper_id, filename, content, len(content), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def _get_pdf_sync(paper_id: str) -> tuple[bytes, str] | None:
    """Return (content_bytes, filename) or None if not found."""
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    try:
        row = conn.execute(
            "SELECT content, filename FROM pdf_files WHERE paper_id = ?",
            (paper_id,),
        ).fetchone()
        return (bytes(row[0]), row[1]) if row else None
    finally:
        conn.close()


def _delete_pdf_sync(paper_id: str) -> None:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    try:
        conn.execute("DELETE FROM pdf_files WHERE paper_id = ?", (paper_id,))
        conn.commit()
    finally:
        conn.close()


def _list_paper_ids_sync() -> set[str]:
    """Return the set of paper_ids that have a stored PDF."""
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    try:
        rows = conn.execute("SELECT paper_id FROM pdf_files").fetchall()
        return {row[0] for row in rows}
    finally:
        conn.close()


def _has_pdf_sync(paper_id: str) -> bool:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    try:
        row = conn.execute(
            "SELECT 1 FROM pdf_files WHERE paper_id = ? LIMIT 1", (paper_id,)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Public async API
# ---------------------------------------------------------------------------

async def init_db() -> None:
    """Create the pdf_files table if it does not exist yet."""
    await asyncio.to_thread(_init_db_sync)


async def store_pdf(paper_id: str, filename: str, content: bytes) -> None:
    """Persist a PDF file. Overwrites any existing entry for the same paper_id."""
    await asyncio.to_thread(_store_pdf_sync, paper_id, filename, content)


async def get_pdf(paper_id: str) -> tuple[bytes, str] | None:
    """Retrieve a PDF.

    Returns:
        (content_bytes, original_filename) or None if not stored.
    """
    return await asyncio.to_thread(_get_pdf_sync, paper_id)


async def delete_pdf(paper_id: str) -> None:
    """Remove a stored PDF (no-op if it does not exist)."""
    await asyncio.to_thread(_delete_pdf_sync, paper_id)


async def list_paper_ids() -> set[str]:
    """Return the set of paper_ids that have an associated PDF in the store."""
    return await asyncio.to_thread(_list_paper_ids_sync)


async def has_pdf(paper_id: str) -> bool:
    """Return True if a PDF is stored for the given paper_id."""
    return await asyncio.to_thread(_has_pdf_sync, paper_id)
