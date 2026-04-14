"""Research Pipeline Supervisor — Phase B.

Orchestrates all agents using a LangGraph StateGraph:

    query_processor
        ↓
    cache_checker
        ├── cache_hit=True  ──────────────────────────────────→ END
        └── cache_hit=False
                ↓
            retriever
                ↓
            reranker_agent
                ↓
            confidence_evaluator
                ├── local_sufficient=True  → analysis_agent → storage_agent → END
                └── local_sufficient=False → external_search_agent → END
                                              (returns candidates only;
                                               ingestion happens after
                                               professor confirms via
                                               POST /api/research/confirm)
"""

import uuid
from datetime import datetime, timezone
from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.agents.analysis_agent import analysis_agent
from app.agents.cache_checker import cache_checker
from app.agents.confidence_evaluator import confidence_evaluator
from app.agents.external_search_agent import external_search_agent
from app.agents.query_processor import query_processor
from app.agents.reranker_agent import reranker_agent
from app.agents.retriever import retriever
from app.agents.storage_agent import storage_agent


# ---------------------------------------------------------------------------
# Shared state schema
# ---------------------------------------------------------------------------

class ResearchState(TypedDict):
    # Core inputs
    question: str
    error: str | None

    # Phase B — query processing
    normalized_query: str
    query_embedding: list[float]

    # Phase B — cache
    cache_hit: bool
    cached_answer: dict

    # Phase B — hybrid retrieval
    retrieved_chunks: list[dict]

    # Phase B — reranking
    reranked_chunks: list[dict]

    # Phase B — confidence
    confidence_score: float

    # Legacy fields kept for external_search / process path compatibility
    local_results: list[dict]
    local_sufficient: bool
    external_papers: list[dict]
    sources_origin: list[str]
    chunks_stored: bool

    # Final output
    analysis: dict

    # Phase B — post-analysis storage
    answer_stored: bool


# ---------------------------------------------------------------------------
# Routing functions
# ---------------------------------------------------------------------------

def _route_after_cache(state: ResearchState) -> str:
    """After cache_checker: short-circuit on hit, else proceed to retriever."""
    return "end" if state.get("cache_hit", False) else "retriever"


def _route_after_confidence(state: ResearchState) -> str:
    """After confidence_evaluator: go straight to analysis or external search.

    When local content is insufficient, the graph fetches external candidates
    but does NOT ingest them.  The API layer returns them for user selection
    via the two-step /confirm flow, which runs process_agent only on the
    papers the professor approves.
    """
    return "analyze" if state.get("local_sufficient", False) else "external_search"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def _build_graph() -> StateGraph:
    workflow = StateGraph(ResearchState)

    # Register all nodes
    workflow.add_node("query_processor", query_processor)
    workflow.add_node("cache_checker", cache_checker)
    workflow.add_node("retriever", retriever)
    workflow.add_node("reranker_agent", reranker_agent)
    workflow.add_node("confidence_evaluator", confidence_evaluator)
    workflow.add_node("external_search", external_search_agent)
    workflow.add_node("analyze", analysis_agent)
    workflow.add_node("storage_agent", storage_agent)

    # Entry point
    workflow.set_entry_point("query_processor")

    # Linear edges
    workflow.add_edge("query_processor", "cache_checker")

    # Cache branch
    workflow.add_conditional_edges(
        "cache_checker",
        _route_after_cache,
        {
            "end": END,
            "retriever": "retriever",
        },
    )

    # Retrieval → reranking → confidence
    workflow.add_edge("retriever", "reranker_agent")
    workflow.add_edge("reranker_agent", "confidence_evaluator")

    # Confidence branch
    workflow.add_conditional_edges(
        "confidence_evaluator",
        _route_after_confidence,
        {
            "analyze": "analyze",
            "external_search": "external_search",
        },
    )

    # External search path — goes straight to END so the API layer can
    # return candidates for professor approval.  process_agent + analysis
    # only run after the professor confirms via POST /api/research/confirm.
    workflow.add_edge("external_search", END)

    # Local-sufficient path: analyze → storage → END
    workflow.add_edge("analyze", "storage_agent")
    workflow.add_edge("storage_agent", END)

    return workflow


# Compile once at import time so we don't rebuild the graph on every request
_compiled_graph = _build_graph().compile()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def run_research_pipeline(question: str) -> dict:
    """Run the full multi-agent research pipeline.

    Args:
        question: The professor's research question.

    Returns:
        dict compatible with the frontend QueryResult type:
        id, question, createdAt, summary, agreements, contradictions,
        researchGaps, citations, externalPapersFetched, newPapersCount,
        confidenceScore, cacheHit.
    """
    initial_state: ResearchState = {
        "question": question,
        "error": None,
        # Phase B
        "normalized_query": "",
        "query_embedding": [],
        "cache_hit": False,
        "cached_answer": {},
        "retrieved_chunks": [],
        "reranked_chunks": [],
        "confidence_score": 0.0,
        "answer_stored": False,
        # Legacy
        "local_results": [],
        "local_sufficient": False,
        "external_papers": [],
        "sources_origin": [],
        "chunks_stored": False,
        "analysis": {},
    }

    final_state: ResearchState = await _compiled_graph.ainvoke(initial_state)

    query_embedding = final_state.get("query_embedding", [])

    # --- Cache hit path: return cached answer directly with metadata ---
    if final_state.get("cache_hit", False):
        cached = final_state.get("cached_answer", {})
        return {
            "id": str(uuid.uuid4()),
            "question": question,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "summary": cached.get("summary", ""),
            "agreements": cached.get("agreements", []),
            "contradictions": cached.get("contradictions", []),
            "researchGaps": cached.get("researchGaps", []),
            "citations": cached.get("citations", []),
            "externalPapersFetched": False,
            "newPapersCount": 0,
            "confidenceScore": final_state.get("confidence_score", 0.0),
            "cacheHit": True,
            "query_embedding": query_embedding,
        }

    # --- Normal path: assemble from analysis ---
    analysis = final_state.get("analysis", {})

    external_papers = final_state.get("external_papers", [])
    external_papers_fetched = (
        not final_state.get("local_sufficient", True) and len(external_papers) > 0
    )
    new_papers_count = len([p for p in external_papers if p.get("abstract")])

    return {
        "id": str(uuid.uuid4()),
        "question": question,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "summary": analysis.get("summary", ""),
        "agreements": analysis.get("agreements", []),
        "contradictions": analysis.get("contradictions", []),
        "researchGaps": analysis.get("researchGaps", []),
        "citations": analysis.get("citations", []),
        "externalPapersFetched": external_papers_fetched,
        "newPapersCount": new_papers_count,
        "confidenceScore": final_state.get("confidence_score", 0.0),
        "cacheHit": False,
        "query_embedding": query_embedding,
        # Phase C: pass through so the API layer can offer two-step selection
        "external_papers": external_papers,
        "local_sufficient": final_state.get("local_sufficient", True),
    }
