"""
Retrieval service: decides which topic to ask about next (topic planning),
builds a natural-language query from that topic + resume context, and
retrieves grounding chunks via whichever RetrievalStrategy is configured
(core/retrieval_strategies.py).

The active strategy is a process-lifetime singleton (important for
HybridRetrievalStrategy, which caches a BM25 index per role internally --
rebuilding it per request would be wasteful).
"""

import random
from dataclasses import dataclass
from functools import lru_cache

from backend.config import get_settings
from backend.core.embeddings import get_embedding_function
from backend.core.retrieval_strategies import RetrievedChunk, get_retrieval_strategy
from backend.ingestion.role_topics import ROLE_TOPICS


@dataclass
class TopicPlan:
    topic: str
    difficulty: str  # "advanced" | "foundational"
    matched_skill: str | None  # the resume skill that justified "advanced", if any


@lru_cache
def get_strategy():
    """Process-lifetime singleton retrieval strategy (public -- used by
    both retrieve_context() below and the LangGraph retrieve node)."""
    settings = get_settings()
    embedding_fn = get_embedding_function()
    return get_retrieval_strategy(settings.retrieval_strategy, embedding_fn)


def plan_topic(
    role: str, extracted_skills: dict, session_id: str, sequence_number: int
) -> TopicPlan:
    """
    Deterministically picks the topic for a given question slot, as a pure
    function of (role, resume skills, session_id, sequence_number) --
    no DB storage needed, reproducible within a session, varies across
    sessions via the session_id seed.

    Difficulty: "advanced" if the topic has a matching resume skill/domain,
    else "foundational".
    """
    if role not in ROLE_TOPICS:
        raise ValueError(f"Unknown role '{role}'")

    topics = list(ROLE_TOPICS[role]["topics"])
    rng = random.Random(session_id)  # seeded -> stable ordering per session
    rng.shuffle(topics)

    topic = topics[(sequence_number - 1) % len(topics)]

    resume_terms = set(extracted_skills.get("skills", []))
    matched_skill = next(
        (term for term in resume_terms if term in topic or topic in term),
        None,
    )
    # Also check for partial word overlap (e.g. resume has "deep learning",
    # topic is "neural networks and deep learning").
    if matched_skill is None:
        topic_words = set(topic.lower().split())
        for term in resume_terms:
            if set(term.lower().split()) & topic_words:
                matched_skill = term
                break

    difficulty = "advanced" if matched_skill else "foundational"
    return TopicPlan(topic=topic, difficulty=difficulty, matched_skill=matched_skill)


def build_query(topic_plan: TopicPlan) -> str:
    """Shapes the topic into a natural-language query, per difficulty."""
    if topic_plan.difficulty == "advanced":
        return (
            f"{topic_plan.topic}, with practical application and implementation "
            f"details relevant to {topic_plan.matched_skill}"
        )
    return f"core concepts and theoretical foundations of {topic_plan.topic}"


def retrieve_chunks(topic_plan: TopicPlan, role: str) -> list[RetrievedChunk]:
    """
    Retrieval given an already-computed TopicPlan -- the piece the graph's
    retrieve node calls directly, so topic planning isn't recomputed.
    """
    settings = get_settings()
    query = build_query(topic_plan)
    strategy = get_strategy()
    return strategy.retrieve(
        query=query,
        role=role,
        k=settings.retrieval_k,
        fetch_k=settings.retrieval_fetch_k,
    )


def retrieve_context(
    role: str, extracted_skills: dict, session_id: str, sequence_number: int
) -> tuple[TopicPlan, list[RetrievedChunk]]:
    """
    Full retrieval step for one question slot: plan the topic, build the
    query, retrieve grounding chunks via the configured strategy.
    """
    topic_plan = plan_topic(role, extracted_skills, session_id, sequence_number)
    chunks = retrieve_chunks(topic_plan, role)
    return topic_plan, chunks