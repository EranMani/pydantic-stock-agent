"""FastAPI application — single source of truth for all HTTP endpoints.

Owns the FastAPI instance, lifespan hook, request/response models, and every
route handler in the project. All HTTP concerns live here; no route definitions
exist in any other module.

Entry point for the web server:
  uvicorn stock_agent.api:app

Current endpoints:
  POST /analyze             — synchronous analysis path (direct run_analysis call).
                              Phase 9 replaces this with async Celery dispatch.
  GET /reports/{ticker}     — return the most recent StockReportRecord for a ticker.
                              Returns 404 if no analysis has been run for that ticker.
  GET /jobs                 — return the N most recent AnalysisJobRecord rows.

Lifespan:
  Managed by db/session.py — creates the async engine on startup, disposes
  the connection pool on shutdown. In development, auto-creates all tables.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from stock_agent.agent import run_analysis
from stock_agent.db.crud import get_report_by_ticker, list_recent_jobs
from stock_agent.db.session import get_session, lifespan
from stock_agent.models.context import ScoringStrategy
from stock_agent.models.report import StockReport


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------


class AnalyzeRequest(BaseModel):
    """Request body for POST /analyze."""

    ticker: str
    strategy: ScoringStrategy = ScoringStrategy()


# ---------------------------------------------------------------------------
# Response models — serialise ORM records to clean JSON without exposing
# SQLAlchemy internals. Pydantic validates and serialises from ORM attributes.
# ---------------------------------------------------------------------------


class StockReportResponse(BaseModel):
    """Response schema for GET /reports/{ticker}.

    Mirrors the StockReportRecord ORM columns. report_json carries the full
    StockReport payload — all other fields are the denormalised fast-query columns.
    """

    id: int = Field(description="Surrogate primary key of this report record.")
    ticker: str = Field(description="Stock ticker symbol (e.g. 'AAPL').")
    company_name: str = Field(description="Full company name resolved at analysis time.")
    report_json: dict[str, Any] = Field(
        description="Full StockReport serialised as JSON — source of truth for all report fields."
    )
    fundamental_score: Decimal = Field(
        description="Fundamental pipeline score [1.0, 10.0]. Denormalised from report_json."
    )
    technical_score: Decimal = Field(
        description="Technical pipeline score [1.0, 10.0]. Denormalised from report_json."
    )
    weighted_score: Decimal = Field(
        description="Final combined score [1.0, 10.0]. Denormalised from report_json."
    )
    recommendation: str = Field(
        description="Agent recommendation: BUY, WATCH, or AVOID."
    )
    created_at: datetime = Field(
        description="UTC timestamp when this record was inserted."
    )

    # orm_mode (v1 alias) is model_config from_attributes in Pydantic v2
    # Required to allow Pydantic to read attributes from an ORM object rather
    # than expecting a plain dict — without this, the route would raise a
    # validation error because ORM instances are not dicts.
    model_config = {"from_attributes": True}


class AnalysisJobResponse(BaseModel):
    """Response schema for a single row from GET /jobs.

    Mirrors the AnalysisJobRecord ORM columns.
    """

    id: int = Field(description="Surrogate primary key of this job record.")
    job_id: str = Field(
        description="Stable UUID identifying this job across DB and Redis."
    )
    ticker: str = Field(description="Stock ticker symbol this job is analysing.")
    status: str = Field(
        description="Job lifecycle state: pending | running | complete | failed."
    )
    created_at: datetime = Field(description="UTC timestamp when the job was enqueued.")
    updated_at: datetime = Field(
        description="UTC timestamp of the last status update."
    )

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(title="Stock Agent API", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Existing endpoint — synchronous analysis path
# ---------------------------------------------------------------------------


@app.post("/analyze", response_model=StockReport)
async def analyze(request: AnalyzeRequest) -> StockReport:
    """Run a full stock analysis and return a structured StockReport.

    Synchronous path — blocks until run_analysis() completes.
    Celery async dispatch will replace this call in Phase 9.
    """
    return await run_analysis(request.ticker, request.strategy)


# ---------------------------------------------------------------------------
# GET /reports/{ticker} — most recent persisted report for a ticker
# ---------------------------------------------------------------------------


@app.get("/reports/{ticker}", response_model=StockReportResponse)
async def get_report(
    ticker: str,
    db: AsyncSession = Depends(get_session),
) -> StockReportResponse:
    """Return the most recent StockReportRecord for the given ticker.

    Calls get_report_by_ticker(db, ticker) from the CRUD layer.
    Returns 404 if no analysis has been persisted for that ticker.
    """
    record = await get_report_by_ticker(db, ticker)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"No report found for ticker '{ticker.upper()}'",
        )
    # Pydantic reads directly from ORM attributes via from_attributes=True
    return StockReportResponse.model_validate(record)


# ---------------------------------------------------------------------------
# GET /jobs — recent analysis job history
# ---------------------------------------------------------------------------


@app.get("/jobs", response_model=list[AnalysisJobResponse])
async def get_jobs(
    limit: int = 20,
    db: AsyncSession = Depends(get_session),
) -> list[AnalysisJobResponse]:
    """Return the N most recent AnalysisJobRecord rows, newest first.

    Optional query parameter `limit` (default 20) controls how many rows to return.
    Returns an empty list when no jobs exist — never 404.
    """
    jobs = await list_recent_jobs(db, limit=limit)
    # Validate each ORM object through the response schema
    return [AnalysisJobResponse.model_validate(job) for job in jobs]
