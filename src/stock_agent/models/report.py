from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class FundamentalData(BaseModel):
    pe_ratio: float | None
    revenue_growth: float | None
    market_cap: float | None
    beta: float | None
    score: float


class TechnicalData(BaseModel):
    sma_50: float
    sma_150: float
    sma_200: float
    high_52w: float
    low_52w: float
    trend_template_passed: bool
    vcp_detected: bool
    score: float


class PeerReport(BaseModel):
    ticker: str
    weighted_score: float
    recommendation: Literal["BUY", "WATCH", "AVOID"]


class StockReport(BaseModel):
    ticker: str
    analysis_date: datetime
    fundamental_score: float
    technical_score: float
    weighted_score: float
    summary: str
    recommendation: Literal["BUY", "WATCH", "AVOID"]
    peers: list[PeerReport]
