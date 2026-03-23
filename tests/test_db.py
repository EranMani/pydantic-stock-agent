"""Tests for SQLAlchemy ORM models.

Uses SQLite in-memory for structural and round-trip verification — no live
PostgreSQL instance required. Integration tests against the real async session
will be added in Step 41 (crud.py) once conftest.py provides the async fixture.

Covers:
- Table names correct
- All expected columns present
- Round-trip save and retrieval (field values preserved)
- Numeric score precision (Decimal, not float)
- Uniqueness constraint on AnalysisJobRecord.job_id
"""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from stock_agent.db.models import AnalysisJobRecord, Base, StockReportRecord


@pytest.fixture(scope="module")
def engine():
    """In-memory SQLite engine with all ORM tables created."""
    _engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(_engine)
    yield _engine
    Base.metadata.drop_all(_engine)


@pytest.fixture
def session(engine):
    """Provide a clean session that rolls back after each test."""
    with Session(engine) as _session:
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


def test_stock_report_record_columns(engine):
    """stock_reports table has all expected columns."""
    inspector = inspect(engine)
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


def test_analysis_job_record_columns(engine):
    """analysis_jobs table has all expected columns."""
    inspector = inspect(engine)
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


def test_analysis_job_record_job_id_unique(engine):
    """job_id must be unique — inserting a duplicate raises IntegrityError."""
    with Session(engine) as s:
        s.add(AnalysisJobRecord(job_id="duplicate-id", ticker="AAPL", status="pending"))
        s.commit()

    with Session(engine) as s:
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
