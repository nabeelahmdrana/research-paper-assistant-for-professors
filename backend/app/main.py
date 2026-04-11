from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.tools import vector_store

app = FastAPI(title="Research Paper Assistant API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Phase 4 (api-developer): uncomment and register routers
# from app.api import research, papers
# app.include_router(research.router, prefix="/api")
# app.include_router(papers.router, prefix="/api")


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
