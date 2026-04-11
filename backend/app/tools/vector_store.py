# Phase 3 (backend agent): implement ChromaDB operations here
# All ChromaDB access in the project goes through this file only

from app.config import settings


def get_collection():  # type: ignore[return]
    """Initialize and return the ChromaDB collection."""
    # TODO (backend agent): implement ChromaDB init
    # import chromadb
    # client = chromadb.PersistentClient(path=settings.chroma_db_path)
    # return client.get_or_create_collection(settings.chroma_collection_name)
    raise NotImplementedError("backend agent: implement get_collection()")


async def add_documents(chunks: list[dict]) -> None:
    """Add document chunks to ChromaDB."""
    raise NotImplementedError("backend agent: implement add_documents()")


async def query(text: str, n_results: int = 10) -> list[dict]:
    """Query ChromaDB for relevant chunks."""
    raise NotImplementedError("backend agent: implement query()")


async def list_papers() -> list[dict]:
    """List all unique papers stored in ChromaDB."""
    raise NotImplementedError("backend agent: implement list_papers()")


async def delete_paper(paper_id: str) -> bool:
    """Delete all chunks for a given paper."""
    raise NotImplementedError("backend agent: implement delete_paper()")


async def paper_count() -> int:
    """Return the number of unique papers stored."""
    raise NotImplementedError("backend agent: implement paper_count()")
