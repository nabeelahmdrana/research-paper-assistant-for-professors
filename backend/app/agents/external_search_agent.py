"""External Search Agent — Phase 5.

Fetches papers from multiple academic databases via the paper-search-mcp
MCP server (openags/paper-search-mcp from mcpmarket.com).

Databases searched concurrently:
  - arXiv         (open-access preprints, CS / physics / math / …)
  - PubMed        (biomedical & life sciences, NLM)
  - bioRxiv       (biology preprints)
  - medRxiv       (medical preprints)

Falls back to empty results per-source if the MCP server is unavailable
or a source times out, so the pipeline always completes.
"""

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Wrapper script that starts paper_search_mcp as a proper MCP server.
# Located at: <project-root>/mcp-server/paper_search_wrapper.py
_WRAPPER_PATH = str(
    Path(__file__).resolve().parents[3] / "mcp-server" / "paper_search_wrapper.py"
)


def _parse_year(published_date: str) -> str:
    """Extract 4-digit year from an ISO datetime string like '2024-03-15T…'."""
    if published_date and len(published_date) >= 4:
        candidate = published_date[:4]
        if candidate.isdigit():
            return candidate
    return ""


def _parse_authors(authors_raw) -> list[str]:
    """Normalise authors field.

    paper_search_mcp returns authors as a semicolon-separated string in
    to_dict().  We convert back to a list for consistency with the rest of
    the pipeline.
    """
    if isinstance(authors_raw, list):
        return [str(a).strip() for a in authors_raw if str(a).strip()]
    if isinstance(authors_raw, str):
        return [a.strip() for a in authors_raw.split(";") if a.strip()]
    return []


async def _call_mcp_tool(tool_name: str, args: dict) -> list[dict]:
    """Spawn the paper-search-mcp server and call one tool.

    Uses sys.executable so the server runs inside the same venv as the
    backend, ensuring all paper_search_mcp dependencies are available.
    Returns [] on any connection or parse error so the pipeline degrades
    gracefully instead of raising.
    """
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[_WRAPPER_PATH],
    )
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, args)
                if not result.content:
                    return []

                # FastMCP v3.2.x returns each result item as a separate
                # TextContent block; older mcp servers return one block with
                # a JSON array.  Handle both formats.
                papers: list[dict] = []
                for block in result.content:
                    raw = getattr(block, "text", None)
                    if not raw:
                        continue
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        papers.extend(parsed)
                    elif isinstance(parsed, dict):
                        papers.append(parsed)
                return papers
    except Exception:
        pass
    return []


def _normalise(paper: dict, default_source: str) -> dict:
    """Map a paper_search_mcp to_dict() record to our pipeline's format."""
    return {
        "paper_id": (paper.get("paper_id") or "").strip(),
        "title": (paper.get("title") or "").strip(),
        "authors": _parse_authors(paper.get("authors", "")),
        "year": _parse_year(paper.get("published_date", "")),
        "abstract": (paper.get("abstract") or "").strip(),
        "doi": (paper.get("doi") or "").strip(),
        "url": (paper.get("url") or paper.get("pdf_url") or "").strip(),
        "source": "external",
        "_db": paper.get("source") or default_source,  # internal tracking only
    }


async def external_search_agent(state: dict) -> dict:
    """Search arXiv, PubMed, bioRxiv, and medRxiv via the MCP server.

    All four sources are queried concurrently.  Results are combined,
    deduplicated by lower-cased title, and limited to papers that have
    an abstract (needed for ingestion).

    Populates:
        state["external_papers"]  – normalised list of paper dicts
        state["sources_origin"]   – list of titles of fetched papers
    """
    question: str = state["question"]
    # Fetch max 2 per source → up to 8 raw candidates after dedup
    query_args = {"query": question, "max_results": 2}

    # Run all four database searches concurrently
    arxiv_papers, pubmed_papers, biorxiv_papers, medrxiv_papers = await asyncio.gather(
        _call_mcp_tool("search_arxiv", query_args),
        _call_mcp_tool("search_pubmed", query_args),
        _call_mcp_tool("search_biorxiv", query_args),
        _call_mcp_tool("search_medrxiv", query_args),
    )

    # Normalise all results
    combined: list[dict] = []
    for paper in arxiv_papers:
        combined.append(_normalise(paper, "arxiv"))
    for paper in pubmed_papers:
        combined.append(_normalise(paper, "pubmed"))
    for paper in biorxiv_papers:
        combined.append(_normalise(paper, "biorxiv"))
    for paper in medrxiv_papers:
        combined.append(_normalise(paper, "medrxiv"))

    # Deduplicate by lower-cased title; skip papers without abstract; cap at 8
    seen_titles: set[str] = set()
    deduped: list[dict] = []
    for paper in combined:
        if len(deduped) >= 8:
            break
        key = paper["title"].lower().strip()
        if not key or key in seen_titles:
            continue
        if not paper["abstract"]:
            continue
        seen_titles.add(key)
        deduped.append(paper)

    sources_origin = [p["title"] for p in deduped]

    return {
        **state,
        "external_papers": deduped,
        "sources_origin": sources_origin,
    }
