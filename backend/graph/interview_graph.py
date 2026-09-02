"""
LangGraph pipeline for generating one interview question at a time.

Deliberately pure w.r.t. persistence: this module takes (role, resume
context, sequence_number) in and returns a GeneratedQuestion out. It
never touches the DB -- session_service.py is responsible for persisting
the result as a Question row. This keeps "orchestrating the AI/ML
pipeline" and "interfacing with storage systems" as genuinely separate
responsibilities (per the assignment's backend expectations), not just
nominally split across files.

Graph shape: START -> plan_topic -> retrieve -> generate_question -> END

A single linear pipeline is enough here -- the "adaptive" surface of the
assignment (continue vs. complete, which question comes next) is a
session-level decision already handled in session_service.py, not
something that needs extra graph branching for a 48-hour scope.
"""

from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from backend.config import get_settings
from backend.services import retrieval_service


class GraphState(TypedDict):
    role: str
    extracted_skills: dict
    session_id: str
    sequence_number: int

    topic: str
    difficulty: str
    matched_skill: str | None
    retrieved_context: list[dict]  # [{source_book, page_number, section_title, chunk_text}]
    question_text: str


def _plan_topic_node(state: GraphState) -> dict:
    topic_plan = retrieval_service.plan_topic(
        role=state["role"],
        extracted_skills=state["extracted_skills"],
        session_id=state["session_id"],
        sequence_number=state["sequence_number"],
    )
    return {
        "topic": topic_plan.topic,
        "difficulty": topic_plan.difficulty,
        "matched_skill": topic_plan.matched_skill,
    }


def _retrieve_node(state: GraphState) -> dict:
    from backend.services.retrieval_service import TopicPlan, retrieve_chunks

    topic_plan = TopicPlan(
        topic=state["topic"],
        difficulty=state["difficulty"],
        matched_skill=state["matched_skill"],
    )
    chunks = retrieve_chunks(topic_plan, role=state["role"])

    retrieved_context = [
        {
            "source_book": c.source_book,
            "page_number": c.page_number,
            "section_title": c.section_title,
            "chunk_text": c.text,
        }
        for c in chunks
    ]
    return {"retrieved_context": retrieved_context}


_QUESTION_SYSTEM_PROMPT = """\
You are a friendly senior engineer conducting a practical screening interview \
for a "{role}" position. You generate ONE short interview question at a time.

STRICT rules — violating any of these is a failure:
- Output ONLY the question text. No preamble, numbering, or answer.
- The question MUST be 1–2 sentences. Never more.
- Use plain, conversational English. NO LaTeX, NO mathematical notation, \
NO multi-part sub-questions (a), (b), (c).
- Ask about ONE specific concept from the reference material. Do NOT combine \
multiple topics into a single question.
- A competent mid-level engineer should be able to understand the question \
immediately without re-reading it.
- "foundational" difficulty = "What is X?" or "Why does Y matter?" level.
- "advanced" difficulty = a short scenario or "how would you" question — \
still clear and practical, NOT a textbook derivation.
- NEVER ask the candidate to derive formulas, write proofs, or outline \
multi-step algorithms.
"""


_QUESTION_USER_PROMPT = """\
Topic: {topic}
Difficulty: {difficulty}

Reference material (from {role}'s knowledge base):
{context_block}

Generate one SHORT, clear interview question on this topic. \
Remember: 1–2 sentences max, plain English, no math notation.
"""



def _format_context_block(retrieved_context: list[dict]) -> str:
    parts = []
    for i, chunk in enumerate(retrieved_context, start=1):
        parts.append(
            f"[{i}] ({chunk['source_book']}, p.{chunk['page_number']}, "
            f"section: {chunk['section_title']})\n{chunk['chunk_text']}"
        )
    return "\n\n".join(parts) if parts else "(no reference material retrieved)"


def _generate_question_node(state: GraphState) -> dict:
    from langchain_groq import ChatGroq

    settings = get_settings()
    llm = ChatGroq(model=settings.llm_model_name, api_key=settings.groq_api_key)

    system_msg = SystemMessage(
        content=_QUESTION_SYSTEM_PROMPT.format(
            role=state["role"],
            matched_skill=state["matched_skill"] or "no specific match found",
        )
    )
    user_msg = HumanMessage(
        content=_QUESTION_USER_PROMPT.format(
            topic=state["topic"],
            difficulty=state["difficulty"],
            role=state["role"],
            context_block=_format_context_block(state["retrieved_context"]),
        )
    )

    response = llm.invoke([system_msg, user_msg])
    return {"question_text": response.content.strip()}


