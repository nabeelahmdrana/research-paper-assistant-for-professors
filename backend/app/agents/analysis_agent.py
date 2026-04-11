# Phase 5 (rag-specialist): implement analysis agent here
# RAG retrieval + Claude LLM → structured literature review


async def analysis_agent(state: dict) -> dict:
    """Retrieve relevant chunks and generate a literature review using RAG.

    Sets state["analysis"] with: summary, agreements, contradictions, gaps, citations.
    Citations must reference actual stored papers — no hallucinated sources.
    """
    # TODO (rag-specialist): implement
    raise NotImplementedError("rag-specialist: implement analysis_agent()")
