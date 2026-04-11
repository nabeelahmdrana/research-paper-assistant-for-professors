from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

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
    return {"status": "ok", "chromadb": False, "paper_count": 0}
