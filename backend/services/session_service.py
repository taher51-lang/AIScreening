"""
Session lifecycle logic: creating sessions, fetching/advancing the current
question, recording answers, and assembling the final summary.

Question *generation* itself (retrieval + LLM call) is delegated to the
LangGraph pipeline in graph/interview_graph.py, which doesn't exist yet --
those calls are marked TODO below. Everything here that's pure DB/session
bookkeeping is fully implemented and tested.
"""

from datetime import datetime

from fastapi import HTTPException
from sqlmodel import Session as DBSession
from sqlmodel import select

from backend.config import get_settings
from backend.models.db_models import (
    Answer,
    Question,
    Session,
    SessionStatus,
    SessionSummary,
)
from backend.models.schemas import (
    AnswerSubmitRequest,
    AnswerSubmitResponse,
    QuestionResponse,
    SessionCreateResponse,
    SessionSummaryResponse,
)

settings = get_settings()


def _to_question_response(question: Question) -> QuestionResponse:
    return QuestionResponse(
        question_id=question.id,
        sequence_number=question.sequence_number,
        topic=question.topic,
        question_text=question.question_text,
        difficulty=question.difficulty.value if question.difficulty else None,
    )


def create_session(
    db: DBSession,
    role: str,
    filename: str,
    raw_text: str,
    extracted_skills: dict,
) -> SessionCreateResponse:
    session = Session(
        role=role,
        resume_filename=filename,
        resume_raw_text=raw_text,
        extracted_skills=extracted_skills,
        status=SessionStatus.in_progress,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return SessionCreateResponse(
        session_id=session.id,
        role=session.role,
        extracted_skills=session.extracted_skills,
        status=session.status.value,
        created_at=session.created_at,
    )


def _get_session_or_404(db: DBSession, session_id: str) -> Session:
    session = db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return session


def _get_latest_question(db: DBSession, session_id: str) -> Question | None:
    return db.exec(
        select(Question)
        .where(Question.session_id == session_id)
        .order_by(Question.sequence_number.desc())
    ).first()


def _get_answer_for_question(db: DBSession, question_id: str) -> Answer | None:
    return db.exec(select(Answer).where(Answer.question_id == question_id)).first()


def get_current_question(db: DBSession, session_id: str) -> QuestionResponse:
    session = _get_session_or_404(db, session_id)

    if session.status == SessionStatus.completed:
        raise HTTPException(status_code=400, detail="Session is already completed")

    latest = _get_latest_question(db, session_id)

    if latest is not None and _get_answer_for_question(db, latest.id) is None:
        # Candidate already has an unanswered question pending -- return it
        # rather than generating a new one.
        return _to_question_response(latest)

    if latest is None:
        # First question of the session.
        # TODO: delegate to graph/interview_graph.py once built:
        #   question = interview_graph.generate_first_question(db, session)
        raise NotImplementedError(
            "Wire up interview_graph.generate_first_question here"
        )

    # All prior questions answered but session not marked complete --
    # this shouldn't normally happen (submit_answer should have advanced
    # or completed the session), but handle defensively.
    raise HTTPException(
        status_code=409,
        detail="Session state is inconsistent -- no pending question found",
    )


def submit_answer(
    db: DBSession, session_id: str, payload: AnswerSubmitRequest
) -> AnswerSubmitResponse:
    session = _get_session_or_404(db, session_id)

    if session.status == SessionStatus.completed:
        raise HTTPException(status_code=400, detail="Session is already completed")

    question = db.get(Question, payload.question_id)
    if question is None or question.session_id != session_id:
        raise HTTPException(status_code=404, detail="Question not found for this session")

    if _get_answer_for_question(db, question.id) is not None:
        raise HTTPException(status_code=400, detail="Question has already been answered")

    answer = Answer(question_id=question.id, answer_text=payload.answer_text)
    db.add(answer)
    db.commit()

    if question.sequence_number >= settings.questions_per_session:
        session.status = SessionStatus.completed
        session.completed_at = datetime.utcnow()
        db.add(session)
        db.commit()
        return AnswerSubmitResponse(
            accepted=True, next_question=None, session_status=session.status.value
        )

    # TODO: delegate to graph/interview_graph.py once built:
    #   next_question = interview_graph.generate_next_question(db, session, question, answer)
    raise NotImplementedError(
        "Wire up interview_graph.generate_next_question here"
    )


def get_summary(db: DBSession, session_id: str) -> SessionSummaryResponse:
    session = _get_session_or_404(db, session_id)

    if session.status != SessionStatus.completed:
        raise HTTPException(status_code=400, detail="Session is not yet completed")

    questions = db.exec(
        select(Question)
        .where(Question.session_id == session_id)
        .order_by(Question.sequence_number)
    ).all()

    qa_pairs = []
    for q in questions:
        answer = _get_answer_for_question(db, q.id)
        qa_pairs.append(
            {
                "question_text": q.question_text,
                "answer_text": answer.answer_text if answer else None,
                "topic": q.topic,
                "difficulty": q.difficulty.value if q.difficulty else None,
            }
        )

    existing_summary = db.exec(
        select(SessionSummary).where(SessionSummary.session_id == session_id)
    ).first()

    if existing_summary is None:
        # TODO: delegate to graph/interview_graph.py or a dedicated
        # summary_service once built:
        #   existing_summary = interview_graph.generate_summary(db, session, qa_pairs)
        raise NotImplementedError("Wire up summary generation here")

    return SessionSummaryResponse(
        session_id=session.id,
        role=session.role,
        summary_text=existing_summary.summary_text,
        insights=existing_summary.insights,
        questions_and_answers=qa_pairs,
    )