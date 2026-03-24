"""Async CRUD operations for the stock analyst agent database layer.

All functions accept an injected AsyncSession — sessions are never created
inside CRUD functions. This follows the session contract defined in session.py:
one session per HTTP request (via get_session) or one session per Celery task
(via async_session_factory).

All five operations are async and use SQLAlchemy ORM exclusively — no raw SQL.
"""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stock_agent.db.models import AnalysisJobRecord, StockReportRecord
from stock_agent.models.report import StockReport


async def create_job(db: AsyncSession, ticker: str) -> AnalysisJobRecord:
    """Create a new AnalysisJobRecord with status 'pending' for the given ticker.

    Generates a stable UUID job_id that is shared between the database record
    and the Redis progress key (job:{job_id}:progress). Adds, commits, refreshes,
    and returns the persisted ORM object.
    """
    import uuid

    job = AnalysisJobRecord(
        job_id=str(uuid.uuid4()),
        ticker=ticker.upper(),
        status="pending",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def update_job_status(db: AsyncSession, job_id: UUID, status: str) -> None:
    """Update the status field of an existing AnalysisJobRecord.

    Looks up the record by job_id (string representation of UUID), sets the
    new status value, and commits. No-op if no matching record exists.
    """
    result = await db.execute(
        select(AnalysisJobRecord).where(AnalysisJobRecord.job_id == str(job_id))
    )
    job = result.scalar_one_or_none()
    if job is not None:
        job.status = status
        await db.commit()


async def save_report(
    db: AsyncSession, job_id: UUID, report: StockReport
) -> StockReportRecord:
    """Serialize a StockReport Pydantic model into a StockReportRecord ORM row.

    Denormalises score and recommendation columns from the report for fast
    querying without JSON parsing. Links the record to its parent job via
    the stable job_id. Adds, commits, refreshes, and returns the persisted ORM object.
    """
    record = StockReportRecord(
        ticker=report.ticker,
        company_name=report.company_name,
        # model_dump serializes datetime, Decimal, and nested models to JSON-safe types
        report_json=report.model_dump(mode="json"),
        fundamental_score=Decimal(str(round(report.fundamental_score, 1))),
        technical_score=Decimal(str(round(report.technical_score, 1))),
        weighted_score=Decimal(str(round(report.weighted_score, 1))),
        recommendation=report.recommendation,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def get_report_by_ticker(
    db: AsyncSession, ticker: str
) -> StockReportRecord | None:
    """Query for the most recent StockReportRecord matching the given ticker symbol.

    Orders by created_at descending so the latest analysis is returned first.
    Returns None if no matching record exists.
    """
    result = await db.execute(
        select(StockReportRecord)
        .where(StockReportRecord.ticker == ticker.upper())
        .order_by(StockReportRecord.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def list_recent_jobs(
    db: AsyncSession, limit: int = 20
) -> list[AnalysisJobRecord]:
    """Return the most recent N AnalysisJobRecord rows ordered by created_at descending.

    Defaults to 20 rows. Used by the NiceGUI job history panel to display
    recent analysis activity without loading the full history.
    """
    result = await db.execute(
        select(AnalysisJobRecord)
        .order_by(AnalysisJobRecord.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
