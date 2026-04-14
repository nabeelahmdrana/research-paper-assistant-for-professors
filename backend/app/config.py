from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # OpenAI-compatible LLM
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o"

    # ChromaDB
    chroma_db_path: str = "./chroma_db"
    # Legacy single-collection name kept so any existing data is not orphaned
    chroma_collection_name: str = "research_papers"

    # Retrieval settings
    embedding_model: str = "all-MiniLM-L6-v2"
    relevance_threshold: float = 0.7
    min_relevant_chunks: int = 5
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # Upload / storage
    upload_dir: str = "./uploads"
    max_file_size_mb: int = 50

    # CORS
    frontend_url: str = "http://localhost:3000"

    # Results persistence (flat JSON — kept for backward compat)
    results_store_path: str = "./research_results.json"

    # Answer cache
    answer_cache_similarity_threshold: float = 0.93


settings = Settings()
