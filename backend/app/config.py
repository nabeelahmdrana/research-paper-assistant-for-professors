from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    chroma_db_path: str = "./chroma_db"
    chroma_collection_name: str = "research_papers"
    embedding_model: str = "all-MiniLM-L6-v2"
    relevance_threshold: float = 0.7
    min_relevant_chunks: int = 5
    chunk_size: int = 1000
    chunk_overlap: int = 200
    upload_dir: str = "./uploads"
    max_file_size_mb: int = 50
    frontend_url: str = "http://localhost:3000"

    class Config:
        env_file = ".env"


settings = Settings()
