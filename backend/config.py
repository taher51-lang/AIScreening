"""
Centralized configuration via environment variables (.env supported).
Nothing in services/api should read os.environ directly -- import
get_settings() instead, so config stays in one auditable place.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "sqlite:///./interview.db"
    db_echo: bool = False
    embedding_provider: str = 'local'
    # Vector store
    chroma_persist_dir: str = "./chroma_db"

    # LLM / embeddings
    # LLM: Groq-hosted openai/gpt-oss-120b (fast inference, OpenAI-compatible API).
    groq_api_key: str | None = None
    llm_model_name: str = "openai/gpt-oss-120b"

    # Embeddings: Cohere embed API (avoids local torch/sentence-transformers
    # install weight). Cohere v3 models require input_type at call time --
    # "search_document" when embedding ingested chunks, "search_query" when
    # embedding a query at retrieval time. See core/vector_store.py.
    cohere_api_key: str | None = None
    embedding_model_name: str = "embed-english-v3.0"

    # Interview behavior
    questions_per_session: int = 6


@lru_cache
def get_settings() -> Settings:
    return Settings()