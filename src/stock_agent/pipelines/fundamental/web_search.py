"""DuckDuckGo web search client for fetching company news and risk signals.

All DDGS calls are synchronous and blocking — each function wraps them with
asyncio.to_thread() so the event loop remains free during network I/O.
"""

import asyncio

from ddgs import DDGS


async def search_company_news(
    ticker: str, company_name: str, max_results: int = 10
) -> list[str]:
    """Search DuckDuckGo for recent news articles about a company.

    Wraps the synchronous DDGS().text() call in asyncio.to_thread() to avoid
    blocking the event loop. Returns a list of article snippet strings.
    Returns an empty list on any error — news unavailability must never crash
    the main analysis pipeline.
    """
    query = f"{ticker} {company_name} news"
    try:
        # DDGS().text() is a blocking call — offload to thread pool
        results: list[dict] = await asyncio.to_thread(
            _ddgs_search, query, max_results
        )
        # Extract the body/snippet text from each result
        return [r["body"] for r in results if r.get("body")]
    except Exception:
        return []


def _ddgs_search(query: str, max_results: int) -> list[dict]:
    """Synchronous helper that calls DuckDuckGo — intended for use via asyncio.to_thread() only."""
    return list(DDGS().text(query, max_results=max_results))
