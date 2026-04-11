"""Research Pipeline Supervisor — Phase 5.

Orchestrates the four agents using a LangGraph StateGraph:

    local_search
        ├── (sufficient) ──→ analysis ──→ END
        └── (insufficient) → external_search → process → analysis → END
"""

import uuid
from datetime import datetime, timezone
from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.agents.analysis_agent import analysis_agent
from app.agents.external_search_agent import external_search_agent
from app.agents.local_search_agent import local_search_agent
from app.agents.process_agent import process_agent


class ResearchState(TypedDict):
    question: str
    local_results: list[dict]
    local_sufficient: bool
    external_papers: list[dict]
    chunks_stored: bool
    analysis: dict
    sources_origin: list[str]
    error: str | None


def _route_after_local_search(state: ResearchState) -> str:
    """Conditional edge: go to analysis if local results are sufficient."""
    return "analyze" if state.get("local_sufficient", False) else "external_search"


def _build_graph() -> StateGraph:
    workflow = StateGraph(ResearchState)

    workflow.add_node("local_search", local_search_agent)
    workflow.add_node("external_search", external_search_agent)
    workflow.add_node("process", process_agent)
    workflow.add_node("analyze", analysis_agent)

    workflow.set_entry_point("local_search")

    workflow.add_conditional_edges(
        "local_search",
        _route_after_local_search,
        {
            "analyze": "analyze",
            "external_search": "external_search",
        },
    )

    workflow.add_edge("external_search", "process")
    workflow.add_edge("process", "analyze")
    workflow.add_edge("analyze", END)

    return workflow


# Compile once at import time so we don't rebuild the graph on every request
_compiled_graph = _build_graph().compile()


async def run_research_pipeline(question: str) -> dict:
    """Run the full multi-agent research pipeline.

    Args:
        question: The professor's research question.

    Returns:
        dict compatible with the frontend QueryResult type:
        id, question, createdAt, summary, agreements, contradictions,
        researchGaps, citations.
    """
    initial_state: ResearchState = {
        "question": question,
        "local_results": [],
        "local_sufficient": False,
        "external_papers": [],
        "chunks_stored": False,
        "analysis": {},
        "sources_origin": [],
        "error": None,
    }

    final_state: ResearchState = await _compiled_graph.ainvoke(initial_state)

    analysis = final_state.get("analysis", {})

    return {
        "id": str(uuid.uuid4()),
        "question": question,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "summary": analysis.get("summary", ""),
        "agreements": analysis.get("agreements", []),
        "contradictions": analysis.get("contradictions", []),
        "researchGaps": analysis.get("researchGaps", []),
        "citations": analysis.get("citations", []),
    }
