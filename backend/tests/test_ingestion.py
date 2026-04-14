# Phase 3 (backend agent): ingestion tests
# Covers: PDF parsing, text chunking, ChromaDB storage, query, list, delete

import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def test_chroma_dir():
    """Create an isolated temporary ChromaDB directory for the test module."""
    tmp = tempfile.mkdtemp(prefix="test_chroma_")
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


def _make_mock_embedding_fn():
    """Return a ChromaDB-compatible callable that produces deterministic 1536-d vectors.

    ChromaDB validates that the embedding function's __call__ has the exact
    signature (self, input: Documents) -> Embeddings.  A plain MagicMock fails
    that check, so we use a real class here.
    """
    class _StubEmbedFn:
        def _vecs(self, texts: list[str]) -> list[list[float]]:
            return [[float(hash(t) % 1000) / 1000.0] + [0.0] * 1535 for t in texts]

        def __call__(self, input: list[str]) -> list[list[float]]:  # noqa: A002
            return self._vecs(input)

        # ChromaDB >= 0.5 uses embed_query() for search and embed_documents()
        # for indexing.  Both delegate to the same deterministic stub.
        def embed_query(self, input: list[str]) -> list[list[float]]:  # noqa: A002
            return self._vecs(input)

        def embed_documents(self, input: list[str]) -> list[list[float]]:  # noqa: A002
            return self._vecs(input)

        # ChromaDB >= 0.5 calls name() during conflict validation.
        # Returning "default" bypasses the conflict check entirely.
        def name(self) -> str:
            return "default"

        @property
        def is_legacy(self) -> bool:
            return False

    return _StubEmbedFn()


@pytest.fixture(scope="module")
def patch_settings(test_chroma_dir):
    """Override settings so tests use an isolated ChromaDB path and a stub
    embedding function that avoids real OpenAI API calls."""
    import app.config as config_module
    import app.tools.vector_store as vs_module

    original_path = config_module.settings.chroma_db_path
    original_collection = config_module.settings.chroma_collection_name

    config_module.settings.chroma_db_path = test_chroma_dir
    config_module.settings.chroma_collection_name = "test_papers"

    # Reset the module-level collection singletons so they re-initialize with
    # the new path and our stub embedding function.
    vs_module._client = None
    vs_module._embedding_fn = None
    vs_module._chunks_collection = None
    vs_module._papers_meta_collection = None
    vs_module._answers_collection = None

    mock_embed_fn = _make_mock_embedding_fn()

    with patch("app.tools.vector_store._get_embedding_fn", return_value=mock_embed_fn):
        yield config_module.settings

    # Restore settings and reset singletons
    config_module.settings.chroma_db_path = original_path
    config_module.settings.chroma_collection_name = original_collection
    vs_module._client = None
    vs_module._embedding_fn = None
    vs_module._chunks_collection = None
    vs_module._papers_meta_collection = None
    vs_module._answers_collection = None


@pytest.fixture(scope="module")
def sample_pdf_path():
    """Create a minimal PDF with readable text using pymupdf (fitz)."""
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    lines = [
        "Attention Is All You Need",
        "Authors: Vaswani et al.",
        "Abstract: The transformer architecture uses self-attention mechanisms.",
        "It replaces recurrent and convolutional layers entirely.",
        "This allows for much greater parallelization during training.",
    ]
    y = 720
    for line in lines:
        page.insert_text((72, y), line, fontsize=12)
        y -= 20

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()
    doc.save(tmp.name)
    doc.close()

    yield tmp.name

    os.unlink(tmp.name)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_pdf(patch_settings, sample_pdf_path):
    """Ingesting a PDF should produce at least one chunk stored in ChromaDB."""
    from app.ingestion.pdf_ingester import ingest_pdf

    metadata = {
        "paper_id": "test_paper_001",
        "title": "Attention Is All You Need",
        "authors": "Vaswani et al.",
        "year": "2017",
        "source": "local",
        "doi": "",
    }

    chunk_count = await ingest_pdf(sample_pdf_path, metadata)
    assert chunk_count > 0, f"Expected at least 1 chunk, got {chunk_count}"


@pytest.mark.asyncio
async def test_query(patch_settings):
    """After ingesting, querying with a relevant term should return results."""
    from app.tools.vector_store import query

    results = await query("attention mechanism transformer", n_results=5)
    assert isinstance(results, list), "query() should return a list"
    assert len(results) > 0, "Expected at least one result after ingestion"

    first = results[0]
    assert "id" in first
    assert "text" in first
    assert "metadata" in first
    assert "distance" in first


@pytest.mark.asyncio
async def test_list_papers(patch_settings):
    """After ingesting, the paper should appear in list_papers()."""
    from app.tools.vector_store import list_papers

    papers = await list_papers()
    assert isinstance(papers, list), "list_papers() should return a list"
    assert len(papers) > 0, "Expected at least one paper in the list"

    paper_ids = [p["paper_id"] for p in papers]
    assert "test_paper_001" in paper_ids, (
        f"test_paper_001 not found in paper IDs: {paper_ids}"
    )


@pytest.mark.asyncio
async def test_delete_paper(patch_settings):
    """After deleting a paper, it should no longer appear in list_papers()."""
    from app.tools.vector_store import delete_paper, list_papers

    deleted = await delete_paper("test_paper_001")
    assert deleted is True, "delete_paper() should return True when paper exists"

    papers = await list_papers()
    paper_ids = [p["paper_id"] for p in papers]
    assert "test_paper_001" not in paper_ids, (
        "Deleted paper should not appear in list_papers()"
    )


@pytest.mark.asyncio
async def test_paper_count(patch_settings, sample_pdf_path):
    """paper_count() should correctly reflect the number of unique papers."""
    from app.tools.vector_store import paper_count
    from app.ingestion.pdf_ingester import ingest_pdf

    # Start from a known state: ingest one paper
    metadata = {
        "paper_id": "test_paper_count_001",
        "title": "Count Test Paper",
        "authors": "Test Author",
        "year": "2024",
        "source": "local",
        "doi": "",
    }
    await ingest_pdf(sample_pdf_path, metadata)

    count = await paper_count()
    assert count >= 1, f"Expected at least 1 paper, got {count}"
