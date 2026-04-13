import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import papers, research
from app.config import settings
from app.tools import vector_store

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-warm the embedding model and ChromaDB on startup."""
    try:
        logger.info("Pre-loading embedding model and ChromaDB collection...")
        vector_store.get_collection()
        logger.info("Embedding model and ChromaDB ready.")
    except Exception as exc:
        logger.warning("Startup pre-warm failed (non-fatal): %s", exc)
    yield


app = FastAPI(title="Research Paper Assistant API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(papers.router, prefix="/api")
app.include_router(research.router, prefix="/api")


@app.get("/api/health")
async def health() -> dict:
    chroma_ok = False
    count = 0
    try:
        count = await vector_store.paper_count()
        chroma_ok = True
    except Exception:
        pass
    return {"status": "ok", "chromadb": chroma_ok, "paper_count": count}
