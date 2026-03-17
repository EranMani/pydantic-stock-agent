"""Pydantic output models for the stock analyst agent.

Defines the structured data shapes that flow through the pipeline:
FundamentalData and TechnicalData are frozen sub-models (immutable after creation);
PeerReport and StockReport are the top-level agent outputs.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FundamentalData(BaseModel):
    """Immutable container for fundamental analysis metrics."""

    # Frozen: prevents accidental mutation after the pipeline computes values
    model_config = ConfigDict(frozen=True)

    pe_ratio: float | None
    revenue_growth: float | None
    market_cap: float | None = Field(default=None, ge=0.0)
    beta: float | None
    score: float = Field(ge=0.0)


class TechnicalData(BaseModel):
    """Immutable container for technical indicator values and pattern flags."""

    # Frozen: ensures indicator values are write-once from the pandas-ta pipeline
    model_config = ConfigDict(frozen=True)

    sma_50: float = Field(ge=0.0)
    sma_150: float = Field(ge=0.0)
    sma_200: float = Field(ge=0.0)
    high_52w: float = Field(ge=0.0)
    low_52w: float = Field(ge=0.0)
    trend_template_passed: bool
    vcp_detected: bool
    score: float = Field(ge=0.0)


class PeerReport(BaseModel):
    """Lightweight peer comparison result — ticker, score, and recommendation only."""

    ticker: str
    weighted_score: float
    recommendation: Literal["BUY", "WATCH", "AVOID"]


class StockReport(BaseModel):
    """Top-level structured output produced by the PydanticAI agent."""

    ticker: str
    analysis_date: datetime
    fundamental_score: float
    technical_score: float
    weighted_score: float
    summary: str
    recommendation: Literal["BUY", "WATCH", "AVOID"]
    peers: list[PeerReport]
