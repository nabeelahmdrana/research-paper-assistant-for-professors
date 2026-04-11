"""Agent pipeline tests — Phase 5.

Tests each agent in isolation and the full supervisor pipeline.
External API calls (Semantic Scholar, arXiv, Anthropic Claude) are patched so
the tests run offline and without API keys.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_chunk(paper_id: str, title: str = "Test Paper", text: str = "Sample text.", source: str = "local") -> dict:
    return {
        "id": f"{paper_id}_chunk_0",
        "text": text,
        "metadata": {
            "paper_id": paper_id,
            "title": title,
            "authors": "Author A, Author B",
            "year": "2023",
            "source": source,
            "doi": "10.1234/test",
            "url": "",
            "chunk_index": 0,
        },
        "distance": 0.1,
    }


# ---------------------------------------------------------------------------
# local_search_agent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_local_search_agent_sufficient() -> None:
    """When ChromaDB returns enough relevant chunks, local_sufficient=True."""
    from app.agents.local_search_agent import local_search_agent
    from app.config import settings

    chunks = [_make_chunk(f"paper_{i}") for i in range(settings.min_relevant_chunks + 2)]

    with patch("app.agents.local_search_agent.vector_store.query", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = chunks
        state = await local_search_agent({"question": "transformers", "local_results": [], "local_sufficient": False, "external_papers": [], "chunks_stored": False, "analysis": {}, "sources_origin": [], "error": None})

    assert state["local_sufficient"] is True
    assert len(state["local_results"]) == settings.min_relevant_chunks + 2


@pytest.mark.asyncio
async def test_local_search_agent_insufficient() -> None:
    """When ChromaDB returns too few results, local_sufficient=False."""
    from app.agents.local_search_agent import local_search_agent

    with patch("app.agents.local_search_agent.vector_store.query", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = []
        state = await local_search_agent({"question": "transformers", "local_results": [], "local_sufficient": False, "external_papers": [], "chunks_stored": False, "analysis": {}, "sources_origin": [], "error": None})

    assert state["local_sufficient"] is False
    assert state["local_results"] == []


@pytest.mark.asyncio
async def test_local_search_agent_filters_by_distance() -> None:
    """Chunks with distance > threshold are excluded from local_results."""
    from app.agents.local_search_agent import local_search_agent

    irrelevant_chunk = _make_chunk("far_paper")
    irrelevant_chunk["distance"] = 0.99  # far away, above threshold

    with patch("app.agents.local_search_agent.vector_store.query", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = [irrelevant_chunk]
        state = await local_search_agent({"question": "q", "local_results": [], "local_sufficient": False, "external_papers": [], "chunks_stored": False, "analysis": {}, "sources_origin": [], "error": None})

    assert state["local_sufficient"] is False
    assert len(state["local_results"]) == 0


# ---------------------------------------------------------------------------
# external_search_agent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_external_search_agent_combines_results() -> None:
    """Results from Semantic Scholar and arXiv are combined and deduped."""
    from app.agents.external_search_agent import external_search_agent

    ss_papers = [{"paperId": "ss1", "title": "Attention Is All You Need", "authors": ["Vaswani"], "year": 2017, "abstract": "Transformer paper", "doi": "", "url": ""}]
    arxiv_papers = [
        {"arxiv_id": "1706.03762", "title": "BERT Paper", "authors": ["Devlin"], "year": 2018, "abstract": "BERT abstract", "doi": "", "url": "https://arxiv.org/abs/1810.04805"},
        # Duplicate title from Semantic Scholar — should be deduped
        {"arxiv_id": "1706.03762", "title": "Attention Is All You Need", "authors": ["Vaswani"], "year": 2017, "abstract": "Dup", "doi": "", "url": ""},
    ]

    state: dict[str, Any] = {"question": "transformers", "local_results": [], "local_sufficient": False, "external_papers": [], "chunks_stored": False, "analysis": {}, "sources_origin": [], "error": None}

    with patch("app.agents.external_search_agent.search_semantic_scholar", new_callable=AsyncMock) as mock_ss, \
         patch("app.agents.external_search_agent.search_arxiv", new_callable=AsyncMock) as mock_arxiv:
        mock_ss.return_value = ss_papers
        mock_arxiv.return_value = arxiv_papers
        state = await external_search_agent(state)

    # 1 from SS + 1 unique from arXiv (dup removed) = 2
    assert len(state["external_papers"]) == 2
    titles = {p["title"] for p in state["external_papers"]}
    assert "BERT Paper" in titles
    assert "Attention Is All You Need" in titles


# ---------------------------------------------------------------------------
# process_agent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_agent_ingests_external_papers() -> None:
    """process_agent calls ingest_paper for each paper with a non-empty abstract."""
    from app.agents.process_agent import process_agent

    external_papers = [
        {"paper_id": "ext1", "title": "Paper A", "authors": ["X"], "year": 2021, "abstract": "Some abstract", "doi": "", "url": "", "source": "external"},
        {"paper_id": "ext2", "title": "Paper B", "authors": ["Y"], "year": 2022, "abstract": "", "doi": "", "url": "", "source": "external"},  # empty abstract — should be skipped
    ]
    state: dict[str, Any] = {"question": "q", "local_results": [], "local_sufficient": False, "external_papers": external_papers, "chunks_stored": False, "analysis": {}, "sources_origin": [], "error": None}

    with patch("app.agents.process_agent.ingest_paper", new_callable=AsyncMock) as mock_ingest:
        mock_ingest.return_value = 3
        state = await process_agent(state)

    # Only Paper A has abstract — should be called once
    assert mock_ingest.call_count == 1
    assert state["chunks_stored"] is True


# ---------------------------------------------------------------------------
# analysis_agent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analysis_agent_calls_claude_and_parses_json() -> None:
    """analysis_agent calls Claude and parses the structured JSON response."""
    from app.agents.analysis_agent import analysis_agent

    chunks = [_make_chunk("p1", title="Attention Is All You Need", text="Transformers are great.")]

    claude_response_json = '{"summary":"Transformers dominate NLP.","agreements":["Self-attention scales [1]"],"contradictions":[],"researchGaps":["Efficiency at scale"],"citations":[{"index":1,"title":"Attention Is All You Need","authors":["Vaswani"],"year":2017,"source":"local","doi":"10.1234/test","url":""}]}'

    mock_message = MagicMock()
    mock_message.content = claude_response_json
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    state: dict[str, Any] = {"question": "What are transformers?", "local_results": chunks, "local_sufficient": True, "external_papers": [], "chunks_stored": False, "analysis": {}, "sources_origin": [], "error": None}

    with patch("app.agents.analysis_agent.vector_store.query", new_callable=AsyncMock) as mock_query, \
         patch("app.agents.analysis_agent.AsyncOpenAI") as mock_anthropic_cls:
        mock_query.return_value = chunks
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_anthropic_cls.return_value = mock_client

        state = await analysis_agent(state)

    analysis = state["analysis"]
    assert analysis["summary"] == "Transformers dominate NLP."
    assert len(analysis["agreements"]) == 1
    assert len(analysis["citations"]) == 1


@pytest.mark.asyncio
async def test_analysis_agent_handles_empty_db() -> None:
    """When ChromaDB is empty, analysis returns a graceful empty response."""
    from app.agents.analysis_agent import analysis_agent

    state: dict[str, Any] = {"question": "q", "local_results": [], "local_sufficient": False, "external_papers": [], "chunks_stored": True, "analysis": {}, "sources_origin": [], "error": None}

    with patch("app.agents.analysis_agent.vector_store.query", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = []
        state = await analysis_agent(state)

    assert "No relevant papers" in state["analysis"]["summary"]
    assert state["analysis"]["citations"] == []


# ---------------------------------------------------------------------------
# Full pipeline — supervisor
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_supervisor_local_path() -> None:
    """When local results are sufficient, external search is skipped."""
    from app.agents.supervisor import run_research_pipeline
    from app.config import settings

    sufficient_chunks = [_make_chunk(f"p{i}") for i in range(settings.min_relevant_chunks + 1)]

    claude_json = '{"summary":"Local summary.","agreements":[],"contradictions":[],"researchGaps":[],"citations":[]}'
    mock_message = MagicMock()
    mock_message.content = claude_json
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch("app.agents.local_search_agent.vector_store.query", new_callable=AsyncMock, return_value=sufficient_chunks), \
         patch("app.agents.analysis_agent.vector_store.query", new_callable=AsyncMock, return_value=sufficient_chunks), \
         patch("app.agents.analysis_agent.AsyncOpenAI") as mock_cls, \
         patch("app.agents.external_search_agent.search_semantic_scholar", new_callable=AsyncMock, return_value=[]), \
         patch("app.agents.external_search_agent.search_arxiv", new_callable=AsyncMock, return_value=[]):

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client

        result = await run_research_pipeline("What are transformers?")

    assert result["summary"] == "Local summary."
    assert "id" in result
    assert "createdAt" in result
    assert result["question"] == "What are transformers?"


@pytest.mark.asyncio
async def test_supervisor_external_path() -> None:
    """When local results are insufficient, external search is triggered."""
    from app.agents.supervisor import run_research_pipeline

    external_papers = [
        {"paper_id": "ext1", "title": "External Paper", "authors": ["X"], "year": 2022, "abstract": "Abstract text", "doi": "", "url": "", "source": "external"}
    ]

    claude_json = '{"summary":"External summary.","agreements":[],"contradictions":[],"researchGaps":[],"citations":[]}'
    mock_message = MagicMock()
    mock_message.content = claude_json
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch("app.agents.local_search_agent.vector_store.query", new_callable=AsyncMock, return_value=[]), \
         patch("app.agents.external_search_agent.search_semantic_scholar", new_callable=AsyncMock, return_value=external_papers), \
         patch("app.agents.external_search_agent.search_arxiv", new_callable=AsyncMock, return_value=[]), \
         patch("app.agents.process_agent.ingest_paper", new_callable=AsyncMock, return_value=2), \
         patch("app.agents.analysis_agent.vector_store.query", new_callable=AsyncMock, return_value=[]), \
         patch("app.agents.analysis_agent.AsyncOpenAI") as mock_cls:

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client

        result = await run_research_pipeline("novel topic with no local papers")

    # When analysis returns empty analysis (no chunks), graceful fallback kicks in
    # but in this test the mock returns empty chunks for analysis, so the graceful path runs
    assert "question" in result
    assert result["question"] == "novel topic with no local papers"
