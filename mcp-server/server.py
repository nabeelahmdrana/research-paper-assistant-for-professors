"""paper-search-mcp server.

Exposes one MCP tool: search_papers(query, limit) that wraps Semantic Scholar.
Run with:
    python server.py
or via the config in mcp-server/config.json.
"""

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("paper-search-mcp")


@mcp.tool()
async def search_papers(query: str, limit: int = 10) -> list[dict]:
    """Search Semantic Scholar for academic papers matching the query.

    Args:
        query: The search query string.
        limit: Maximum number of results to return (default 10).

    Returns:
        List of paper dicts with keys: paperId, title, authors, year,
        abstract, doi, url.
    """
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    fields = "paperId,title,authors,year,abstract,externalIds,url"
    params = {"query": query, "limit": min(limit, 100), "fields": fields}

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError:
            return []
        except httpx.HTTPError:
            return []

    raw = response.json()
    papers = raw.get("data", [])

    results: list[dict] = []
    for paper in papers:
        external_ids = paper.get("externalIds") or {}
        doi = external_ids.get("DOI", "")
        arxiv_id = external_ids.get("ArXiv", "")

        author_names = [a.get("name", "") for a in (paper.get("authors") or [])]

        paper_url = paper.get("url") or ""
        if not paper_url and arxiv_id:
            paper_url = f"https://arxiv.org/abs/{arxiv_id}"
        elif not paper_url and doi:
            paper_url = f"https://doi.org/{doi}"

        results.append(
            {
                "paperId": paper.get("paperId", ""),
                "title": paper.get("title", ""),
                "authors": author_names,
                "year": paper.get("year") or "",
                "abstract": paper.get("abstract", "") or "",
                "doi": doi,
                "url": paper_url,
            }
        )

    return results


if __name__ == "__main__":
    mcp.run()
