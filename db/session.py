"""
db/session.py — SQLAlchemy 2.0 Session Factory for PatentPilot AI

Provides a typed session factory and engine connection using psycopg2-binary.
Loads DATABASE_URL from .env.
"""

import os
from typing import Generator
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://patentpilot:patentpilot@localhost:5432/patentpilot"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


def get_db() -> Generator[Session, None, None]:
    """Dependency for obtaining a DB session, ensuring proper closure."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
