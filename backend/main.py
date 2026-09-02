"""
FastAPI application entrypoint. Contains ONLY app wiring -- no business
logic, no route handlers beyond a health check. Run with:

    uvicorn backend.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes_interview import router as interview_router
from backend.api.routes_resume import router as resume_router
from backend.db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # create SQLite tables if they don't exist yet
    yield


app = FastAPI(
    title="AI-Powered Candidate Screening System",
    description="Role-based technical interview simulation via a RAG pipeline over role-specific textbooks.",
    version="0.1.0",
    lifespan=lifespan,
)

# React dev server (Vite default port). Tighten this before any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resume_router)
app.include_router(interview_router)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}