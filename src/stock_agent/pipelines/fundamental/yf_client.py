"""yfinance client for fetching fundamental data.

All yfinance calls are synchronous and blocking — each function wraps them
with asyncio.to_thread() so the event loop remains free during network I/O.

_get_ticker_info is decorated with @lru_cache so all callers within a single
analysis run share one cached HTTP response — fetch_valuation_metrics,
fetch_earnings_growth, fetch_industry_peers, and fetch_company_name all
call it without triggering redundant network requests.
"""

import asyncio
import re
from functools import lru_cache

import yfinance as yf
from duckduckgo_search import DDGS


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
    """Fetch the full company name for a ticker via yfinance, with DuckDuckGo fallback.

    Primary: yfinance longName field (e.g. 'ONDS' → 'Ondas Holdings Inc.').
    Fallback: DuckDuckGo search for '{ticker} stock' when longName is missing —
    prevents raw ticker strings from corrupting downstream news search queries.
    Last resort: the ticker symbol itself if both sources fail.
    Uses the shared _get_ticker_info cache — no extra HTTP call if called after
    fetch_valuation_metrics or fetch_earnings_growth for the same ticker.
    """
    info: dict = await asyncio.to_thread(_get_ticker_info, ticker)
    name = info.get("longName")
    if name:
        return name
    return await _search_company_name_ddg(ticker)


async def _search_company_name_ddg(ticker: str) -> str:
    """Resolve a company name via DuckDuckGo when yfinance longName is unavailable.

    Runs a single DuckDuckGo text search in a thread pool (blocking call) and
    strips the parenthetical ticker suffix from the result title, e.g.:
      'Nebius Group N.V. (NBIS) Stock Price...' → 'Nebius Group N.V.'
    Falls back to the ticker symbol itself on any error or empty result.
    """
    def _search() -> str:
        # Blocking DuckDuckGo HTTP call — must run in a thread pool
        results = DDGS().text(f"{ticker} stock", max_results=1)
        if not results:
            return ticker
        title = results[0].get("title", "")
        # Strip ' (TICKER) ...' suffix produced by financial sites
        cleaned = re.sub(r"\s*\(.*?\).*", "", title).strip()
        return cleaned or ticker

    try:
        return await asyncio.to_thread(_search)
    except Exception:
        return ticker


@lru_cache(maxsize=128)
def _get_ticker_info(ticker: str) -> dict:
    """Synchronous helper that calls yfinance — intended for use via asyncio.to_thread() only.

    @lru_cache ensures all callers within a process share one cached response per ticker,
    eliminating redundant HTTP round trips across fetch_valuation_metrics,
    fetch_earnings_growth, fetch_industry_peers, and fetch_company_name.
    """
    return yf.Ticker(ticker).info
