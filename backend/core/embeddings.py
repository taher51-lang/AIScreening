"""
Shared embedding function factory. Both ingestion (ingest.py) and
retrieval (services/retrieval_service.py) must use the exact same
embedding function -- same provider, same model -- or vectors won't be
comparable in the Chroma collection.

Provider is switchable via `EMBEDDING_PROVIDER` env var (config.py):
  - "local"  (default): sentence-transformers, runs on-device. No API
    key, no rate limits, but pulls in torch (disk-heavy install).
  - "cohere": Cohere embed API. Lighter install, but free-tier keys hit
    429 rate limits fast during bulk textbook ingestion -- kept available
    as a fallback/option, not the current default, for exactly that reason.
"""

from backend.config import get_settings


def get_embedding_function():
    settings = get_settings()

    if settings.embedding_provider == "cohere":
        from langchain_cohere import CohereEmbeddings

        if not settings.cohere_api_key:
            raise RuntimeError(
                "COHERE_API_KEY is not set. Add it to your .env file, "
                "or set EMBEDDING_PROVIDER=local to use sentence-transformers instead."
            )
        return CohereEmbeddings(
            model=settings.cohere_embedding_model_name,
            cohere_api_key=settings.cohere_api_key,
        )

    if settings.embedding_provider == "local":
        from langchain_huggingface import HuggingFaceEmbeddings

        return HuggingFaceEmbeddings(model_name=settings.embedding_model_name)

    raise ValueError(
        f"Unknown embedding_provider '{settings.embedding_provider}'. "
        "Use 'local' or 'cohere'."
    )