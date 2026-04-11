from pydantic import BaseModel


class Paper(BaseModel):
    id: str
    title: str
    authors: list[str]
    year: int | str
    source: str  # "local" | "external" | "pdf" | "doi" | "arxiv"
    abstract: str = ""
    doi: str | None = None
    url: str | None = None
    date_added: str = ""


class ResearchQuery(BaseModel):
    question: str


class Citation(BaseModel):
    index: int
    title: str
    authors: list[str]
    year: int | str
    doi: str | None = None
    url: str | None = None
    source: str  # "local" | "external"


class ResearchResult(BaseModel):
    id: str
    question: str
    created_at: str
    summary: str
    agreements: list[str]
    contradictions: list[str]
    research_gaps: list[str]
    citations: list[Citation]


class DbStats(BaseModel):
    paper_count: int
    db_size_mb: float
    is_connected: bool


class ApiResponse(BaseModel):
    data: dict | list | None = None
    error: str | None = None
    status: int = 200
