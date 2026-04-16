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
    embedding_model: str = "text-embedding-3-small"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    relevance_threshold: float = 0.7
    chunk_size: int = 512
    chunk_overlap: int = 64

    # Upload / storage
    upload_dir: str = "./uploads"
    max_file_size_mb: int = 50

    # CORS
    frontend_url: str = "http://localhost:3000"

    # Answer cache
    answer_cache_similarity_threshold: float = 0.90

    # Confidence score weights (must sum to 1.0)
    confidence_weight_rerank: float = 0.4
    confidence_weight_similarity: float = 0.35
    confidence_weight_diversity: float = 0.25


settings = Settings()
