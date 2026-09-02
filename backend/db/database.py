"""
Database engine + session management.

Keeps DB wiring in one place so services never construct engines/sessions
themselves -- they depend on `get_session` (a FastAPI dependency) instead.
This is what keeps DB access swappable later (e.g. SQLite -> Postgres)
without touching service code.
"""

from sqlmodel import SQLModel, Session, create_engine

from backend.config import get_settings

settings = get_settings()

# check_same_thread=False is required for SQLite when used with FastAPI's
# threaded request handling; safe here since SQLModel/SQLAlchemy manages
# a connection pool per-session, not a single shared connection.
engine = create_engine(
    settings.database_url,
    echo=settings.db_echo,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)


def init_db() -> None:
    """Create all tables. Call once at app startup."""
    # Import models so their table metadata is registered on SQLModel.metadata
    # before create_all runs.
    from backend.models import db_models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session():
    """FastAPI dependency: yields a DB session, closed automatically after the request."""
    with Session(engine) as session:
        yield session