from dotenv import load_dotenv
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional

load_dotenv()

class Settings(BaseSettings):
    app_name: str = "AI Customer Support Platform"
    app_version: str = "0.1.0"
    debug: bool = False

    # API
    host: str = "0.0.0.0"
    port: int = 8000
    # Comma-separated list of allowed browser origins ("*" allows any origin, without credentials)
    cors_origins: str = "*"

    # Auth
    auth_enabled: bool = True
    # Accept both API_KEY and BACKEND_API_KEY (the name used by render.yaml and the frontend)
    api_key: Optional[str] = Field(default=None, validation_alias=AliasChoices("API_KEY", "BACKEND_API_KEY"))
    supabase_jwt_secret: Optional[str] = None

    # PostgreSQL
    postgres_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/customer_support",
        validation_alias=AliasChoices("POSTGRES_URL", "DATABASE_URL"),
    )

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
    # Accept both GROQ_MODEL and MODEL_NAME (the name used by render.yaml)
    groq_model: str = Field(default="openai/gpt-oss-120b", validation_alias=AliasChoices("GROQ_MODEL", "MODEL_NAME"))
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
    max_retries: int = 1

    # Opik
    opik_api_key: Optional[str] = None
    opik_workspace: Optional[str] = None
    opik_project_name: str = "ai-customer-support"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        populate_by_name=True,
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

settings = Settings()
