from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    chroma_db_path: str = "./chroma_db"
    chroma_collection_name: str = "research_papers"
    embedding_model: str = "text-embedding-3-small"
    relevance_threshold: float = 0.7
    min_relevant_chunks: int = 5
    chunk_size: int = 1000
    chunk_overlap: int = 200
    upload_dir: str = "./uploads"
    max_file_size_mb: int = 50
    frontend_url: str = "http://localhost:3000"
    results_store_path: str = "./research_results.json"


settings = Settings()
