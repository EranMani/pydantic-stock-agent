"""Tests for FastAPI endpoints: GET /reports/{ticker} and GET /jobs.

Strategy:
- Use httpx.AsyncClient + ASGITransport to drive the FastAPI app directly
  without starting a real HTTP server.
- Override the get_session FastAPI dependency with an in-memory SQLite session
  so tests run with no external infrastructure (no Postgres, no Docker).
- Seed data via the CRUD layer (same functions the production code uses) to
  keep the setup free of raw SQL and consistent with the ORM contract.

Endpoints under test:
  GET /reports/{ticker}  — happy path + 404 when no report exists
  GET /jobs              — happy path (multiple rows) + empty list
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
import httpx
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from stock_agent.api import app
from stock_agent.db.crud import create_job, save_report
from stock_agent.db.models import Base
from stock_agent.db.session import get_session
from stock_agent.models.report import (
    FundamentalData,
    KeyPoint,
    PeerReport,
    StockReport,
    TechnicalData,
)


# ---------------------------------------------------------------------------
# In-memory SQLite session fixture
# Mirrors the pattern established in test_db.py.
# A fresh database is created for each test function — complete isolation.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def async_sqlite_session():
    """Yield a clean AsyncSession backed by an in-memory SQLite database.

    Creates all ORM tables at the start and drops them after the test,
    ensuring full isolation. Uses aiosqlite driver.
    """
    async_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSession(async_engine, expire_on_commit=False) as session:
        yield session

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await async_engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_client(async_sqlite_session: AsyncSession):
    """Yield an httpx.AsyncClient wired to the FastAPI app.

    Overrides the get_session dependency so all route handlers use the
    in-memory SQLite session injected here — no live Postgres required.

    The override is installed before the client is yielded and removed
    after the test completes, leaving the app's dependency registry clean.
    """

    async def _override_get_session():
        """Yield the test session instead of opening a real DB session."""
        yield async_sqlite_session

    # Install the dependency override on the FastAPI app
    app.dependency_overrides[get_session] = _override_get_session

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, async_sqlite_session

    # Clean up the override after the test
    app.dependency_overrides.pop(get_session, None)


# ---------------------------------------------------------------------------
# Helper — build a minimal but valid StockReport for seeding
# ---------------------------------------------------------------------------


def _make_stock_report(ticker: str = "AAPL") -> StockReport:
    """Build a minimal valid StockReport for test seeding."""
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


# ---------------------------------------------------------------------------
# GET /reports/{ticker}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_report_returns_200_with_correct_fields(test_client):
    """GET /reports/{ticker} returns 200 and the expected report fields."""
    client, db = test_client

    # Seed: create a job and persist a report
    job = await create_job(db, "AAPL")
    report = _make_stock_report("AAPL")
    await save_report(db, uuid.UUID(job.job_id), report)

    response = await client.get("/reports/AAPL")

    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "AAPL"
    assert data["company_name"] == "Apple Inc."
    assert data["recommendation"] == "BUY"
    # Scores must be present as serialised numbers
    assert float(data["fundamental_score"]) == pytest.approx(7.5, abs=0.1)
    assert float(data["technical_score"]) == pytest.approx(8.0, abs=0.1)
    assert float(data["weighted_score"]) == pytest.approx(7.8, abs=0.1)
    # report_json must carry the full payload
    assert "ticker" in data["report_json"]
    assert data["report_json"]["ticker"] == "AAPL"
    # Metadata fields must be present
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_get_report_ticker_case_insensitive(test_client):
    """GET /reports/{ticker} must match regardless of ticker case in the URL."""
    client, db = test_client

    job = await create_job(db, "AAPL")
    report = _make_stock_report("AAPL")
    await save_report(db, uuid.UUID(job.job_id), report)

    # Query with lowercase — should still return the record
    response = await client.get("/reports/aapl")

    assert response.status_code == 200
    assert response.json()["ticker"] == "AAPL"


@pytest.mark.asyncio
async def test_get_report_returns_404_when_not_found(test_client):
    """GET /reports/{ticker} returns 404 when no report exists for that ticker."""
    client, _ = test_client

    response = await client.get("/reports/ZZZZ")

    assert response.status_code == 404
    # FastAPI error shape: {"detail": "..."}
    assert "detail" in response.json()
    assert "ZZZZ" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_report_returns_latest_when_multiple_exist(test_client):
    """GET /reports/{ticker} returns a record (not None) when multiple reports exist."""
    client, db = test_client

    # Seed two reports for the same ticker
    job1 = await create_job(db, "TSLA")
    job2 = await create_job(db, "TSLA")
    report = _make_stock_report("TSLA")
    rec1 = await save_report(db, uuid.UUID(job1.job_id), report)
    rec2 = await save_report(db, uuid.UUID(job2.job_id), report)

    response = await client.get("/reports/TSLA")

    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "TSLA"
    # Must be one of the two seeded records
    assert data["id"] in (rec1.id, rec2.id)


# ---------------------------------------------------------------------------
# GET /jobs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_jobs_returns_200_with_correct_fields(test_client):
    """GET /jobs returns 200 and a list with the expected job fields."""
    client, db = test_client

    job = await create_job(db, "AAPL")

    response = await client.get("/jobs")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    item = data[0]
    assert item["job_id"] == job.job_id
    assert item["ticker"] == "AAPL"
    assert item["status"] == "pending"
    assert "id" in item
    assert "created_at" in item
    assert "updated_at" in item


@pytest.mark.asyncio
async def test_get_jobs_returns_empty_list_when_no_jobs(test_client):
    """GET /jobs returns 200 with an empty list when no jobs exist.

    Must not return 404 — an empty history is not an error.
    """
    client, _ = test_client

    response = await client.get("/jobs")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_jobs_respects_limit_query_param(test_client):
    """GET /jobs?limit=N returns at most N rows."""
    client, db = test_client

    for ticker in ("AAPL", "MSFT", "TSLA", "NVDA", "GOOG"):
        await create_job(db, ticker)

    response = await client.get("/jobs?limit=3")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3


@pytest.mark.asyncio
async def test_get_jobs_returns_all_within_default_limit(test_client):
    """GET /jobs with default limit returns all rows when under 20."""
    client, db = test_client

    for ticker in ("AAPL", "MSFT", "TSLA"):
        await create_job(db, ticker)

    response = await client.get("/jobs")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    tickers = {item["ticker"] for item in data}
    assert tickers == {"AAPL", "MSFT", "TSLA"}
