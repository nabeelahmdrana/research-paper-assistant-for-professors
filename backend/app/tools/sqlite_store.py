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
    id                      TEXT PRIMARY KEY,
    question                TEXT NOT NULL,
    summary                 TEXT,
    agreements              TEXT,
    contradictions          TEXT,
    gaps                    TEXT,
    citations               TEXT,
    created_at              TEXT NOT NULL,
    confidence_score        REAL    DEFAULT 0.0,
    cache_hit               INTEGER DEFAULT 0,
    external_papers_fetched INTEGER DEFAULT 0,
    new_papers_count        INTEGER DEFAULT 0
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
    last_updated         TEXT    NOT NULL,
    cache_hits           INTEGER DEFAULT 0,
    external_queries     INTEGER DEFAULT 0,
    confidence_sum       REAL    DEFAULT 0.0
);
"""


# ---------------------------------------------------------------------------
# Internal sync helpers
# ---------------------------------------------------------------------------

def _get_conn() -> sqlite3.Connection:
    return sqlite3.connect(str(_DB_PATH), check_same_thread=False)


def _migrate_tables_sync(conn: sqlite3.Connection) -> None:
    """Add new columns to existing tables when upgrading an existing database."""
    # recent_queries — new columns added in v1.0.3
    new_rq_cols = [
        ("confidence_score",        "REAL    DEFAULT 0.0"),
        ("cache_hit",               "INTEGER DEFAULT 0"),
        ("external_papers_fetched", "INTEGER DEFAULT 0"),
        ("new_papers_count",        "INTEGER DEFAULT 0"),
    ]
    existing_cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(recent_queries)").fetchall()
    }
    for col_name, col_def in new_rq_cols:
        if col_name not in existing_cols:
            conn.execute(
                f"ALTER TABLE recent_queries ADD COLUMN {col_name} {col_def}"
            )

    # pipeline_stats — new columns added in v1.0.3
    new_ps_cols = [
        ("cache_hits",       "INTEGER DEFAULT 0"),
        ("external_queries", "INTEGER DEFAULT 0"),
        ("confidence_sum",   "REAL    DEFAULT 0.0"),
    ]
    existing_ps_cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(pipeline_stats)").fetchall()
    }
    for col_name, col_def in new_ps_cols:
        if col_name not in existing_ps_cols:
            conn.execute(
                f"ALTER TABLE pipeline_stats ADD COLUMN {col_name} {col_def}"
            )


def _init_db_sync() -> None:
    conn = _get_conn()
    try:
        conn.execute(_CREATE_RECENT_QUERIES_SQL)
        conn.execute(_CREATE_PAPERS_SQL)
        conn.execute(_CREATE_PIPELINE_STATS_SQL)
        # Migrate existing tables to add new columns (no-op for fresh DBs)
        _migrate_tables_sync(conn)
        # Seed a single stats row so fetch always returns data
        conn.execute(
            """
            INSERT OR IGNORE INTO pipeline_stats
                (id, total_papers, total_queries, avg_processing_time, last_updated,
                 cache_hits, external_queries, confidence_sum)
            VALUES (1, 0, 0, 0.0, ?, 0, 0, 0.0)
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
    confidence_score: float = 0.0,
    cache_hit: bool = False,
    external_papers_fetched: bool = False,
    new_papers_count: int = 0,
) -> None:
    conn = _get_conn()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO recent_queries
                (id, question, summary, agreements, contradictions, gaps, citations,
                 created_at, confidence_score, cache_hit, external_papers_fetched, new_papers_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                confidence_score,
                1 if cache_hit else 0,
                1 if external_papers_fetched else 0,
                new_papers_count,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _row_to_result(row: tuple) -> dict:
    """Convert a recent_queries DB row to the API-compatible result dict."""
    def _parse(val: str | None) -> list:
        if not val:
            return []
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return []

    return {
        "id": row[0],
        "question": row[1],
        "summary": row[2] or "",
        "agreements": _parse(row[3]),
        "contradictions": _parse(row[4]),
        "researchGaps": _parse(row[5]),   # "gaps" column → camelCase key
        "citations": _parse(row[6]),
        "createdAt": row[7],              # "created_at" column → camelCase key
        "confidenceScore": row[8] or 0.0,
        "cacheHit": bool(row[9]),
        "externalPapersFetched": bool(row[10]),
        "newPapersCount": row[11] or 0,
    }


def _fetch_recent_queries_sync(limit: int) -> list[dict]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            """
            SELECT id, question, summary, agreements, contradictions, gaps, citations,
                   created_at, confidence_score, cache_hit, external_papers_fetched, new_papers_count
            FROM recent_queries
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        conn.close()

    return [_row_to_result(row) for row in rows]


def _fetch_all_queries_sync() -> list[dict]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            """
            SELECT id, question, summary, agreements, contradictions, gaps, citations,
                   created_at, confidence_score, cache_hit, external_papers_fetched, new_papers_count
            FROM recent_queries
            ORDER BY created_at DESC
            """
        ).fetchall()
    finally:
        conn.close()

    return [_row_to_result(row) for row in rows]


def _fetch_query_by_id_sync(query_id: str) -> dict | None:
    conn = _get_conn()
    try:
        row = conn.execute(
            """
            SELECT id, question, summary, agreements, contradictions, gaps, citations,
                   created_at, confidence_score, cache_hit, external_papers_fetched, new_papers_count
            FROM recent_queries
            WHERE id = ?
            """,
            (query_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None
    return _row_to_result(row)


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
    cache_hits: int = 0,
    external_queries: int = 0,
    confidence_sum: float = 0.0,
) -> None:
    conn = _get_conn()
    try:
        # Only update total_papers if the caller passes a non-zero value, to
        # avoid overwriting the papers count when called from the research module.
        if total_papers > 0:
            conn.execute(
                """
                INSERT OR REPLACE INTO pipeline_stats
                    (id, total_papers, total_queries, avg_processing_time, last_updated,
                     cache_hits, external_queries, confidence_sum)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    total_papers,
                    total_queries,
                    avg_processing_time,
                    datetime.now(timezone.utc).isoformat(),
                    cache_hits,
                    external_queries,
                    confidence_sum,
                ),
            )
        else:
            # Preserve the existing total_papers value
            conn.execute(
                """
                UPDATE pipeline_stats
                SET total_queries = ?,
                    avg_processing_time = ?,
                    last_updated = ?,
                    cache_hits = ?,
                    external_queries = ?,
                    confidence_sum = ?
                WHERE id = 1
                """,
                (
                    total_queries,
                    avg_processing_time,
                    datetime.now(timezone.utc).isoformat(),
                    cache_hits,
                    external_queries,
                    confidence_sum,
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
            SELECT total_papers, total_queries, avg_processing_time, last_updated,
                   cache_hits, external_queries, confidence_sum
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
            "cache_hits": 0,
            "external_queries": 0,
            "confidence_sum": 0.0,
        }
    return {
        "total_papers": row[0] or 0,
        "total_queries": row[1] or 0,
        "avg_processing_time": row[2] or 0.0,
        "last_updated": row[3] or "",
        "cache_hits": row[4] or 0,
        "external_queries": row[5] or 0,
        "confidence_sum": row[6] or 0.0,
    }


def load_stats_sync() -> dict[str, float]:
    """Load pipeline statistics from SQLite synchronously.

    Returns a dict matching ``_STATS_DEFAULTS`` in research.py so it can be
    called at module-import time (before the async event loop starts).
    Returns defaults if the database does not yet exist.
    """
    if not _DB_PATH.exists():
        return {
            "total_queries": 0.0,
            "cache_hits": 0.0,
            "external_queries": 0.0,
            "confidence_sum": 0.0,
        }
    try:
        row = _fetch_pipeline_stats_sync()
        return {
            "total_queries": float(row["total_queries"]),
            "cache_hits": float(row["cache_hits"]),
            "external_queries": float(row["external_queries"]),
            "confidence_sum": float(row["confidence_sum"]),
        }
    except Exception:
        return {
            "total_queries": 0.0,
            "cache_hits": 0.0,
            "external_queries": 0.0,
            "confidence_sum": 0.0,
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
    confidence_score: float = 0.0,
    cache_hit: bool = False,
    external_papers_fetched: bool = False,
    new_papers_count: int = 0,
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
        confidence_score,
        cache_hit,
        external_papers_fetched,
        new_papers_count,
    )


async def fetch_recent_queries(limit: int = 20) -> list[dict]:
    """Return up to *limit* most-recent query results, newest first."""
    return await asyncio.to_thread(_fetch_recent_queries_sync, limit)


async def fetch_all_queries() -> list[dict]:
    """Return all query results ordered by most recent first."""
    return await asyncio.to_thread(_fetch_all_queries_sync)


async def fetch_query_by_id(query_id: str) -> dict | None:
    """Return a single query result by ID, or None if not found."""
    return await asyncio.to_thread(_fetch_query_by_id_sync, query_id)


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
    cache_hits: int = 0,
    external_queries: int = 0,
    confidence_sum: float = 0.0,
) -> None:
    """Overwrite the single pipeline_stats row with current counts."""
    await asyncio.to_thread(
        _upsert_pipeline_stats_sync,
        total_papers,
        total_queries,
        avg_processing_time,
        cache_hits,
        external_queries,
        confidence_sum,
    )


async def fetch_pipeline_stats() -> dict:
    """Return pipeline stats dict with all tracked counters."""
    return await asyncio.to_thread(_fetch_pipeline_stats_sync)
