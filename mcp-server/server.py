"""paper-search-mcp server.

Exposes two MCP tools:
  - search_papers(query, limit)       — wraps Semantic Scholar API
  - search_arxiv_papers(query, limit) — wraps arXiv Atom feed API

Run with:
    python server.py
or via the config in mcp-server/config.json.
"""

import xml.etree.ElementTree as ET

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("paper-search-mcp")

_ATOM_NS = "http://www.w3.org/2005/Atom"
_ARXIV_NS = "http://arxiv.org/schemas/atom"


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


@mcp.tool()
async def search_arxiv_papers(query: str, limit: int = 10) -> list[dict]:
    """Search arXiv for academic papers matching the query.

    Args:
        query: The search query string.
        limit: Maximum number of results to return (default 10).

    Returns:
        List of paper dicts with keys: arxiv_id, title, authors, year,
        abstract, doi, url.
    """
    url = "https://export.arxiv.org/api/query"
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": min(limit, 100),
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError:
            return []
        except httpx.HTTPError:
            return []

    root = ET.fromstring(response.text)
    results: list[dict] = []

    for entry in root.findall(f"{{{_ATOM_NS}}}entry"):
        id_el = entry.find(f"{{{_ATOM_NS}}}id")
        full_id = (id_el.text or "").strip() if id_el is not None else ""
        arxiv_id = full_id.split("/abs/")[-1] if "/abs/" in full_id else full_id

        title_el = entry.find(f"{{{_ATOM_NS}}}title")
        title = " ".join((title_el.text or "").split()) if title_el is not None else ""

        summary_el = entry.find(f"{{{_ATOM_NS}}}summary")
        abstract = (
            " ".join((summary_el.text or "").split()) if summary_el is not None else ""
        )

        published_el = entry.find(f"{{{_ATOM_NS}}}published")
        year: int | str = ""
        if published_el is not None and published_el.text:
            try:
                year = int(published_el.text[:4])
            except ValueError:
                year = published_el.text[:4]

        authors: list[str] = []
        for author_el in entry.findall(f"{{{_ATOM_NS}}}author"):
            name_el = author_el.find(f"{{{_ATOM_NS}}}name")
            if name_el is not None and name_el.text:
                authors.append(name_el.text.strip())

        doi_el = entry.find(f"{{{_ARXIV_NS}}}doi")
        doi = doi_el.text.strip() if doi_el is not None and doi_el.text else ""

        paper_url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else full_id

        results.append(
            {
                "arxiv_id": arxiv_id,
                "title": title,
                "authors": authors,
                "year": year,
                "abstract": abstract,
                "doi": doi,
                "url": paper_url,
            }
        )

    return results


if __name__ == "__main__":
    mcp.run()
