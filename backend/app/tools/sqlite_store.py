"""SQLite-backed store for recent queries, papers, and pipeline stats.

All three tables live in the same ``./pdf_store.db`` file that ``pdf_storage``
already manages.  Tables are created automatically on first use via
``init_sqlite_store()``.

The public API mirrors the pattern used in ``pdf_storage``: every public
function is ``async`` and delegates to a private sync helper that runs in a
``asyncio.to_thread`` pool so the FastAPI event loop is never blocked.

JSON columns (agreements, contradictions, gaps, citations, authors) are stored
as TEXT and serialised/deserialised transparently by the save/fetch helpers.
"""

import asyncio
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_DB_PATH = Path("./pdf_store.db")

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

_CREATE_RECENT_QUERIES_SQL = """
CREATE TABLE IF NOT EXISTS recent_queries (
    id         TEXT PRIMARY KEY,
    question   TEXT NOT NULL,
    summary    TEXT,
    agreements TEXT,
    contradictions TEXT,
    gaps       TEXT,
    citations  TEXT,
    created_at TEXT NOT NULL
);
"""

_CREATE_PAPERS_SQL = """
CREATE TABLE IF NOT EXISTS papers (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    authors     TEXT,
    abstract    TEXT,
    source      TEXT,
    file_name   TEXT,
    url         TEXT,
    doi         TEXT,
    chunk_count INTEGER DEFAULT 0,
    created_at  TEXT NOT NULL
);
"""

_CREATE_PIPELINE_STATS_SQL = """
CREATE TABLE IF NOT EXISTS pipeline_stats (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    total_papers         INTEGER DEFAULT 0,
    total_queries        INTEGER DEFAULT 0,
    avg_processing_time  REAL    DEFAULT 0.0,
    last_updated         TEXT    NOT NULL
);
"""


# ---------------------------------------------------------------------------
# Internal sync helpers
# ---------------------------------------------------------------------------

def _get_conn() -> sqlite3.Connection:
    return sqlite3.connect(str(_DB_PATH), check_same_thread=False)


def _init_db_sync() -> None:
    conn = _get_conn()
    try:
        conn.execute(_CREATE_RECENT_QUERIES_SQL)
        conn.execute(_CREATE_PAPERS_SQL)
        conn.execute(_CREATE_PIPELINE_STATS_SQL)
        # Seed a single stats row so fetch always returns data
        conn.execute(
            """
            INSERT OR IGNORE INTO pipeline_stats
                (id, total_papers, total_queries, avg_processing_time, last_updated)
            VALUES (1, 0, 0, 0.0, ?)
            """,
            (datetime.now(timezone.utc).isoformat(),),
        )
        conn.commit()
    finally:
        conn.close()


# ---- recent_queries --------------------------------------------------------

