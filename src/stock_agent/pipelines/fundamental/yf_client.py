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


def _get_ticker_info(ticker: str) -> dict:
    """Synchronous helper that calls yfinance — intended for use via asyncio.to_thread() only."""
    return yf.Ticker(ticker).info
