"""Deterministic sample data for the stock-agent CLI demo mode.

Mock mode gives interviewers and reviewers a reproducible typed StockReport
without requiring API keys, network access, yfinance, DuckDuckGo, or an LLM.
"""

from datetime import datetime, timezone

from stock_agent.models.report import KeyPoint, PeerReport, StockReport


def build_mock_report(ticker: str) -> StockReport:
    """Return a deterministic StockReport for the requested ticker."""
    normalized_ticker = ticker.upper()
    company_name = {
        "NVDA": "NVIDIA Corporation",
        "AAPL": "Apple Inc.",
        "MSFT": "Microsoft Corporation",
    }.get(normalized_ticker, f"{normalized_ticker} Demo Company")

    return StockReport(
        ticker=normalized_ticker,
        company_name=company_name,
        current_price=123.45,
        analysis_date=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
        market_summary=(
            f"{company_name} is shown in mock mode with strong growth context, "
            "constructive technical posture, and valuation risk kept visible."
        ),
        fundamental_score=7.4,
        technical_score=8.2,
        weighted_score=7.8,
        calculation="(7.4 x 0.50) + (8.2 x 0.50) = 7.8",
        key_points=[
            KeyPoint(text="Revenue growth sample of 42% supports the fundamental score", sentiment="positive"),
            KeyPoint(text="Price remains above the 50/150/200-day moving averages", sentiment="positive"),
            KeyPoint(text="Mock P/E ratio of 31.6 keeps valuation risk in view", sentiment="negative"),
            KeyPoint(text="VCP pattern is marked as detected in sample technical data", sentiment="positive"),
        ],
        risks=[
            "Valuation could compress if growth expectations cool.",
            "Supply or demand shocks can affect near-term margins.",
        ],
        sources=[
            "mock://market-data/nvda",
            "mock://news-context/nvda",
        ],
        confidence="medium",
        recommendation="BUY",
        peers=[
            PeerReport(ticker="AMD", weighted_score=6.9, recommendation="WATCH"),
            PeerReport(ticker="MSFT", weighted_score=7.1, recommendation="BUY"),
        ],
    )
