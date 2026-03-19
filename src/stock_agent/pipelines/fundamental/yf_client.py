"""yfinance client for fetching fundamental data.

All yfinance calls are synchronous and blocking — each function wraps them
with asyncio.to_thread() so the event loop remains free during network I/O.

_get_ticker_info is decorated with @lru_cache so all callers within a single
analysis run share one cached HTTP response — fetch_valuation_metrics,
fetch_earnings_growth, fetch_industry_peers, and fetch_company_name all
call it without triggering redundant network requests.
"""

import asyncio
from functools import lru_cache

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


async def fetch_company_name(ticker: str) -> str:
    """Fetch the full company name for a ticker via yfinance.

    Returns the longName field (e.g. 'ONDS' → 'Ondas Holdings Inc.'). Falls back
    to the ticker symbol itself if longName is missing — ensures the caller always
    receives a usable string for news search queries and agent prompts.
    Uses the shared _get_ticker_info cache — no extra HTTP call if called after
    fetch_valuation_metrics or fetch_earnings_growth for the same ticker.
    """
    info: dict = await asyncio.to_thread(_get_ticker_info, ticker)
    return info.get("longName") or ticker


@lru_cache(maxsize=128)
def _get_ticker_info(ticker: str) -> dict:
    """Synchronous helper that calls yfinance — intended for use via asyncio.to_thread() only.

    @lru_cache ensures all callers within a process share one cached response per ticker,
    eliminating redundant HTTP round trips across fetch_valuation_metrics,
    fetch_earnings_growth, fetch_industry_peers, and fetch_company_name.
    """
    return yf.Ticker(ticker).info