def _build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("plan_topic", _plan_topic_node)
    graph.add_node("retrieve", _retrieve_node)
    graph.add_node("generate_question", _generate_question_node)

    graph.add_edge(START, "plan_topic")
    graph.add_edge("plan_topic", "retrieve")
    graph.add_edge("retrieve", "generate_question")
    graph.add_edge("generate_question", END)

    return graph.compile()


_compiled_graph = None


def _get_compiled_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = _build_graph()
    return _compiled_graph


class GeneratedQuestion(TypedDict):
    topic: str
    difficulty: str
    question_text: str
    retrieved_context: list[dict]


def generate_question(
    role: str, extracted_skills: dict, session_id: str, sequence_number: int
) -> GeneratedQuestion:
    """
    Runs the full plan -> retrieve -> generate pipeline for one question
    slot. Used for both the first question and every subsequent one --
    session_service.py decides *when* to call this, not this module.
    """
    graph = _get_compiled_graph()
    result = graph.invoke(
        {
            "role": role,
            "extracted_skills": extracted_skills,
            "session_id": session_id,
            "sequence_number": sequence_number,
        }
    )
    return GeneratedQuestion(
        topic=result["topic"],
        difficulty=result["difficulty"],
        question_text=result["question_text"],
        retrieved_context=result["retrieved_context"],
    )


_SUMMARY_SYSTEM_PROMPT = """\
You are a senior technical interviewer writing a structured post-interview \
summary for a "{role}" candidate screening session. Base your assessment \
strictly on the questions and answers provided -- do not invent details.
"""

_SUMMARY_USER_PROMPT = """\
Below is the full transcript of a role-based technical screening interview.

{transcript}

Write a concise summary (3-5 sentences) of the candidate's overall \
performance, then list:
- 2-4 strengths (topics/answers that showed solid understanding)
- 2-4 gaps (topics/answers that were weak, incomplete, or skipped)

Format your response as:
SUMMARY: <summary text>
STRENGTHS: <comma-separated list>
GAPS: <comma-separated list>
"""


def _format_transcript(qa_pairs: list[dict]) -> str:
    parts = []
    for i, qa in enumerate(qa_pairs, start=1):
        answer = qa.get("answer_text") or "(no answer given)"
        parts.append(
            f"Q{i} [{qa.get('topic', 'unknown topic')}, "
            f"{qa.get('difficulty', 'unknown')} difficulty]: {qa['question_text']}\n"
            f"A{i}: {answer}"
        )
    return "\n\n".join(parts)


def _parse_summary_response(text: str) -> tuple[str, list[str], list[str]]:
    """Best-effort parse of the SUMMARY/STRENGTHS/GAPS format; falls back
    gracefully if the model doesn't follow it exactly."""
    summary_text, strengths, gaps = text.strip(), [], []

    for line in text.splitlines():
        line = line.strip()
        if line.upper().startswith("SUMMARY:"):
            summary_text = line.split(":", 1)[1].strip()
        elif line.upper().startswith("STRENGTHS:"):
            strengths = [s.strip() for s in line.split(":", 1)[1].split(",") if s.strip()]
        elif line.upper().startswith("GAPS:"):
            gaps = [g.strip() for g in line.split(":", 1)[1].split(",") if g.strip()]

    return summary_text, strengths, gaps


def generate_summary(role: str, qa_pairs: list[dict]) -> dict:
    """
    Single LLM call over the full transcript -- not a graph, since there's
    no multi-step orchestration needed for a one-shot summarization task.
    Returns {"summary_text": str, "insights": {"strengths": [...], "gaps": [...]}}.
    """
    from langchain_groq import ChatGroq

    settings = get_settings()
    llm = ChatGroq(model=settings.llm_model_name, api_key=settings.groq_api_key)

    system_msg = SystemMessage(content=_SUMMARY_SYSTEM_PROMPT.format(role=role))
    user_msg = HumanMessage(
        content=_SUMMARY_USER_PROMPT.format(transcript=_format_transcript(qa_pairs))
    )

    response = llm.invoke([system_msg, user_msg])
    summary_text, strengths, gaps = _parse_summary_response(response.content)

    return {
        "summary_text": summary_text,
        "insights": {
            "strengths": strengths,
            "gaps": gaps,
            "topic_breakdown": [
                {"topic": qa.get("topic"), "difficulty": qa.get("difficulty")}
                for qa in qa_pairs
            ],
        },
    }