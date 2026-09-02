"""
Thin wrapper around a persistent Chroma collection.

Kept in `core/` (not `ingestion/`) because both the ingestion script and
the retrieval service (built later) need the same access pattern:
get_or_create the collection, embed, upsert/query.
"""

from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings

from backend.config import get_settings

import chromadb.api.rust
import chromadb.api.shared_system_client
import chromadb.config
import chromadb.telemetry.product
from chromadb.api import ServerAPI

# 1. Patch RustBindingsAPI.stop to avoid AttributeError: 'RustBindingsAPI' object has no attribute 'bindings'
def _safe_rust_stop(self):
    if hasattr(self, "bindings"):
        try:
            del self.bindings
        except Exception:
            pass

chromadb.api.rust.RustBindingsAPI.stop = _safe_rust_stop

# 2. Patch SharedSystemClient._create_system_if_not_exists to safely handle missing system entries
_orig_create_system = chromadb.api.shared_system_client.SharedSystemClient._create_system_if_not_exists


def _safe_create_system_if_not_exists(cls, identifier: str, settings):
    try:
        return _orig_create_system(identifier, settings)
    except Exception:
        if identifier in cls._identifier_to_system:
            return cls._identifier_to_system[identifier]
        new_system = chromadb.config.System(settings)
        cls._identifier_to_system[identifier] = new_system
        try:
            new_system.instance(chromadb.telemetry.product.ProductTelemetryClient)
            new_system.instance(ServerAPI)
            new_system.start()
        except Exception:
            pass
        cls._identifier_to_system[identifier] = new_system
        return new_system


chromadb.api.shared_system_client.SharedSystemClient._create_system_if_not_exists = classmethod(
    _safe_create_system_if_not_exists
)


COLLECTION_NAME = "interview_knowledge_base"


_vector_store_instance: Chroma | None = None



def get_vector_store(embedding_function: Embeddings) -> Chroma:
    """
    Returns a persistent Chroma vector store instance.

    `embedding_function` is injected rather than constructed here, since the
    embedding provider (OpenAI / local sentence-transformers / other) is
    still an open decision -- this wrapper stays agnostic to that choice.
    """
    global _vector_store_instance
    if _vector_store_instance is None:
        import chromadb

        settings = get_settings()
        persist_dir = str(Path(settings.chroma_persist_dir).resolve())
        client = chromadb.PersistentClient(path=persist_dir)
        _vector_store_instance = Chroma(
            client=client,
            collection_name=COLLECTION_NAME,
            embedding_function=embedding_function,
        )
    return _vector_store_instance