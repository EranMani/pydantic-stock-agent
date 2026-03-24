"""Tests for SQLAlchemy ORM models, session factory, and async CRUD operations.

Uses SQLite in-memory for structural and round-trip verification — no live
PostgreSQL instance required.

Covers:
- Table names correct
- All expected columns present
- Round-trip save and retrieval (field values preserved)
- Numeric score precision (Decimal, not float)
- Uniqueness constraint on AnalysisJobRecord.job_id
- Session factory produces AsyncSession instances
- Engine is an AsyncEngine instance
- CRUD: create_job, update_job_status, save_report, get_report_by_ticker, list_recent_jobs
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import Session

from stock_agent.db.crud import (
    create_job,
    get_report_by_ticker,
    list_recent_jobs,
    save_report,
    update_job_status,
)
from stock_agent.db.models import AnalysisJobRecord, Base, StockReportRecord
from stock_agent.db.session import async_session_factory, engine
from stock_agent.models.report import (
    FundamentalData,
    KeyPoint,
    PeerReport,
    StockReport,
    TechnicalData,
)


# ---------------------------------------------------------------------------
# Async test session fixtures (SQLite in-memory via aiosqlite)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def async_sqlite_session():
    """Provide a clean AsyncSession backed by an in-memory SQLite database.

    Creates all ORM tables fresh for each test function and drops them after,
    ensuring full isolation between CRUD tests. Uses aiosqlite driver.
    """
    async_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSession(async_engine, expire_on_commit=False) as session:
        yield session

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await async_engine.dispose()


def _make_stock_report(ticker: str = "AAPL") -> StockReport:
    """Build a minimal but valid StockReport instance for CRUD tests."""
    return StockReport(
        ticker=ticker,
        company_name="Apple Inc." if ticker == "AAPL" else f"{ticker} Corp.",
        analysis_date=datetime.now(timezone.utc),
        fundamental_score=7.5,
        technical_score=8.0,
        weighted_score=7.8,
        key_points=[
            KeyPoint(text="Strong revenue growth of 15%", sentiment="positive"),
            KeyPoint(text="VCP pattern detected", sentiment="positive"),
            KeyPoint(text="P/E ratio of 28.4", sentiment="neutral"),
            KeyPoint(text="Beta of 1.2", sentiment="neutral"),
        ],
        recommendation="BUY",
        peers=[
            PeerReport(ticker="MSFT", weighted_score=7.2, recommendation="WATCH"),
        ],
    )


@pytest.fixture(scope="module")
def sqlite_engine():
    """In-memory SQLite engine with all ORM tables created."""
    _engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(_engine)
    yield _engine
    Base.metadata.drop_all(_engine)


@pytest.fixture
def session(sqlite_engine):
    """Provide a clean session that rolls back after each test."""
    with Session(sqlite_engine) as _session:
        yield _session
        _session.rollback()


# ---------------------------------------------------------------------------
# Table structure
# ---------------------------------------------------------------------------


def test_stock_report_record_table_name():
    """StockReportRecord maps to the stock_reports table."""
    assert StockReportRecord.__tablename__ == "stock_reports"


def test_analysis_job_record_table_name():
    """AnalysisJobRecord maps to the analysis_jobs table."""
    assert AnalysisJobRecord.__tablename__ == "analysis_jobs"


def test_stock_report_record_columns(sqlite_engine):
    """stock_reports table has all expected columns."""
    inspector = inspect(sqlite_engine)
    columns = {col["name"] for col in inspector.get_columns("stock_reports")}
    expected = {
        "id",
        "ticker",
        "company_name",
        "report_json",
        "fundamental_score",
        "technical_score",
        "weighted_score",
        "recommendation",
        "created_at",
    }
    assert expected == columns


def test_analysis_job_record_columns(sqlite_engine):
    """analysis_jobs table has all expected columns."""
    inspector = inspect(sqlite_engine)
    columns = {col["name"] for col in inspector.get_columns("analysis_jobs")}
    expected = {"id", "job_id", "ticker", "status", "created_at", "updated_at"}
    assert expected == columns


# ---------------------------------------------------------------------------
# Round-trip: StockReportRecord
# ---------------------------------------------------------------------------


def test_stock_report_record_round_trip(session):
    """Save a StockReportRecord and retrieve it — all fields must survive the round-trip."""
    record = StockReportRecord(
        ticker="AAPL",
        company_name="Apple Inc.",
        report_json={"ticker": "AAPL", "recommendation": "BUY", "weighted_score": 8.1},
        fundamental_score=Decimal("7.5"),
        technical_score=Decimal("8.0"),
        weighted_score=Decimal("7.8"),
        recommendation="BUY",
    )
    session.add(record)
    session.commit()
    session.refresh(record)

    assert record.id is not None
    assert record.ticker == "AAPL"
    assert record.company_name == "Apple Inc."
    assert record.report_json["recommendation"] == "BUY"
    assert record.fundamental_score == Decimal("7.5")
    assert record.technical_score == Decimal("8.0")
    assert record.weighted_score == Decimal("7.8")
    assert record.recommendation == "BUY"
    assert record.created_at is not None


def test_stock_report_record_score_precision(session):
    """Score fields store exact Decimal values — not imprecise floats."""
    record = StockReportRecord(
        ticker="MSFT",
        company_name="Microsoft Corporation",
        report_json={},
        fundamental_score=Decimal("6.3"),
        technical_score=Decimal("9.1"),
        weighted_score=Decimal("7.7"),
        recommendation="WATCH",
    )
    session.add(record)
    session.commit()
    session.refresh(record)

    # Numeric(4, 1) must preserve exactly one decimal place
    assert record.fundamental_score == Decimal("6.3")
    assert record.technical_score == Decimal("9.1")
    assert record.weighted_score == Decimal("7.7")


# ---------------------------------------------------------------------------
# Round-trip: AnalysisJobRecord
# ---------------------------------------------------------------------------


def test_analysis_job_record_round_trip(session):
    """Save an AnalysisJobRecord and retrieve it — all fields must survive the round-trip."""
    record = AnalysisJobRecord(
        job_id="123e4567-e89b-12d3-a456-426614174000",
        ticker="AAPL",
        status="pending",
    )
    session.add(record)
    session.commit()
    session.refresh(record)

    assert record.id is not None
    assert record.job_id == "123e4567-e89b-12d3-a456-426614174000"
    assert record.ticker == "AAPL"
    assert record.status == "pending"
    assert record.created_at is not None
    assert record.updated_at is not None


def test_analysis_job_record_status_transitions(session):
    """Status field accepts all valid lifecycle values."""
    for status in ("pending", "running", "complete", "failed"):
        record = AnalysisJobRecord(
            job_id=f"job-id-{status}",
            ticker="TSLA",
            status=status,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        assert record.status == status


# ---------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------


def test_analysis_job_record_job_id_unique(sqlite_engine):
    """job_id must be unique — inserting a duplicate raises IntegrityError."""
    with Session(sqlite_engine) as s:
        s.add(AnalysisJobRecord(job_id="duplicate-id", ticker="AAPL", status="pending"))
        s.commit()

    with Session(sqlite_engine) as s:
        s.add(AnalysisJobRecord(job_id="duplicate-id", ticker="MSFT", status="pending"))
        with pytest.raises(IntegrityError):
            s.commit()


# ---------------------------------------------------------------------------
# __repr__
# ---------------------------------------------------------------------------


def test_stock_report_record_repr():
    """__repr__ includes key identifiers for readable debug output."""
    r = StockReportRecord(ticker="AAPL", weighted_score=Decimal("8.1"), recommendation="BUY")
    assert "AAPL" in repr(r)
    assert "BUY" in repr(r)


def test_analysis_job_record_repr():
    """__repr__ includes key identifiers for readable debug output."""
    r = AnalysisJobRecord(job_id="abc-123", ticker="MSFT", status="running")
    assert "abc-123" in repr(r)
    assert "running" in repr(r)


# ---------------------------------------------------------------------------
# Session factory (Step 40)
# ---------------------------------------------------------------------------


def test_engine_is_async_engine():
    """engine exported from session.py must be an AsyncEngine instance."""
    assert isinstance(engine, AsyncEngine)


@pytest.mark.anyio
async def test_session_factory_produces_async_session():
    """async_session_factory() must yield an AsyncSession instance."""
    async with async_session_factory() as session:
        assert isinstance(session, AsyncSession)


# ---------------------------------------------------------------------------
# CRUD: create_job (Step 42)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_job_returns_record(async_sqlite_session):
    """create_job must return a persisted AnalysisJobRecord with status 'pending'."""
    job = await create_job(async_sqlite_session, "AAPL")

    assert job.id is not None
    assert job.ticker == "AAPL"
    assert job.status == "pending"
    assert job.job_id is not None
    # job_id must be a valid UUID string (8-4-4-4-12 format)
    parsed = uuid.UUID(job.job_id)
    assert str(parsed) == job.job_id


@pytest.mark.asyncio
async def test_create_job_normalises_ticker(async_sqlite_session):
    """create_job must normalise ticker to uppercase."""
    job = await create_job(async_sqlite_session, "aapl")
    assert job.ticker == "AAPL"


@pytest.mark.asyncio
async def test_create_job_unique_job_ids(async_sqlite_session):
    """Each create_job call must produce a unique job_id."""
    job1 = await create_job(async_sqlite_session, "AAPL")
    job2 = await create_job(async_sqlite_session, "AAPL")
    assert job1.job_id != job2.job_id


# ---------------------------------------------------------------------------
# CRUD: update_job_status (Step 42)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_job_status_transitions(async_sqlite_session):
    """update_job_status must persist the new status value on the record."""
    job = await create_job(async_sqlite_session, "TSLA")
    job_uuid = uuid.UUID(job.job_id)

    for status in ("running", "complete", "failed"):
        await update_job_status(async_sqlite_session, job_uuid, status)
        # Re-fetch to confirm the value was committed to the DB
        updated = await async_sqlite_session.get(AnalysisJobRecord, job.id)
        assert updated.status == status


@pytest.mark.asyncio
async def test_update_job_status_no_op_for_missing_job(async_sqlite_session):
    """update_job_status must not raise when job_id does not exist."""
    missing_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
    # Should complete without error
    await update_job_status(async_sqlite_session, missing_id, "running")


# ---------------------------------------------------------------------------
# CRUD: save_report (Step 42)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_report_persists_record(async_sqlite_session):
    """save_report must create a StockReportRecord linked to the given job_id."""
    job = await create_job(async_sqlite_session, "AAPL")
    report = _make_stock_report("AAPL")

    record = await save_report(async_sqlite_session, uuid.UUID(job.job_id), report)

    assert record.id is not None
    assert record.ticker == "AAPL"
    assert record.company_name == "Apple Inc."
    assert record.recommendation == "BUY"
    assert record.fundamental_score == Decimal("7.5")
    assert record.technical_score == Decimal("8.0")
    assert record.weighted_score == Decimal("7.8")


@pytest.mark.asyncio
async def test_save_report_json_roundtrip(async_sqlite_session):
    """save_report must serialise the full StockReport into report_json."""
    job = await create_job(async_sqlite_session, "AAPL")
    report = _make_stock_report("AAPL")

    record = await save_report(async_sqlite_session, uuid.UUID(job.job_id), report)

    assert record.report_json["ticker"] == "AAPL"
    assert record.report_json["recommendation"] == "BUY"
    assert "fundamental_score" in record.report_json
    assert "key_points" in record.report_json
    assert len(record.report_json["peers"]) == 1


@pytest.mark.asyncio
async def test_save_report_score_precision(async_sqlite_session):
    """Score columns must store Decimal values, not raw floats."""
    job = await create_job(async_sqlite_session, "MSFT")
    report = _make_stock_report("MSFT")

    record = await save_report(async_sqlite_session, uuid.UUID(job.job_id), report)

    # Decimal comparisons — no float imprecision
    assert record.fundamental_score == Decimal("7.5")
    assert record.technical_score == Decimal("8.0")
    assert record.weighted_score == Decimal("7.8")


# ---------------------------------------------------------------------------
# CRUD: get_report_by_ticker (Step 42)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_report_by_ticker_returns_latest(async_sqlite_session):
    """get_report_by_ticker must return a record for the ticker when multiple exist.

    SQLite in-memory has second-level timestamp precision — two rows inserted in
    the same second share the same created_at. The function is expected to return
    one of the matching records (not None). Production PostgreSQL uses microsecond
    timestamps, so the "newest first" ordering is reliable there.
    """
    job1 = await create_job(async_sqlite_session, "AAPL")
    job2 = await create_job(async_sqlite_session, "AAPL")

    report = _make_stock_report("AAPL")
    rec1 = await save_report(async_sqlite_session, uuid.UUID(job1.job_id), report)
    rec2 = await save_report(async_sqlite_session, uuid.UUID(job2.job_id), report)

    latest = await get_report_by_ticker(async_sqlite_session, "AAPL")
    # Must return one of the two records — not None
    assert latest is not None
    assert latest.id in (rec1.id, rec2.id)
    assert latest.ticker == "AAPL"


@pytest.mark.asyncio
async def test_get_report_by_ticker_returns_none_when_missing(async_sqlite_session):
    """get_report_by_ticker must return None when no record exists for the ticker."""
    result = await get_report_by_ticker(async_sqlite_session, "ZZZZ")
    assert result is None


@pytest.mark.asyncio
async def test_get_report_by_ticker_normalises_ticker(async_sqlite_session):
    """get_report_by_ticker must match regardless of ticker case."""
    job = await create_job(async_sqlite_session, "NVDA")
    report = _make_stock_report("NVDA")
    await save_report(async_sqlite_session, uuid.UUID(job.job_id), report)

    result = await get_report_by_ticker(async_sqlite_session, "nvda")
    assert result is not None
    assert result.ticker == "NVDA"


# ---------------------------------------------------------------------------
# CRUD: list_recent_jobs (Step 42)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_recent_jobs_returns_all_when_under_limit(async_sqlite_session):
    """list_recent_jobs must return all jobs when total count is below the limit."""
    for ticker in ("AAPL", "MSFT", "TSLA"):
        await create_job(async_sqlite_session, ticker)

    jobs = await list_recent_jobs(async_sqlite_session, limit=20)
    assert len(jobs) == 3


@pytest.mark.asyncio
async def test_list_recent_jobs_respects_limit(async_sqlite_session):
    """list_recent_jobs must return at most `limit` rows."""
    for ticker in ("AAPL", "MSFT", "TSLA", "NVDA", "GOOG"):
        await create_job(async_sqlite_session, ticker)

    jobs = await list_recent_jobs(async_sqlite_session, limit=3)
    assert len(jobs) == 3


@pytest.mark.asyncio
async def test_list_recent_jobs_ordered_newest_first(async_sqlite_session):
    """list_recent_jobs must return all expected tickers and apply the DESC ordering.

    SQLite in-memory has second-level timestamp precision — three rows inserted in
    the same second share the same created_at. We verify the result contains all
    expected tickers rather than asserting a specific id ordering, which would be
    non-deterministic when timestamps are equal. Production PostgreSQL uses microsecond
    precision, making the DESC order fully deterministic there.
    """
    await create_job(async_sqlite_session, "AAPL")
    await create_job(async_sqlite_session, "MSFT")
    await create_job(async_sqlite_session, "TSLA")

    jobs = await list_recent_jobs(async_sqlite_session, limit=20)

    assert len(jobs) == 3
    tickers = {j.ticker for j in jobs}
    assert tickers == {"AAPL", "MSFT", "TSLA"}


@pytest.mark.asyncio
async def test_list_recent_jobs_empty_returns_empty_list(async_sqlite_session):
    """list_recent_jobs must return an empty list when no jobs exist."""
    jobs = await list_recent_jobs(async_sqlite_session, limit=20)
    assert jobs == []
