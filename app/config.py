from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

load_dotenv()

class Settings(BaseSettings):
    app_name: str = "AI Customer Support Platform"
    app_version: str = "0.1.0"
    debug: bool = False

    # API
    host: str = "0.0.0.0"
    port: int = 8000

    # Auth
    auth_enabled: bool = True
    api_key: Optional[str] = "rag-secret-api-key-2026"
    supabase_jwt_secret: Optional[str] = None

    # PostgreSQL
    postgres_url: str = "postgresql://postgres:postgres@localhost:5432/customer_support"

    # Supabase
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: Optional[str] = None
    qdrant_collection: str = "knowledge_base"
    embedding_dim: int = 384

    # Groq
    groq_api_key: Optional[str] = None
    groq_model: str = "openai/gpt-oss-120b"
    groq_max_tokens: int = 1024
    groq_temperature: float = 0.2

    # Embeddings
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Cross-Encoder reranker
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    reranker_top_k: int = 5

    # Retrieval
    hybrid_dense_weight: float = 0.5
    hybrid_sparse_weight: float = 0.5
    rrf_k: int = 60
    retrieval_top_k: int = 20

    # LangGraph
    max_retries: int = 3

    # Opik
    opik_api_key: Optional[str] = None
    opik_workspace: Optional[str] = None
    opik_project_name: str = "ai-customer-support"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

settings = Settings()
