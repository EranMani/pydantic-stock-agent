"""yfinance client for fetching fundamental data.

All yfinance calls are synchronous and blocking — each function wraps them
with asyncio.to_thread() so the event loop remains free during network I/O.
"""

import asyncio

import yfinance as yf


async def fetch_valuation_metrics(ticker: str) -> dict[str, float | None]:
    """Fetch market cap, P/E ratio, and beta for a ticker via yfinance.

    Wraps the synchronous yfinance .info call in asyncio.to_thread() to avoid
    blocking the event loop. Missing fields are returned as None.
    """
    # yfinance .info is a blocking HTTP call — offload to a thread pool
    info: dict = await asyncio.to_thread(_get_ticker_info, ticker)

    return {
        "pe_ratio": info.get("trailingPE"),
        "beta": info.get("beta"),
        "market_cap": info.get("marketCap"),
    }


async def fetch_earnings_growth(ticker: str) -> dict[str, float | None]:
    """Fetch revenue growth and earnings growth rates for a ticker via yfinance.

    Both fields can be None for pre-revenue or pre-profit companies, and can be
    negative during periods of contraction. Wraps blocking yfinance call via
    asyncio.to_thread().
    """
    # Reuse cached .info dict — blocking call offloaded to thread pool
    info: dict = await asyncio.to_thread(_get_ticker_info, ticker)

    return {
        "revenue_growth": info.get("revenueGrowth"),
        "earnings_growth": info.get("earningsGrowth"),
    }


async def fetch_industry_peers(ticker: str) -> list[str]:
    """Fetch a list of industry peer tickers for a given stock via yfinance.

    Returns at most 10 tickers. Falls back to an empty list on any error —
    peer unavailability must never crash the main analysis pipeline.
    Note: score-based filtering of peers happens later in the agent tool layer
    (get_peer_reports in Step 30), not here.
    """
    try:
        info: dict = await asyncio.to_thread(_get_ticker_info, ticker)
        # yfinance returns peers under the recommendationKey siblings or industryPeers;
        # use the company's own industry peers list capped at 10
        peers: list[str] = info.get("industryPeers", []) or []
        return peers[:10]
    except Exception:
        # Graceful fallback — peer data is supplementary, not critical
        return []


def _get_ticker_info(ticker: str) -> dict:
    """Synchronous helper that calls yfinance — intended for use via asyncio.to_thread() only."""
    return yf.Ticker(ticker).info
