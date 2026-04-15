"""Agent pipeline tests — Phase 5 / Phase B.

Tests each agent in isolation and the full supervisor pipeline.
External API calls (MCP, OpenAI) are patched so the tests run offline
and without API keys.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_chunk(
    paper_id: str,
    title: str = "Test Paper",
    text: str = "Sample text.",
    source: str = "local",
    distance: float = 0.1,
) -> dict:
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
        "distance": distance,
    }


def _make_openai_response(json_text: str) -> MagicMock:
    """Build a mock OpenAI ChatCompletion response containing json_text."""
    mock_message = MagicMock()
    mock_message.content = json_text
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    return mock_response


def _make_mock_query_processor_client(embedding: list[float]) -> AsyncMock:
    """Build a mock AsyncOpenAI client for query_processor (embeddings + HyDE chat)."""
    mock_embedding_data = MagicMock()
    mock_embedding_data.embedding = embedding
    mock_embed_response = MagicMock()
    mock_embed_response.data = [mock_embedding_data]

    # HyDE chat response — return empty string so HyDE embedding is skipped
    mock_chat_msg = MagicMock()
    mock_chat_msg.content = ""
    mock_chat_choice = MagicMock()
    mock_chat_choice.message = mock_chat_msg
    mock_chat_response = MagicMock()
    mock_chat_response.choices = [mock_chat_choice]

    mock_client = AsyncMock()
    mock_client.embeddings.create = AsyncMock(return_value=mock_embed_response)
    mock_client.chat.completions.create = AsyncMock(return_value=mock_chat_response)
    return mock_client


# Helper: full initial state with all Phase B fields
def _base_state(**overrides: Any) -> dict:
    state: dict[str, Any] = {
        "question": "transformers",
        "error": None,
        "normalized_query": "",
        "query_embedding": [],
        "cache_hit": False,
        "cached_answer": {},
        "retrieved_chunks": [],
        "reranked_chunks": [],
        "confidence_score": 0.0,
        "answer_stored": False,
        "local_results": [],
        "local_sufficient": False,
        "external_papers": [],
        "chunks_stored": False,
        "analysis": {},
        "sources_origin": [],
    }
    state.update(overrides)
    return state


# ---------------------------------------------------------------------------
# query_processor
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_query_processor_normalises_query() -> None:
    """query_processor strips and lowercases the query and generates an embedding."""
    from app.agents.query_processor import query_processor

    mock_embedding_data = MagicMock()
    mock_embedding_data.embedding = [0.1, 0.2, 0.3]
    mock_embed_response = MagicMock()
    mock_embed_response.data = [mock_embedding_data]

    # HyDE: mock the chat completion too (returns empty to simplify)
    mock_chat_response = MagicMock()
    mock_chat_response.choices = [MagicMock()]
    mock_chat_response.choices[0].message.content = ""

    mock_client = AsyncMock()
    mock_client.embeddings.create = AsyncMock(return_value=mock_embed_response)
    mock_client.chat.completions.create = AsyncMock(return_value=mock_chat_response)

    with patch("app.agents.query_processor.AsyncOpenAI", return_value=mock_client):
        state = await query_processor(_base_state(question="  Transformers NLP  "))

    assert state["normalized_query"] == "transformers nlp"
    assert state["query_embedding"] == [0.1, 0.2, 0.3]


# ---------------------------------------------------------------------------
# cache_checker
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_checker_hit() -> None:
    """cache_checker returns cache_hit=True when lookup returns a result."""
    from app.agents.cache_checker import cache_checker

    cached_answer = {"summary": "Cached.", "agreements": [], "contradictions": [], "researchGaps": [], "citations": []}

    with patch("app.agents.cache_checker.answer_cache.lookup", new_callable=AsyncMock, return_value=cached_answer):
        state = await cache_checker(_base_state(query_embedding=[0.1, 0.2, 0.3]))

    assert state["cache_hit"] is True
    assert state["cached_answer"] == cached_answer


@pytest.mark.asyncio
async def test_cache_checker_miss() -> None:
    """cache_checker returns cache_hit=False when lookup returns None."""
    from app.agents.cache_checker import cache_checker

    with patch("app.agents.cache_checker.answer_cache.lookup", new_callable=AsyncMock, return_value=None):
        state = await cache_checker(_base_state(query_embedding=[0.1, 0.2, 0.3]))

    assert state["cache_hit"] is False
    assert state["cached_answer"] == {}


@pytest.mark.asyncio
async def test_cache_checker_empty_embedding() -> None:
    """cache_checker skips lookup when query_embedding is empty."""
    from app.agents.cache_checker import cache_checker

    with patch("app.agents.cache_checker.answer_cache.lookup", new_callable=AsyncMock) as mock_lookup:
        state = await cache_checker(_base_state(query_embedding=[]))

    mock_lookup.assert_not_called()
    assert state["cache_hit"] is False


# ---------------------------------------------------------------------------
# retriever
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retriever_merges_results() -> None:
    """retriever combines vector and BM25 results and applies RRF."""
    from app.agents.retriever import retriever

    vector_chunks = [_make_chunk(f"vec_{i}") for i in range(5)]
    bm25_chunks = [_make_chunk(f"bm25_{i}") for i in range(5)]

    mock_bm25 = MagicMock()
    mock_bm25.is_ready = True
    mock_bm25.search.return_value = bm25_chunks

    with patch("app.agents.retriever.vector_store.query", new_callable=AsyncMock, return_value=vector_chunks), \
         patch("app.agents.retriever.bm25_index", mock_bm25):
        state = await retriever(_base_state(question="transformers"))

    # All 10 unique chunks should appear (5 vec + 5 bm25, no overlap)
    assert len(state["retrieved_chunks"]) == 10
    # Every chunk should have an rrf_score
    for chunk in state["retrieved_chunks"]:
        assert "rrf_score" in chunk


@pytest.mark.asyncio
async def test_retriever_rebuilds_bm25_if_not_ready() -> None:
    """retriever calls build_index() when the BM25 index is not ready."""
    from app.agents.retriever import retriever

    mock_bm25 = MagicMock()
    mock_bm25.is_ready = False
    mock_bm25.build_index = AsyncMock()
    mock_bm25.search.return_value = []

    with patch("app.agents.retriever.vector_store.query", new_callable=AsyncMock, return_value=[]), \
         patch("app.agents.retriever.bm25_index", mock_bm25):
        await retriever(_base_state(question="q"))

    mock_bm25.build_index.assert_awaited_once()


# ---------------------------------------------------------------------------
# reranker_agent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reranker_agent_reranks_chunks() -> None:
    """reranker_agent returns reranked_chunks with rerank_score added."""
    from app.agents.reranker_agent import reranker_agent

    chunks = [_make_chunk(f"p{i}") for i in range(5)]
    reranked = [dict(c, rerank_score=float(5 - i)) for i, c in enumerate(chunks)]

    with patch("app.agents.reranker_agent.reranker.rerank", return_value=reranked):
        state = await reranker_agent(_base_state(question="q", retrieved_chunks=chunks))

    assert state["reranked_chunks"] == reranked


@pytest.mark.asyncio
async def test_reranker_agent_empty_input() -> None:
    """reranker_agent returns empty list when retrieved_chunks is empty."""
    from app.agents.reranker_agent import reranker_agent

    state = await reranker_agent(_base_state(question="q", retrieved_chunks=[]))
    assert state["reranked_chunks"] == []


# ---------------------------------------------------------------------------
# confidence_evaluator
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_confidence_evaluator_sufficient() -> None:
    """High-similarity chunks from 3+ papers should yield local_sufficient=True."""
    from app.agents.confidence_evaluator import confidence_evaluator

    chunks = [_make_chunk(f"paper_{i}", distance=0.05) for i in range(4)]
    state = await confidence_evaluator(_base_state(reranked_chunks=chunks))

    assert state["confidence_score"] > 0.7
    assert state["local_sufficient"] is True


@pytest.mark.asyncio
async def test_confidence_evaluator_insufficient() -> None:
    """No chunks should yield confidence=0 and local_sufficient=False."""
    from app.agents.confidence_evaluator import confidence_evaluator

    state = await confidence_evaluator(_base_state(reranked_chunks=[]))
    assert state["confidence_score"] == 0.0
    assert state["local_sufficient"] is False


# ---------------------------------------------------------------------------
# storage_agent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_storage_agent_stores_answer() -> None:
    """storage_agent calls answer_cache.store and sets answer_stored=True."""
    from app.agents.storage_agent import storage_agent

    analysis = {"summary": "Test.", "agreements": [], "contradictions": [], "researchGaps": [], "citations": []}

    with patch("app.agents.storage_agent.answer_cache.store", new_callable=AsyncMock) as mock_store:
        state = await storage_agent(_base_state(
            question="test query",
            query_embedding=[0.1, 0.2],
            analysis=analysis,
        ))

    mock_store.assert_awaited_once()
    assert state["answer_stored"] is True


@pytest.mark.asyncio
async def test_storage_agent_skips_on_empty_embedding() -> None:
    """storage_agent sets answer_stored=False and skips store when embedding is empty."""
    from app.agents.storage_agent import storage_agent

    with patch("app.agents.storage_agent.answer_cache.store", new_callable=AsyncMock) as mock_store:
        state = await storage_agent(_base_state(
            question="q",
            query_embedding=[],
            analysis={"summary": "x"},
        ))

    mock_store.assert_not_called()
    assert state["answer_stored"] is False


# ---------------------------------------------------------------------------
# local_search_agent (retained for backward compatibility)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_local_search_agent_sufficient() -> None:
    """When ChromaDB returns enough relevant chunks, local_sufficient=True."""
    from app.agents.local_search_agent import local_search_agent
    from app.config import settings

    chunks = [_make_chunk(f"paper_{i}") for i in range(settings.min_relevant_chunks + 2)]

    with patch("app.agents.local_search_agent.vector_store.query", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = chunks
        state = await local_search_agent(_base_state())

    assert state["local_sufficient"] is True
    assert len(state["local_results"]) == settings.min_relevant_chunks + 2


@pytest.mark.asyncio
async def test_local_search_agent_insufficient() -> None:
    """When ChromaDB returns too few results, local_sufficient=False."""
    from app.agents.local_search_agent import local_search_agent

    with patch("app.agents.local_search_agent.vector_store.query", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = []
        state = await local_search_agent(_base_state())

    assert state["local_sufficient"] is False
    assert state["local_results"] == []


@pytest.mark.asyncio
async def test_local_search_agent_filters_by_distance() -> None:
    """Chunks with distance > threshold are excluded from local_results."""
    from app.agents.local_search_agent import local_search_agent

    irrelevant_chunk = _make_chunk("far_paper", distance=0.99)

    with patch("app.agents.local_search_agent.vector_store.query", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = [irrelevant_chunk]
        state = await local_search_agent(_base_state(question="q"))

    assert state["local_sufficient"] is False
    assert len(state["local_results"]) == 0


# ---------------------------------------------------------------------------
# external_search_agent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_external_search_agent_combines_results() -> None:
    """Results from arXiv and PubMed (via MCP) are combined and deduplicated."""
    from app.agents.external_search_agent import external_search_agent

    # external_search_agent calls: search_arxiv, search_pubmed, search_biorxiv, search_medrxiv
    arxiv_papers = [
        {
            "title": "Attention Is All You Need",
            "authors": ["Vaswani"],
            "published_date": "2017-06-12",
            "abstract": "Transformer paper",
            "doi": "",
            "url": "",
            "paper_id": "arxiv:1706.03762",
        }
    ]
    pubmed_papers = [
        {
            "title": "BERT Paper",
            "authors": ["Devlin"],
            "published_date": "2018-10-11",
            "abstract": "BERT abstract",
            "doi": "",
            "url": "https://arxiv.org/abs/1810.04805",
            "paper_id": "pubmed:bert",
        },
        # Duplicate title — should be deduped
        {
            "title": "Attention Is All You Need",
            "authors": ["Vaswani"],
            "published_date": "2017-06-12",
            "abstract": "Dup",
            "doi": "",
            "url": "",
            "paper_id": "pubmed:dup",
        },
    ]

    async def mock_mcp_tool(tool_name: str, args: dict) -> list[dict]:
        if tool_name == "search_arxiv":
            return arxiv_papers
        if tool_name == "search_pubmed":
            return pubmed_papers
        return []

    with patch("app.agents.external_search_agent._call_mcp_tool", side_effect=mock_mcp_tool):
        state = await external_search_agent(_base_state())

    # 1 from arXiv + 1 unique from PubMed (dup removed) = 2
    assert len(state["external_papers"]) == 2
    titles = {p["title"] for p in state["external_papers"]}
    assert "BERT Paper" in titles
    assert "Attention Is All You Need" in titles
    assert len(state["sources_origin"]) == 2


# ---------------------------------------------------------------------------
# process_agent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_agent_ingests_external_papers() -> None:
    """process_agent calls ingest_paper for each paper with a non-empty abstract."""
    from app.agents.process_agent import process_agent

    external_papers = [
        {"paper_id": "ext1", "title": "Paper A", "authors": ["X"], "year": 2021, "abstract": "Some abstract", "doi": "", "url": "", "source": "external"},
        {"paper_id": "ext2", "title": "Paper B", "authors": ["Y"], "year": 2022, "abstract": "", "doi": "", "url": "", "source": "external"},
    ]
    state = _base_state(external_papers=external_papers)

    with patch("app.agents.process_agent.ingest_paper", new_callable=AsyncMock) as mock_ingest:
        mock_ingest.return_value = 3
        state = await process_agent(state)

    assert mock_ingest.call_count == 1
    assert state["chunks_stored"] is True
    ingested_meta = mock_ingest.call_args[0][1]
    assert ingested_meta["source"] == "local"


# ---------------------------------------------------------------------------
# analysis_agent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analysis_agent_uses_reranked_chunks() -> None:
    """analysis_agent uses reranked_chunks when available and calls the LLM."""
    from app.agents.analysis_agent import analysis_agent

    chunks = [_make_chunk("p1", title="Attention Is All You Need", text="Transformers are great.")]

    llm_response_json = (
        '{"summary":"Transformers dominate NLP.",'
        '"agreements":["Self-attention scales [1]"],'
        '"contradictions":[],'
        '"researchGaps":["Efficiency at scale"],'
        '"citations":[{"index":1,"title":"Attention Is All You Need",'
        '"authors":["Vaswani"],"year":2017,"source":"local","doi":"10.1234/test","url":""}]}'
    )

    mock_response = _make_openai_response(llm_response_json)

    state = _base_state(
        question="What are transformers?",
        reranked_chunks=chunks,
    )

    with patch("app.agents.analysis_agent.AsyncOpenAI") as mock_openai_cls:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_openai_cls.return_value = mock_client

        state = await analysis_agent(state)

    analysis = state["analysis"]
    assert analysis["summary"] == "Transformers dominate NLP."
    assert len(analysis["agreements"]) == 1
    assert len(analysis["citations"]) == 1


@pytest.mark.asyncio
async def test_analysis_agent_falls_back_to_retrieved_chunks() -> None:
    """When reranked_chunks is empty, analysis_agent falls back to retrieved_chunks."""
    from app.agents.analysis_agent import analysis_agent

    chunks = [_make_chunk("p1", text="Fallback text.")]
    llm_response_json = (
        '{"summary":"Fallback summary.","agreements":[],'
        '"contradictions":[],"researchGaps":[],"citations":[]}'
    )
    mock_response = _make_openai_response(llm_response_json)

    state = _base_state(
        question="test",
        reranked_chunks=[],
        retrieved_chunks=chunks,
    )

    with patch("app.agents.analysis_agent.AsyncOpenAI") as mock_openai_cls:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_openai_cls.return_value = mock_client

        state = await analysis_agent(state)

    assert state["analysis"]["summary"] == "Fallback summary."


@pytest.mark.asyncio
async def test_analysis_agent_handles_empty_db() -> None:
    """When all chunk sources are empty, analysis returns a graceful empty response."""
    from app.agents.analysis_agent import analysis_agent

    state = _base_state(
        question="q",
        reranked_chunks=[],
        retrieved_chunks=[],
    )

    with patch("app.agents.analysis_agent.vector_store.query", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = []
        state = await analysis_agent(state)

    assert "No relevant papers" in state["analysis"]["summary"]
    assert state["analysis"]["citations"] == []


# ---------------------------------------------------------------------------
# Full pipeline — supervisor
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_supervisor_cache_hit_returns_early() -> None:
    """When cache_checker finds a hit, the pipeline short-circuits to END."""
    from app.agents.supervisor import run_research_pipeline

    cached_answer = {
        "summary": "Cached answer.",
        "agreements": [],
        "contradictions": [],
        "researchGaps": [],
        "citations": [],
    }

    mock_embedding = [0.1] * 384
    mock_qp_client = _make_mock_query_processor_client(mock_embedding)

    with patch("app.agents.query_processor.AsyncOpenAI", return_value=mock_qp_client), \
         patch("app.agents.query_expander.AsyncOpenAI", return_value=mock_qp_client), \
         patch("app.agents.cache_checker.answer_cache.lookup", new_callable=AsyncMock, return_value=cached_answer):

        result = await run_research_pipeline("cached query")

    assert result["cacheHit"] is True
    assert result["summary"] == "Cached answer."


@pytest.mark.asyncio
async def test_supervisor_local_path() -> None:
    """When local results are sufficient, external search is skipped."""
    from app.agents.supervisor import run_research_pipeline
    from app.config import settings

    sufficient_chunks = [_make_chunk(f"p{i}", distance=0.05) for i in range(settings.min_relevant_chunks + 1)]
    mock_embedding = [0.1] * 384

    llm_json = (
        '{"summary":"Local summary.","agreements":[],'
        '"contradictions":[],"researchGaps":[],"citations":[]}'
    )
    mock_response = _make_openai_response(llm_json)

    mock_bm25 = MagicMock()
    mock_bm25.is_ready = True
    mock_bm25.search.return_value = sufficient_chunks
    mock_qp_client = _make_mock_query_processor_client(mock_embedding)

    mock_analysis_client = AsyncMock()
    mock_analysis_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("app.agents.query_processor.AsyncOpenAI", return_value=mock_qp_client), \
         patch("app.agents.query_expander.AsyncOpenAI", return_value=mock_qp_client), \
         patch("app.agents.cache_checker.answer_cache.lookup", new_callable=AsyncMock, return_value=None), \
         patch("app.agents.retriever.vector_store.query", new_callable=AsyncMock, return_value=sufficient_chunks), \
         patch("app.agents.retriever.vector_store.query_by_embedding", new_callable=AsyncMock, return_value=sufficient_chunks), \
         patch("app.agents.retriever.bm25_index", mock_bm25), \
         patch("app.agents.reranker_agent.reranker.rerank", return_value=[dict(c, rerank_score=1.0) for c in sufficient_chunks]), \
         patch("app.agents.analysis_agent.AsyncOpenAI", return_value=mock_analysis_client), \
         patch("app.agents.storage_agent.answer_cache.store", new_callable=AsyncMock), \
         patch("app.agents.external_search_agent._call_mcp_tool", new_callable=AsyncMock, return_value=[]):

        result = await run_research_pipeline("What are transformers?")

    assert result["summary"] == "Local summary."
    assert "id" in result
    assert "createdAt" in result
    assert result["question"] == "What are transformers?"
    assert result["externalPapersFetched"] is False
    assert result["newPapersCount"] == 0
    assert result["cacheHit"] is False
    assert "confidenceScore" in result


@pytest.mark.asyncio
async def test_supervisor_skips_external_when_chunks_present_even_if_insufficient() -> None:
    """Low confidence but reranked chunks exist: answer from library, MCP not called."""
    from app.agents.supervisor import run_research_pipeline

    weak = [_make_chunk("w1", distance=0.92), _make_chunk("w2", distance=0.93)]
    mock_embedding = [0.1] * 384
    llm_json = (
        '{"summary":"From library despite low confidence.","agreements":[],'
        '"contradictions":[],"researchGaps":[],"citations":[]}'
    )
    mock_response = _make_openai_response(llm_json)

    mock_bm25 = MagicMock()
    mock_bm25.is_ready = True
    mock_bm25.search.return_value = []
    mock_qp_client = _make_mock_query_processor_client(mock_embedding)

    mock_analysis_client = AsyncMock()
    mock_analysis_client.chat.completions.create = AsyncMock(return_value=mock_response)

    mock_mcp = AsyncMock(return_value=[])

    with patch("app.agents.query_processor.AsyncOpenAI", return_value=mock_qp_client), \
         patch("app.agents.query_expander.AsyncOpenAI", return_value=mock_qp_client), \
         patch("app.agents.cache_checker.answer_cache.lookup", new_callable=AsyncMock, return_value=None), \
         patch("app.agents.retriever.vector_store.query", new_callable=AsyncMock, return_value=weak), \
         patch("app.agents.retriever.vector_store.query_by_embedding", new_callable=AsyncMock, return_value=weak), \
         patch("app.agents.retriever.bm25_index", mock_bm25), \
         patch(
             "app.agents.reranker_agent.reranker.rerank",
             return_value=[dict(c, rerank_score=-4.0) for c in weak],
         ), \
         patch("app.agents.external_search_agent._call_mcp_tool", mock_mcp), \
         patch("app.agents.analysis_agent.AsyncOpenAI", return_value=mock_analysis_client), \
         patch("app.agents.storage_agent.answer_cache.store", new_callable=AsyncMock):

        result = await run_research_pipeline("niche topic low similarity")

    mock_mcp.assert_not_called()
    assert result["externalPapersFetched"] is False
    assert result["summary"] == "From library despite low confidence."


@pytest.mark.asyncio
async def test_supervisor_external_path() -> None:
    """When the library returns no chunks, external search is triggered."""
    from app.agents.supervisor import run_research_pipeline

    mock_embedding = [0.1] * 384

    llm_json = (
        '{"summary":"External summary.","agreements":[],'
        '"contradictions":[],"researchGaps":[],"citations":[]}'
    )
    mock_response = _make_openai_response(llm_json)

    mock_bm25 = MagicMock()
    mock_bm25.is_ready = True
    mock_bm25.search.return_value = []

    mcp_paper = {
        "title": "External Paper",
        "authors": ["X"],
        "published_date": "2022-01-01",
        "abstract": "Abstract text",
        "doi": "",
        "url": "",
        "paper_id": "arxiv:ext1",
    }

    async def mock_mcp_tool(tool_name: str, args: dict) -> list[dict]:
        if tool_name == "search_arxiv":
            return [mcp_paper]
        return []

    mock_qp_client = _make_mock_query_processor_client(mock_embedding)
    mock_analysis_client = AsyncMock()
    mock_analysis_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("app.agents.query_processor.AsyncOpenAI", return_value=mock_qp_client), \
         patch("app.agents.query_expander.AsyncOpenAI", return_value=mock_qp_client), \
         patch("app.agents.cache_checker.answer_cache.lookup", new_callable=AsyncMock, return_value=None), \
         patch("app.agents.retriever.vector_store.query", new_callable=AsyncMock, return_value=[]), \
         patch("app.agents.retriever.vector_store.query_by_embedding", new_callable=AsyncMock, return_value=[]), \
         patch("app.agents.retriever.bm25_index", mock_bm25), \
         patch("app.agents.reranker_agent.reranker.rerank", return_value=[]), \
         patch("app.agents.external_search_agent._call_mcp_tool", side_effect=mock_mcp_tool), \
         patch("app.agents.process_agent.ingest_paper", new_callable=AsyncMock, return_value=2), \
         patch("app.agents.analysis_agent.vector_store.query", new_callable=AsyncMock, return_value=[]), \
         patch("app.agents.analysis_agent.AsyncOpenAI", return_value=mock_analysis_client), \
         patch("app.agents.storage_agent.answer_cache.store", new_callable=AsyncMock):

        result = await run_research_pipeline("novel topic with no local papers")

    assert result["question"] == "novel topic with no local papers"
    assert result["externalPapersFetched"] is True
    assert result["newPapersCount"] == 1
    assert result["cacheHit"] is False
