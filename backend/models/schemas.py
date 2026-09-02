"""
API-facing request/response shapes. Deliberately kept separate from
models/db_models.py (the ORM tables) -- even though some fields overlap,
the API contract and the persistence shape are allowed to evolve
independently. Routes should only ever return these, never raw
SQLModel rows.
"""

from datetime import datetime

from pydantic import BaseModel


class RoleOption(BaseModel):
    role_id: str
    display_name: str


class SessionCreateResponse(BaseModel):
    session_id: str
    role: str
    extracted_skills: dict
    status: str
    created_at: datetime


class QuestionResponse(BaseModel):
    question_id: str
    sequence_number: int
    topic: str
    question_text: str
    difficulty: str | None = None


class AnswerSubmitRequest(BaseModel):
    question_id: str
    answer_text: str


class AnswerSubmitResponse(BaseModel):
    accepted: bool
    next_question: QuestionResponse | None = None
    session_status: str


class SessionSummaryResponse(BaseModel):
    session_id: str
    role: str
    summary_text: str
    insights: dict
    questions_and_answers: list[dict]  # [{question_text, answer_text, topic, difficulty}, ...]