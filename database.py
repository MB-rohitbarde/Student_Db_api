"""
database.py
------------
Centralized database configuration and session management for the application.

This module creates the SQLAlchemy engine, a session factory, and the declarative
base used by ORM models. It also provides `get_db()`, a FastAPI dependency that
opens and reliably closes a database session per request.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base


SQLALCHEMY_DATABASE_URL = "sqlite:///./app.db"  # Local SQLite file in project root

# Create the engine that manages DB connections.
# For SQLite, `check_same_thread=False` allows access from multiple threads
# (e.g., FastAPI workers) within the same process.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# Session factory used to create short-lived sessions per request/task.
# - autocommit=False: we control transactions explicitly.
# - autoflush=False: avoid unintended flushes; flush happens on commit or when needed.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()  # Base class for all ORM models


def get_db():
    """
    FastAPI dependency that yields a database session.

    Why:
    - Provides a fresh session per request to avoid cross-request state.
    - Ensures the session is closed even if the request raises an exception.

    Usage:
    - Add `db: Session = Depends(get_db)` to route handlers.
    """
    db = SessionLocal()  # open a new session for the current request/task
    try:
        yield db  # yield control so route logic can use the session
    finally:
        db.close()  # always close to free connections/resources



