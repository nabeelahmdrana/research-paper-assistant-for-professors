import xml.etree.ElementTree as ET

import httpx


_ATOM_NS = "http://www.w3.org/2005/Atom"
_ARXIV_NS = "http://arxiv.org/schemas/atom"


def _parse_arxiv_feed(xml_text: str) -> list[dict]:
    """Parse an arXiv Atom feed and return a list of paper dicts."""
    root = ET.fromstring(xml_text)
    results: list[dict] = []

    for entry in root.findall(f"{{{_ATOM_NS}}}entry"):
        # arXiv ID lives in the <id> element as a full URL
        id_el = entry.find(f"{{{_ATOM_NS}}}id")
        full_id = (id_el.text or "").strip() if id_el is not None else ""
        arxiv_id = full_id.split("/abs/")[-1] if "/abs/" in full_id else full_id

        title_el = entry.find(f"{{{_ATOM_NS}}}title")
        title = " ".join((title_el.text or "").split()) if title_el is not None else ""

        summary_el = entry.find(f"{{{_ATOM_NS}}}summary")
        abstract = (
            " ".join((summary_el.text or "").split()) if summary_el is not None else ""
        )

        # Published date — take the year
        published_el = entry.find(f"{{{_ATOM_NS}}}published")
        year: int | str = ""
        if published_el is not None and published_el.text:
            try:
                year = int(published_el.text[:4])
            except ValueError:
                year = published_el.text[:4]

        # Authors
        authors: list[str] = []
        for author_el in entry.findall(f"{{{_ATOM_NS}}}author"):
            name_el = author_el.find(f"{{{_ATOM_NS}}}name")
            if name_el is not None and name_el.text:
                authors.append(name_el.text.strip())

        # DOI (if the paper has been published with a journal DOI)
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


async def search_arxiv(query: str, max_results: int = 10) -> list[dict]:
    """Search arXiv for papers matching the query.

    No API key required.

    Args:
        query: Search string.
        max_results: Maximum number of results to return.

    Returns:
        List of paper dicts with keys: arxiv_id, title, authors, year,
        abstract, doi, url.
    """
    url = "http://export.arxiv.org/api/query"
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError:
            return []
        except httpx.HTTPError:
            return []

    return _parse_arxiv_feed(response.text)
