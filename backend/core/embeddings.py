"""
Shared embedding function factory. Both ingestion (ingest.py) and
retrieval (services/retrieval_service.py, built later) must use the exact
same embedding function -- same provider, same model, same object type --
or vectors won't be comparable in the Chroma collection.
"""

from backend.config import get_settings


def get_embedding_function():
    """
    Cohere embed API -- avoids installing torch/sentence-transformers
    locally. langchain_cohere.CohereEmbeddings automatically applies
    input_type="search_document" inside embed_documents() (ingestion call
    site) and input_type="search_query" inside embed_query() (retrieval
    call site) -- same instance is correct for both.
    """
    from langchain_cohere import CohereEmbeddings

    settings = get_settings()
    if not settings.cohere_api_key:
        raise RuntimeError(
            "COHERE_API_KEY is not set. Add it to your .env file."
        )
    return CohereEmbeddings(
        model=settings.embedding_model_name,
        cohere_api_key=settings.cohere_api_key,
    )