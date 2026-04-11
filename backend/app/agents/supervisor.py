# Phase 5 (rag-specialist): implement LangGraph supervisor here
from typing import TypedDict


class ResearchState(TypedDict):
    question: str
    local_results: list[dict]
    local_sufficient: bool
    external_papers: list[dict]
    chunks_stored: bool
    analysis: dict
    sources_origin: list[str]
    error: str | None


async def run_research_pipeline(question: str) -> dict:
    """Run the full multi-agent research pipeline.

    Args:
        question: The professor's research question

    Returns:
        dict with summary, agreements, contradictions, gaps, citations
    """
    # TODO (rag-specialist): implement LangGraph StateGraph
    raise NotImplementedError("rag-specialist: implement run_research_pipeline()")
