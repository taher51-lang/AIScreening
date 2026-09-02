"""
Thin wrapper around a persistent Chroma collection.

Kept in `core/` (not `ingestion/`) because both the ingestion script and
the retrieval service (built later) need the same access pattern:
get_or_create the collection, embed, upsert/query.
"""

from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings

from backend.config import get_settings

settings = get_settings()

COLLECTION_NAME = "interview_knowledge_base"


def get_vector_store(embedding_function: Embeddings) -> Chroma:
    """
    Returns a persistent Chroma vector store instance.

    `embedding_function` is injected rather than constructed here, since the
    embedding provider (OpenAI / local sentence-transformers / other) is
    still an open decision -- this wrapper stays agnostic to that choice.
    """
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embedding_function,
        persist_directory=settings.chroma_persist_dir,
    )