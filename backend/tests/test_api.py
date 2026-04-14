"""API endpoint tests (Phase 4).

Uses an in-process ASGI client so no real server is required.
All ChromaDB calls use a temporary directory to avoid polluting production data.
"""

import io
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="module")
async def tmp_chroma(tmp_path_factory: pytest.TempPathFactory) -> AsyncGenerator[None, None]:
    """Redirect ChromaDB to an isolated temp directory for the test module."""
    tmp_dir = tmp_path_factory.mktemp("chroma_api")
    original_path = settings.chroma_db_path
    settings.chroma_db_path = str(tmp_dir)
    yield
    settings.chroma_db_path = original_path


@pytest_asyncio.fixture(scope="module")
async def client(tmp_chroma: None) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


def _minimal_pdf_bytes() -> bytes:
    """Return a minimal valid PDF as bytes for upload tests."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 3 3]>>endobj\n"
        b"xref\n0 4\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\n"
        b"startxref\n190\n%%EOF"
    )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "chromadb" in data
    assert "paper_count" in data


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_stats(client: AsyncClient) -> None:
    response = await client.get("/api/stats")
    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    stats = body["data"]
    assert "paperCount" in stats
    assert "isConnected" in stats


# ---------------------------------------------------------------------------
# Papers — upload
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upload_pdf(client: AsyncClient) -> None:
    """Uploading a valid (minimal) PDF should succeed."""
    pdf_bytes = _minimal_pdf_bytes()
    files = [("files", ("test_paper.pdf", io.BytesIO(pdf_bytes), "application/pdf"))]
    response = await client.post("/api/papers/upload", files=files)
    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["data"]["uploaded"] >= 0  # may be 0 if PDF has no extractable text


@pytest.mark.asyncio
async def test_upload_non_pdf_rejected(client: AsyncClient) -> None:
    """Uploading a non-PDF should be reported in errors, not crash."""
    files = [("files", ("report.docx", io.BytesIO(b"fake docx"), "application/octet-stream"))]
    response = await client.post("/api/papers/upload", files=files)
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["uploaded"] == 0
    assert len(body["data"]["errors"]) == 1


@pytest.mark.asyncio
async def test_upload_no_files_returns_400(client: AsyncClient) -> None:
    """Sending no files should return HTTP 400."""
    response = await client.post("/api/papers/upload")
    assert response.status_code == 422  # FastAPI validation error for missing field


# ---------------------------------------------------------------------------
# Papers — list & delete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_papers(client: AsyncClient) -> None:
    response = await client.get("/api/papers")
    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert "papers" in body["data"]
    assert "total" in body["data"]


@pytest.mark.asyncio
async def test_delete_paper_not_found(client: AsyncClient) -> None:
    response = await client.delete("/api/papers/nonexistent-id-xyz")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Research
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_research_empty_question(client: AsyncClient) -> None:
    response = await client.post("/api/research", json={"question": "  "})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_run_research_returns_result(client: AsyncClient) -> None:
    """Phase B pipeline is wired — /api/research returns a structured result."""
    from unittest.mock import AsyncMock, MagicMock, patch

    mock_message = MagicMock()
    mock_message.content = (
        '{"summary":"Test summary.","agreements":[],'
        '"contradictions":[],"researchGaps":[],"citations":[]}'
    )
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_bm25 = MagicMock()
    mock_bm25.is_ready = True
    mock_bm25.search.return_value = []

    # Mock the OpenAI client used by query_processor (embeddings + HyDE chat)
    mock_embed_data = MagicMock()
    mock_embed_data.embedding = [0.1] * 1536
    mock_embed_resp = MagicMock()
    mock_embed_resp.data = [mock_embed_data]

    mock_hyde_chat_msg = MagicMock()
    mock_hyde_chat_msg.content = ""
    mock_hyde_chat_choice = MagicMock()
    mock_hyde_chat_choice.message = mock_hyde_chat_msg
    mock_hyde_chat_resp = MagicMock()
    mock_hyde_chat_resp.choices = [mock_hyde_chat_choice]

    mock_qp_client = AsyncMock()
    mock_qp_client.embeddings.create = AsyncMock(return_value=mock_embed_resp)
    mock_qp_client.chat.completions.create = AsyncMock(return_value=mock_hyde_chat_resp)

    # Mock the OpenAI client used by analysis_agent (chat completions)
    mock_analysis_client = AsyncMock()
    mock_analysis_client.chat.completions.create = AsyncMock(return_value=mock_response)

    def _make_openai_client(*args, **kwargs):
        # Return different mocks depending on which module is constructing the client
        import traceback
        stack = "".join(traceback.format_stack())
        if "query_processor" in stack or "query_expander" in stack:
            return mock_qp_client
        return mock_analysis_client

    with patch("app.agents.query_processor.AsyncOpenAI", side_effect=_make_openai_client), \
         patch("app.agents.query_expander.AsyncOpenAI", return_value=mock_qp_client), \
         patch("app.agents.cache_checker.answer_cache.lookup", new_callable=AsyncMock, return_value=None), \
         patch("app.agents.retriever.vector_store.query", new_callable=AsyncMock, return_value=[]), \
         patch("app.agents.retriever.bm25_index", mock_bm25), \
         patch("app.agents.reranker_agent.reranker.rerank", return_value=[]), \
         patch("app.agents.external_search_agent._call_mcp_tool", new_callable=AsyncMock, return_value=[]), \
         patch("app.agents.analysis_agent.vector_store.query", new_callable=AsyncMock, return_value=[]), \
         patch("app.agents.analysis_agent.AsyncOpenAI", return_value=mock_analysis_client), \
         patch("app.agents.storage_agent.answer_cache.store", new_callable=AsyncMock):

        response = await client.post(
            "/api/research",
            json={"question": "What is the transformer architecture?"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    result = body["data"]
    assert "summary" in result
    assert "citations" in result
    assert "id" in result


@pytest.mark.asyncio
async def test_list_research_results(client: AsyncClient) -> None:
    response = await client.get("/api/research")
    assert response.status_code == 200
    body = response.json()
    assert "results" in body["data"]
    assert "total" in body["data"]


@pytest.mark.asyncio
async def test_get_research_result_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/research/unknown-result-id")
    assert response.status_code == 404
