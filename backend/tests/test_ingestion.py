# Phase 3 (backend agent): ingestion tests
# Covers: PDF parsing, text chunking, ChromaDB storage, query, list, delete

import io
import os
import shutil
import tempfile

import pytest
import pytest_asyncio
from pypdf import PdfWriter

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def test_chroma_dir():
    """Create an isolated temporary ChromaDB directory for the test module."""
    tmp = tempfile.mkdtemp(prefix="test_chroma_")
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture(scope="module")
def patch_settings(test_chroma_dir):
    """Override settings so tests use the isolated ChromaDB path."""
    import app.config as config_module

    original_path = config_module.settings.chroma_db_path
    original_collection = config_module.settings.chroma_collection_name

    config_module.settings.chroma_db_path = test_chroma_dir
    config_module.settings.chroma_collection_name = "test_papers"

    yield config_module.settings

    config_module.settings.chroma_db_path = original_path
    config_module.settings.chroma_collection_name = original_collection


@pytest.fixture(scope="module")
def sample_pdf_path():
    """Create a minimal in-memory PDF and write it to a temp file."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)

    # pypdf does not provide a simple 'add text' API at this level;
    # we write raw PDF content stream to add readable text to the page.
    content_stream = (
        b"BT\n"
        b"/F1 12 Tf\n"
        b"72 720 Td\n"
        b"(Attention Is All You Need) Tj\n"
        b"0 -20 Td\n"
        b"(Authors: Vaswani et al.) Tj\n"
        b"0 -20 Td\n"
        b"(Abstract: The transformer architecture uses self-attention mechanisms.) Tj\n"
        b"0 -20 Td\n"
        b"(It replaces recurrent and convolutional layers entirely.) Tj\n"
        b"0 -20 Td\n"
        b"(This allows for much greater parallelization during training.) Tj\n"
        b"ET\n"
    )

    # Add font resource and content stream directly via compress_content_streams
    from pypdf.generic import (
        ArrayObject,
        ContentStream,
        DecodedStreamObject,
        DictionaryObject,
        NameObject,
        RectangleObject,
    )

    # Embed text as a raw content stream on the page object
    stream_obj = DecodedStreamObject()
    stream_obj.set_data(content_stream)
    page.replace_contents(stream_obj)

    # Write to a temp file
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    writer.write(tmp)
    tmp.close()

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
