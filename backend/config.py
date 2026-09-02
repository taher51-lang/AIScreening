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

    # Vector store
    chroma_persist_dir: str = "./chroma_db"

    # LLM / embeddings -- provider TBD; keys left optional so the app
    # doesn't crash at import time before a provider is chosen.
    llm_api_key: str | None = None
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Interview behavior
    questions_per_session: int = 6


@lru_cache
def get_settings() -> Settings:
    return Settings()