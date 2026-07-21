"""
db/models.py — SQLAlchemy 2.0 ORM Models for PatentPilot AI

Defines persistent tables corresponding to PatentPilotState:
- patents
- research_papers
- technical_entities
- reports
- approvals
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base declarative class for all models."""
    pass


class Patent(Base):
    __tablename__ = "patents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patent_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    inventors: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    ipc_codes: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    pdf_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class ResearchPaper(Base):
    __tablename__ = "research_papers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    paper_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    authors: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class TechnicalEntity(Base):
    __tablename__ = "technical_entities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    algorithms: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    datasets: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    frameworks: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    inventors: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    ipc_codes: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    keywords: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_query: Mapped[str] = mapped_column(Text, nullable=False)
    search_keywords: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    novelty_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    novelty_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prior_art: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    technical_entities: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    report_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    approval_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    approval_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    approvals: Mapped[List["Approval"]] = relationship("Approval", back_populates="report", cascade="all, delete-orphan")


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id: Mapped[str] = mapped_column(String(36), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    decision: Mapped[str] = mapped_column(String(50), nullable=False)  # "approved", "rejected", "re-run"
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    report: Mapped["Report"] = relationship("Report", back_populates="approvals")
