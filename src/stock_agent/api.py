"""FastAPI application — single source of truth for all HTTP endpoints.

Owns the FastAPI instance, lifespan hook, request/response models, and every
route handler in the project. All HTTP concerns live here; no route definitions
exist in any other module.

Entry point for the web server:
  uvicorn stock_agent.api:app

Current endpoints:
  POST /analyze  — synchronous analysis path (direct run_analysis call).
                   Phase 9 replaces this with async Celery dispatch.

Lifespan:
  Placeholder until db/session.py is built in Step 40. At that point the
  real async SQLAlchemy engine init and connection pool warm-up will replace
  the no-op yield below.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from stock_agent.agent import run_analysis
from stock_agent.models.context import ScoringStrategy
from stock_agent.models.report import StockReport


class AnalyzeRequest(BaseModel):
    """Request body for POST /analyze."""

    ticker: str
    strategy: ScoringStrategy = ScoringStrategy()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan hook — placeholder until db/session.py is built (Step 40).

    Step 40 replaces this with the real async SQLAlchemy engine init and
    connection pool warm-up. Keeping the hook wired here so the architecture
    slot exists and the startup/shutdown pattern is established.
    """
    # STARTUP — nothing to initialise yet
    yield
    # SHUTDOWN — nothing to dispose yet


app = FastAPI(title="Stock Agent API", lifespan=lifespan)


@app.post("/analyze", response_model=StockReport)
async def analyze(request: AnalyzeRequest) -> StockReport:
    """Run a full stock analysis and return a structured StockReport.

    Synchronous path — blocks until run_analysis() completes.
    Celery async dispatch will replace this call in Phase 9.
    """
    return await run_analysis(request.ticker, request.strategy)
