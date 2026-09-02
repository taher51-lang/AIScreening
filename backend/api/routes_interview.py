"""
Interview lifecycle endpoints: fetch current/next question, submit an
answer, retrieve the final structured summary. Sessions are identified
by UUID (no auth) per the assumptions documented in the README.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session as DBSession

from backend.db.database import get_session
from backend.models.schemas import (
    AnswerSubmitRequest,
    AnswerSubmitResponse,
    QuestionResponse,
    SessionSummaryResponse,
)
from backend.services import session_service

router = APIRouter(prefix="/api/interview", tags=["interview"])


@router.get("/{session_id}/current-question", response_model=QuestionResponse)
def get_current_question(session_id: str, db: DBSession = Depends(get_session)):
    return session_service.get_current_question(db, session_id)


@router.post("/{session_id}/answer", response_model=AnswerSubmitResponse)
def submit_answer(
    session_id: str,
    payload: AnswerSubmitRequest,
    db: DBSession = Depends(get_session),
):
    return session_service.submit_answer(db, session_id, payload)


@router.get("/{session_id}/summary", response_model=SessionSummaryResponse)
def get_summary(session_id: str, db: DBSession = Depends(get_session)):
    return session_service.get_summary(db, session_id)