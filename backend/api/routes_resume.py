"""
Resume upload + session-creation endpoints.

Routes stay thin: validate input, delegate to services, shape the
response via schemas.py. No business logic lives here.
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session as DBSession

from backend.db.database import get_session
from backend.ingestion.role_topics import ROLE_TOPICS
from backend.models.schemas import RoleOption, SessionCreateResponse
from backend.services import resume_service, session_service

router = APIRouter(prefix="/api/resume", tags=["resume"])

ALLOWED_EXTENSIONS = (".pdf", ".txt")


@router.get("/roles", response_model=list[RoleOption])
def list_roles():
    """Roles are scoped to what the provided knowledge base actually covers."""
    display_names = {
        "ai_ml_engineer": "AI / ML Engineer",
        "data_scientist_applied_ml": "Data Scientist / Applied ML Engineer",
        "advanced_ml_researcher": "Advanced ML Researcher",
    }
    return [
        RoleOption(role_id=role_id, display_name=display_names.get(role_id, role_id))
        for role_id in ROLE_TOPICS.keys()
    ]


@router.post("/upload", response_model=SessionCreateResponse)
async def upload_resume(
    role: str = Form(...),
    file: UploadFile = File(...),
    db: DBSession = Depends(get_session),
):
    if role not in ROLE_TOPICS:
        raise HTTPException(status_code=400, detail=f"Unknown role '{role}'")

    filename = file.filename or ""
    if not filename.lower().endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail="Resume must be a .pdf or .txt file",
        )

    raw_text, extracted_skills = await resume_service.process_resume_upload(file)

    if not raw_text.strip():
        raise HTTPException(
            status_code=422,
            detail="Could not extract any text from the uploaded resume",
        )

    return session_service.create_session(db, role, filename, raw_text, extracted_skills)