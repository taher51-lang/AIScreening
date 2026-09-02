"""
Pluggable retrieval strategies, all behind one interface:

    strategy.retrieve(query: str, role: str, k: int) -> list[RetrievedChunk]

Swap the active strategy via `RETRIEVAL_STRATEGY` env var (see config.py)
without touching retrieval_service.py or the graph -- lets you A/B test
which performs best on this specific corpus.

Three implementations:
  - SemanticRetrievalStrategy: plain top-k cosine similarity.
  - MMRRetrievalStrategy: Maximal Marginal Relevance -- fetches a larger
    candidate pool, then greedily picks results that are relevant but
    diverse from each other, avoiding near-duplicate chunks from a
    section that repeats the same term many times.
  - HybridRetrievalStrategy: BM25 (sparse, exact-term) + semantic (dense),
    combined via LangChain's EnsembleRetriever. Included for completeness
    / experimentation, though for this corpus (dense, non-rare topic
    terms repeated throughout a chapter) BM25 is expected to add little --
    see design discussion. Cheap to test and discard if it doesn't help.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from langchain_core.documents import Document

from backend.core.vector_store import get_vector_store


@dataclass
class RetrievedChunk:
    text: str
    source_book: str
    page_number: int
    section_title: str


def _to_retrieved_chunk(doc: Document) -> RetrievedChunk:
    meta = doc.metadata
    return RetrievedChunk(
        text=doc.page_content,
        source_book=meta.get("source_book", "unknown"),
        page_number=meta.get("page_number", -1),
        section_title=meta.get("section_title", "unknown"),
    )


class RetrievalStrategy(ABC):
    @abstractmethod
    def retrieve(
        self, query: str, role: str, k: int, fetch_k: int
    ) -> list[RetrievedChunk]:
        ...


class SemanticRetrievalStrategy(RetrievalStrategy):
    """Plain top-k cosine similarity search, filtered by role."""

    def __init__(self, embedding_function):
        self.vector_store = get_vector_store(embedding_function)

    def retrieve(self, query: str, role: str, k: int, fetch_k: int) -> list[RetrievedChunk]:
        docs = self.vector_store.similarity_search(
            query, k=k, filter={"role_tag": role}
        )
        return [_to_retrieved_chunk(d) for d in docs]


class MMRRetrievalStrategy(RetrievalStrategy):
    """
    Maximal Marginal Relevance: fetch `fetch_k` candidates, then greedily
    select `k` that are relevant to the query but diverse from each other.
    Default strategy -- see module docstring for why.
    """

    def __init__(self, embedding_function):
        self.vector_store = get_vector_store(embedding_function)

    def retrieve(self, query: str, role: str, k: int, fetch_k: int) -> list[RetrievedChunk]:
        docs = self.vector_store.max_marginal_relevance_search(
            query, k=k, fetch_k=fetch_k, filter={"role_tag": role}
        )
        return [_to_retrieved_chunk(d) for d in docs]


class HybridRetrievalStrategy(RetrievalStrategy):
    """
    BM25 (sparse) + semantic (dense) fused via EnsembleRetriever.

    BM25Retriever needs the full document set up front (it's not a live
    index like Chroma), so we fetch all chunks for a role from Chroma once
    and cache the resulting BM25Retriever per role for the process
    lifetime -- rebuilding it per-query would be wasteful.
    """

    def __init__(self, embedding_function):
        self.embedding_function = embedding_function
        self.vector_store = get_vector_store(embedding_function)
        self._bm25_cache: dict[str, "BM25Retriever"] = {}

    def _get_bm25_retriever(self, role: str, k: int):
        from langchain_community.retrievers import BM25Retriever

        if role not in self._bm25_cache:
            raw = self.vector_store.get(where={"role_tag": role})
            documents = [
                Document(page_content=text, metadata=meta)
                for text, meta in zip(raw["documents"], raw["metadatas"])
            ]
            if not documents:
                raise ValueError(
                    f"No ingested chunks found for role '{role}' -- "
                    "run ingestion before using hybrid retrieval."
                )
            self._bm25_cache[role] = BM25Retriever.from_documents(documents)

        self._bm25_cache[role].k = k
        return self._bm25_cache[role]

    def retrieve(self, query: str, role: str, k: int, fetch_k: int) -> list[RetrievedChunk]:
        bm25_retriever = self._get_bm25_retriever(role, k)
        semantic_retriever = self.vector_store.as_retriever(
            search_kwargs={"k": k, "filter": {"role_tag": role}}
        )

        # Retrieve from both sources independently
        bm25_docs = bm25_retriever.invoke(query)
        semantic_docs = semantic_retriever.invoke(query)

        # Simple reciprocal rank fusion: score each doc by 1/(rank+1),
        # combine scores across both lists, return top-k by fused score.
        scores: dict[str, tuple[float, Document]] = {}
        for rank, doc in enumerate(bm25_docs):
            key = doc.page_content[:200]
            prev_score = scores.get(key, (0.0, doc))[0]
            scores[key] = (prev_score + 0.5 / (rank + 1), doc)
        for rank, doc in enumerate(semantic_docs):
            key = doc.page_content[:200]
            prev_score = scores.get(key, (0.0, doc))[0]
            scores[key] = (prev_score + 0.5 / (rank + 1), doc)

        ranked = sorted(scores.values(), key=lambda x: x[0], reverse=True)
        docs = [doc for _, doc in ranked[:k]]
        return [_to_retrieved_chunk(d) for d in docs]



_STRATEGY_REGISTRY = {
    "semantic": SemanticRetrievalStrategy,
    "mmr": MMRRetrievalStrategy,
    "hybrid": HybridRetrievalStrategy,
}


def get_retrieval_strategy(strategy_name: str, embedding_function) -> RetrievalStrategy:
    if strategy_name not in _STRATEGY_REGISTRY:
        raise ValueError(
            f"Unknown retrieval strategy '{strategy_name}'. "
            f"Choose from: {list(_STRATEGY_REGISTRY.keys())}"
        )
    return _STRATEGY_REGISTRY[strategy_name](embedding_function)