"""External Search Agent — Phase 5.

Fetches papers from Semantic Scholar and arXiv when local DB is insufficient.
"""

from app.tools.arxiv_search import search_arxiv
from app.tools.semantic_scholar import search_semantic_scholar


async def external_search_agent(state: dict) -> dict:
    """Search Semantic Scholar and arXiv for papers relevant to the question.

    Results from both APIs are combined and deduplicated by title
    (case-insensitive).

    Populates:
        state["external_papers"] – list of paper dicts ready for ingestion
    """
    question: str = state["question"]

    # Fetch from both sources concurrently
    import asyncio

    ss_papers, arxiv_papers = await asyncio.gather(
        search_semantic_scholar(question, limit=10),
        search_arxiv(question, max_results=10),
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

    return {
        **state,
        "external_papers": deduped,
    }
