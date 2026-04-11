# Phase 3 (backend agent): implement all Pydantic schemas here
from pydantic import BaseModel


class Paper(BaseModel):
    id: str
    title: str
    authors: list[str]
    year: int
    source: str  # "local" | "external"
    doi: str | None = None


class ResearchQuery(BaseModel):
    question: str


class Citation(BaseModel):
    id: str
    title: str
    authors: list[str]
    year: int
    doi: str | None = None
    source: str


class ResearchResult(BaseModel):
    summary: str
    agreements: list[str]
    contradictions: list[str]
    gaps: list[str]
    citations: list[Citation]


class ApiResponse(BaseModel):
    data: dict | None = None
    error: str | None = None
