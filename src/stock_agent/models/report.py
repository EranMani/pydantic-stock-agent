"""Pydantic output models for the stock analyst agent.

Defines the structured data shapes that flow through the pipeline:
FundamentalData and TechnicalData are frozen sub-models (immutable after creation);
PeerReport and StockReport are the top-level agent outputs.
"""

from datetime import datetime
from typing import Literal

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field
from pydantic.functional_validators import AfterValidator

# Score fields are always rounded to one decimal place (e.g. 7.1, 4.0)
Score = Annotated[float, AfterValidator(lambda v: round(v, 1))]


class FundamentalData(BaseModel):
    """Immutable container for fundamental analysis metrics."""

    # Frozen: prevents accidental mutation after the pipeline computes values
    model_config = ConfigDict(frozen=True)

    pe_ratio: float | None = Field(
        default=None,
        description="Price-to-earnings ratio. Lower values may indicate undervaluation. Can be negative for loss-making companies.",
    )
    revenue_growth: float | None = Field(
        default=None,
        description="Year-over-year revenue growth rate as a decimal (e.g. 0.15 = 15%). Can be negative during revenue contraction.",
    )
    market_cap: float | None = Field(
        default=None,
        ge=0.0,
        description="Total market capitalisation in USD. Always non-negative.",
    )
    beta: float | None = Field(
        default=None,
        description="Measure of price volatility relative to the market. Beta > 1 means amplified moves; beta < 0 means inverse correlation to the market.",
    )
    score: Score = Field(
        ge=0.0,
        description="Computed fundamental score in the range [1.0, 10.0]. Higher is better.",
    )


class TechnicalData(BaseModel):
    """Immutable container for technical indicator values and pattern flags."""

    # Frozen: ensures indicator values are write-once from the pandas-ta pipeline
    model_config = ConfigDict(frozen=True)

    sma_50: float = Field(
        ge=0.0,
        description="50-day simple moving average of closing price in USD.",
    )
    sma_150: float = Field(
        ge=0.0,
        description="150-day simple moving average of closing price in USD.",
    )
    sma_200: float = Field(
        ge=0.0,
        description="200-day simple moving average of closing price in USD.",
    )
    high_52w: float = Field(
        ge=0.0,
        description="Highest closing price over the past 52 weeks (252 trading days) in USD.",
    )
    low_52w: float = Field(
        ge=0.0,
        description="Lowest closing price over the past 52 weeks (252 trading days) in USD.",
    )
    trend_template_passed: bool = Field(
        description="True if the stock satisfies all Minervini Trend Template conditions (price above MAs, 200-day MA trending up, etc.).",
    )
    vcp_detected: bool = Field(
        description="True if a Volatility Contraction Pattern is detected — successive price ranges narrowing over the last 60 bars.",
    )
    score: Score = Field(
        ge=0.0,
        description="Computed technical score in the range [1.0, 10.0]. Higher is better.",
    )


class PeerReport(BaseModel):
    """Lightweight peer comparison result — ticker, score, and recommendation only."""

    ticker: str = Field(
        description="Stock ticker symbol of the peer company (e.g. 'MSFT').",
    )
    weighted_score: Score = Field(
        description="Final weighted score for this peer in the range [1.0, 10.0].",
    )
    recommendation: Literal["BUY", "WATCH", "AVOID"] = Field(
        description="Agent recommendation for this peer based on its weighted score.",
    )


class StockReport(BaseModel):
    """Top-level structured output produced by the PydanticAI agent."""

    ticker: str = Field(
        description="Stock ticker symbol being analysed (e.g. 'AAPL').",
    )
    analysis_date: datetime = Field(
        description="UTC timestamp of when this analysis was generated.",
    )
    fundamental_score: Score = Field(
        description="Fundamental pipeline score in the range [1.0, 10.0].",
    )
    technical_score: Score = Field(
        description="Technical pipeline score in the range [1.0, 10.0].",
    )
    weighted_score: Score = Field(
        description="Final score combining fundamental and technical scores using ScoringStrategy weights. Range [1.0, 10.0].",
    )
    summary: str = Field(
        description="Concise analyst narrative summarising the key drivers behind the recommendation.",
    )
    recommendation: Literal["BUY", "WATCH", "AVOID"] = Field(
        description="Final recommendation: BUY (strong setup), WATCH (monitor for entry), AVOID (unfavourable conditions).",
    )
    peers: list[PeerReport] = Field(
        description="Analysis results for industry peer stocks fetched from yfinance (up to 5 peers).",
    )