def _save_query_sync(
    query_id: str,
    question: str,
    summary: str,
    agreements: list[Any],
    contradictions: list[Any],
    gaps: list[Any],
    citations: list[Any],
    created_at: str,
) -> None:
    conn = _get_conn()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO recent_queries
                (id, question, summary, agreements, contradictions, gaps, citations, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                query_id,
                question,
                summary,
                json.dumps(agreements),
                json.dumps(contradictions),
                json.dumps(gaps),
                json.dumps(citations),
                created_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _fetch_recent_queries_sync(limit: int) -> list[dict]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            """
            SELECT id, question, summary, agreements, contradictions, gaps, citations, created_at
            FROM recent_queries
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        conn.close()

    def _parse(val: str | None) -> list:
        if not val:
            return []
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return []

    results: list[dict] = []
    for row in rows:
        results.append(
            {
                "id": row[0],
                "question": row[1],
                "summary": row[2] or "",
                "agreements": _parse(row[3]),
                "contradictions": _parse(row[4]),
                "gaps": _parse(row[5]),
                "citations": _parse(row[6]),
                "created_at": row[7],
            }
        )
    return results


# ---- papers ----------------------------------------------------------------

def _save_paper_sync(
    paper_id: str,
    title: str,
    authors: list[str],
    abstract: str,
    source: str,
    file_name: str | None,
    url: str | None,
    doi: str | None,
    chunk_count: int,
    created_at: str,
) -> None:
    conn = _get_conn()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO papers
                (id, title, authors, abstract, source, file_name, url, doi, chunk_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                paper_id,
                title,
                json.dumps(authors),
                abstract,
                source,
                file_name or "",
                url or "",
                doi or "",
                chunk_count,
                created_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _fetch_recent_papers_sync(limit: int) -> list[dict]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            """
            SELECT id, title, authors, abstract, source, file_name, url, doi, chunk_count, created_at
            FROM papers
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        conn.close()

    def _parse_authors(val: str | None) -> list[str]:
        if not val:
            return []
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return [str(a) for a in parsed]
            return [str(parsed)]
        except (json.JSONDecodeError, TypeError):
            return []

    results: list[dict] = []
    for row in rows:
        results.append(
            {
                "id": row[0],
                "title": row[1],
                "authors": _parse_authors(row[2]),
                "abstract": row[3] or "",
                "source": row[4] or "",
                "file_name": row[5] or "",
                "url": row[6] or "",
                "doi": row[7] or "",
                "chunk_count": row[8] or 0,
                "created_at": row[9],
            }
        )
    return results


def _delete_paper_record_sync(paper_id: str) -> None:
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM papers WHERE id = ?", (paper_id,))
        conn.commit()
    finally:
        conn.close()


# ---- pipeline_stats --------------------------------------------------------

def _upsert_pipeline_stats_sync(
    total_papers: int,
    total_queries: int,
    avg_processing_time: float,
) -> None:
    conn = _get_conn()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO pipeline_stats
                (id, total_papers, total_queries, avg_processing_time, last_updated)
            VALUES (1, ?, ?, ?, ?)
            """,
            (
                total_papers,
                total_queries,
                avg_processing_time,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _fetch_pipeline_stats_sync() -> dict:
    conn = _get_conn()
    try:
        row = conn.execute(
            """
            SELECT total_papers, total_queries, avg_processing_time, last_updated
            FROM pipeline_stats
            WHERE id = 1
            """
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return {
            "total_papers": 0,
            "total_queries": 0,
            "avg_processing_time": 0.0,
            "last_updated": "",
        }
    return {
        "total_papers": row[0] or 0,
        "total_queries": row[1] or 0,
        "avg_processing_time": row[2] or 0.0,
        "last_updated": row[3] or "",
    }


# ---------------------------------------------------------------------------
# Public async API
# ---------------------------------------------------------------------------

async def init_sqlite_store() -> None:
    """Create all tables and seed the pipeline_stats row if needed."""
    await asyncio.to_thread(_init_db_sync)


# ---- recent_queries --------------------------------------------------------

async def save_query(
    query_id: str,
    question: str,
    summary: str,
    agreements: list[Any],
    contradictions: list[Any],
    gaps: list[Any],
    citations: list[Any],
    created_at: str,
) -> None:
    """Persist a completed research query result to SQLite."""
    await asyncio.to_thread(
        _save_query_sync,
        query_id,
        question,
        summary,
        agreements,
        contradictions,
        gaps,
        citations,
        created_at,
    )


async def fetch_recent_queries(limit: int = 20) -> list[dict]:
    """Return up to *limit* most-recent query results, newest first."""
    return await asyncio.to_thread(_fetch_recent_queries_sync, limit)


# ---- papers ----------------------------------------------------------------

async def save_paper(
    paper_id: str,
    title: str,
    authors: list[str],
    abstract: str,
    source: str,
    file_name: str | None,
    url: str | None,
    doi: str | None,
    chunk_count: int,
    created_at: str,
) -> None:
    """Persist paper metadata to SQLite (upsert by id)."""
    await asyncio.to_thread(
        _save_paper_sync,
        paper_id,
        title,
        authors,
        abstract,
        source,
        file_name,
        url,
        doi,
        chunk_count,
        created_at,
    )


async def fetch_recent_papers(limit: int = 20) -> list[dict]:
    """Return up to *limit* most-recently added papers, newest first."""
    return await asyncio.to_thread(_fetch_recent_papers_sync, limit)


async def delete_paper_record(paper_id: str) -> None:
    """Remove a paper metadata row from SQLite (no-op if not present)."""
    await asyncio.to_thread(_delete_paper_record_sync, paper_id)


# ---- pipeline_stats --------------------------------------------------------

async def upsert_pipeline_stats(
    total_papers: int,
    total_queries: int,
    avg_processing_time: float,
) -> None:
    """Overwrite the single pipeline_stats row with current counts."""
    await asyncio.to_thread(
        _upsert_pipeline_stats_sync,
        total_papers,
        total_queries,
        avg_processing_time,
    )


async def fetch_pipeline_stats() -> dict:
    """Return pipeline stats dict with keys total_papers, total_queries, avg_processing_time, last_updated."""
    return await asyncio.to_thread(_fetch_pipeline_stats_sync)
