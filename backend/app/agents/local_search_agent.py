"""Local Search Agent — Phase 5.

Queries ChromaDB for chunks relevant to the research question and decides
whether the local results are sufficient to answer without external lookup.
"""

from app.config import settings
from app.tools import vector_store


async def local_search_agent(state: dict) -> dict:
    """Query ChromaDB for relevant paper chunks.

    Fetches up to 2× min_relevant_chunks results and filters by the
    configured relevance_threshold.  A result is "sufficient" when at least
    min_relevant_chunks chunks pass the threshold.

    Cosine distance returned by ChromaDB is in [0, 2]:
      0 = identical, 1 = orthogonal, 2 = opposite.
    We treat distance <= (1 - relevance_threshold) as relevant
    (e.g. threshold 0.7 → distance <= 0.3).

    Populates:
        state["local_results"]   – list of relevant chunk dicts
        state["local_sufficient"] – True if enough results found
    """
    question: str = state["question"]
    n_fetch = max(settings.min_relevant_chunks * 2, 20)

    raw_results = await vector_store.query(question, n_results=n_fetch)

    # Filter by relevance threshold
    max_distance = 1.0 - settings.relevance_threshold
    relevant = [r for r in raw_results if r.get("distance", 1.0) <= max_distance]

    local_sufficient = len(relevant) >= settings.min_relevant_chunks

    return {
        **state,
        "local_results": relevant,
        "local_sufficient": local_sufficient,
    }
