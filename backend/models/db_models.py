"""
SQLModel ORM table definitions.

Design notes:
- UUIDs (as strings) are used for all primary keys instead of auto-increment
  ints, since session_id is generated client-side-visible and referenced
  across the resume upload -> interview -> summary lifecycle.
- `retrieved_context` and `extracted_skills` are stored as JSON columns
  (via sqlmodel's Column(JSON)) rather than normalized join tables, to keep
  traceability cheap: each Question row carries exactly the chunks that
  produced it (source_book, page_number, section_title, chunk_text).
- Answer is a separate table from Question (not a column on Question)
  because a question can exist in an "asked but not yet answered" state
  during a live session — this models the interview lifecycle correctly.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


def generate_uuid() -> str:
    return str(uuid.uuid4())


class SessionStatus(str, Enum):
    in_progress = "in_progress"
    completed = "completed"


class DifficultyLevel(str, Enum):
    foundational = "foundational"  # role-topic not matched in resume -> baseline question
    advanced = "advanced"          # role-topic matched to a resume skill -> deep-dive question


class Session(SQLModel, table=True):
    """One candidate's interview session, scoped by a generated UUID (no auth)."""

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    role: str = Field(index=True)  # e.g. "ai_ml_engineer", "data_scientist_applied_ml"

    resume_filename: str
    resume_raw_text: Optional[str] = None

    # Structured extraction output: {"skills": [...], "technologies": [...], "domains": [...]}
    extracted_skills: dict = Field(default_factory=dict, sa_column=Column(JSON))

    status: SessionStatus = Field(default=SessionStatus.in_progress, index=True)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class Question(SQLModel, table=True):
    """A single generated interview question, with full retrieval provenance."""

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    session_id: str = Field(foreign_key="session.id", index=True)

    sequence_number: int  # order within the interview (1, 2, 3, ...)
    topic: str            # the role-topic this question targeted, e.g. "bayesian learning"

    question_text: str

    # List of {source_book, page_number, section_title, chunk_text} dicts —
    # gives traceability of exactly which retrieved chunks produced this question.
    retrieved_context: list = Field(default_factory=list, sa_column=Column(JSON))

    difficulty: Optional[DifficultyLevel] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)


class Answer(SQLModel, table=True):
    """A candidate's response to a given question. One-to-one with Question."""

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    question_id: str = Field(foreign_key="question.id", unique=True, index=True)

    answer_text: str
    submitted_at: datetime = Field(default_factory=datetime.utcnow)


class SessionSummary(SQLModel, table=True):
    """Final structured summary + insights for a completed session."""

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    session_id: str = Field(foreign_key="session.id", unique=True, index=True)

    summary_text: str

    # e.g. {"strengths": [...], "gaps": [...], "topic_breakdown": {...}}
    insights: dict = Field(default_factory=dict, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=datetime.utcnow)