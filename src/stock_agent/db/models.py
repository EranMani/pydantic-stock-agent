"""SQLAlchemy ORM models for the stock analyst agent.

Defines the declarative Base and two tables:
- StockReportRecord  → stock_reports  (persisted analysis results)
- AnalysisJobRecord  → analysis_jobs  (job lifecycle tracking for Celery workers)

Score columns use Numeric(4, 1) — never Float — to prevent precision drift in
PostgreSQL (e.g. 7.1 stored as 7.09999... with Float). Numeric stores exact decimals.

Base is imported by migrations/env.py to enable Alembic autogenerate.
Base is imported by db/session.py (Step 40) for the lifespan create_all in dev mode.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, Integer, JSON, Numeric, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all ORM models in this project."""


class StockReportRecord(Base):
    """Persisted result of a completed stock analysis.

    Stores the full StockReport as JSON alongside denormalised score and
    recommendation columns for fast querying without JSON parsing.
    """

    __tablename__ = "stock_reports"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        doc="Surrogate primary key.",
    )
    ticker: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        doc="Stock ticker symbol (e.g. 'AAPL'). Indexed for ticker-based lookups.",
    )
    company_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Full company name resolved at analysis time (e.g. 'Apple Inc.').",
    )
    report_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        doc="Full StockReport serialised as JSON — source of truth for all report fields.",
    )
    fundamental_score: Mapped[Decimal] = mapped_column(
        Numeric(4, 1),
        nullable=False,
        doc="Fundamental pipeline score [1.0, 10.0]. Denormalised from report_json for queries.",
    )
    technical_score: Mapped[Decimal] = mapped_column(
        Numeric(4, 1),
        nullable=False,
        doc="Technical pipeline score [1.0, 10.0]. Denormalised from report_json for queries.",
    )
    weighted_score: Mapped[Decimal] = mapped_column(
        Numeric(4, 1),
        nullable=False,
        doc="Final combined score [1.0, 10.0]. Denormalised from report_json for queries.",
    )
    recommendation: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        doc="Agent recommendation: BUY, WATCH, or AVOID.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when this record was inserted.",
    )

    def __repr__(self) -> str:
        """Human-readable representation for debugging."""
        return (
            f"<StockReportRecord id={self.id} ticker={self.ticker!r} "
            f"score={self.weighted_score} rec={self.recommendation!r}>"
        )


class AnalysisJobRecord(Base):
    """Tracks the lifecycle of a Celery analysis job.

    job_id is the stable identifier shared between the database record and the
    Redis progress key (job:{job_id}:progress). It must never change mid-job.
    Celery's own task_id changes per sub-task in a chord and must NOT be used here.
    """

    __tablename__ = "analysis_jobs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        doc="Surrogate primary key.",
    )
    job_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        unique=True,
        index=True,
        doc="Stable UUID identifying this job across DB and Redis. Format: 8-4-4-4-12.",
    )
    ticker: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        doc="Stock ticker symbol this job is analysing.",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        doc="Job lifecycle state: pending | running | complete | failed.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when the job was enqueued.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="UTC timestamp of last status update. Updated by the Celery task on every transition.",
    )

    def __repr__(self) -> str:
        """Human-readable representation for debugging."""
        return (
            f"<AnalysisJobRecord id={self.id} job_id={self.job_id!r} "
            f"ticker={self.ticker!r} status={self.status!r}>"
        )
