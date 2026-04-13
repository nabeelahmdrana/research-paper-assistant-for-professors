"""External Search Agent — Phase 5.

Fetches papers from Semantic Scholar and arXiv via the local MCP server
when local DB is insufficient. Falls back to empty results if the MCP
server is unavailable.
"""

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Resolve the MCP server path relative to this file:
# backend/app/agents/ → backend/app/ → backend/ → project-root/ → mcp-server/
_MCP_SERVER_PATH = str(
    Path(__file__).resolve().parents[3] / "mcp-server" / "server.py"
)


async def _call_mcp_tool(tool_name: str, args: dict) -> list[dict]:
    """Spawn the local MCP server and call one of its tools.

    Uses sys.executable so the MCP server runs in the same venv as the
    backend, ensuring all dependencies are available.
    Returns an empty list on any connection or parse error so the pipeline
    degrades gracefully instead of raising.
    """
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[_MCP_SERVER_PATH],
    )
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, args)
                if result.content:
                    return json.loads(result.content[0].text)
    except Exception:
        return []
    return []


async def external_search_agent(state: dict) -> dict:
    """Search Semantic Scholar and arXiv via the MCP server.

    Results from both sources are combined and deduplicated by title
    (case-insensitive).

    Populates:
        state["external_papers"]  – list of paper dicts ready for ingestion
        state["sources_origin"]   – list of titles of fetched papers
    """
    question: str = state["question"]

    # Call both MCP tools concurrently
    ss_papers, arxiv_papers = await asyncio.gather(
        _call_mcp_tool("search_papers", {"query": question, "limit": 10}),
        _call_mcp_tool("search_arxiv_papers", {"query": question, "limit": 10}),
    )

    # Normalise to a common structure
    combined: list[dict] = []

    for paper in ss_papers:
        combined.append(
            {
                "paper_id": paper.get("paperId") or "",
                "title": paper.get("title", ""),
                "authors": paper.get("authors", []),
                "year": paper.get("year", ""),
                "abstract": paper.get("abstract", ""),
                "doi": paper.get("doi", ""),
                "url": paper.get("url", ""),
                "source": "external",
            }
        )

    for paper in arxiv_papers:
        combined.append(
            {
                "paper_id": paper.get("arxiv_id") or "",
                "title": paper.get("title", ""),
                "authors": paper.get("authors", []),
                "year": paper.get("year", ""),
                "abstract": paper.get("abstract", ""),
                "doi": paper.get("doi", ""),
                "url": paper.get("url", ""),
                "source": "external",
            }
        )

    # Deduplicate by lowercased title
    seen_titles: set[str] = set()
    deduped: list[dict] = []
    for paper in combined:
        key = paper["title"].lower().strip()
        if key and key not in seen_titles:
            seen_titles.add(key)
            deduped.append(paper)

    sources_origin = [p["title"] for p in deduped if p["title"]]

    return {
        **state,
        "external_papers": deduped,
        "sources_origin": sources_origin,
    }
