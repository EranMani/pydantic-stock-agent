"""DuckDuckGo web search client for fetching company news and risk signals.

All DDGS calls are synchronous and blocking — each function wraps them with
asyncio.to_thread() so the event loop remains free during network I/O.

Search strategy: multiple focused queries fired concurrently via asyncio.gather()
for better signal-to-noise ratio than a single generic query. Each query targets
a specific category of market-moving event.
"""

import asyncio
from datetime import datetime

from ddgs import DDGS

# Results per individual query — kept low intentionally so that each targeted
# query contributes focused signal rather than diluting with generic coverage
_RESULTS_PER_QUERY = 5

# Keywords that indicate a concrete risk event — used by extract_risk_flags()
# to filter raw search snippets down to genuine red flags before LLM reasoning
RISK_KEYWORDS: list[str] = [
    "lawsuit",
    "SEC",
    "investigation",
    "fraud",
    "recall",
    "fine",
    "penalty",
    "bankruptcy",
]


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


async def search_recent_catalysts(
    ticker: str, company_name: str
) -> list[str]:
    """Search for recent high-signal catalyst events that may explain price action.

    Fires multiple focused queries concurrently via asyncio.gather() to surface
    earnings, dilution, acquisitions, deals, partnerships, and IR announcements.
    Always includes the current year to avoid stale results — never hardcoded.
    Returns a deduplicated merged list of snippets.
    """
    year = datetime.now().year

    # Each query targets a specific category of market-moving catalyst
    queries = [
        f"{ticker} {company_name} catalyst earnings revenue guidance {year}",
        f"{ticker} {company_name} shares offering dilution capital raise {year}",
        f"{ticker} {company_name} acquisition merger deal {year}",
        f"{ticker} {company_name} government contract partnership deal {year}",
        f"{ticker} {company_name} investor relations press release {year}",
    ]

    # Fire all queries concurrently — no sequential blocking
    results_per_query: list[list[str]] = await asyncio.gather(
        *[_search_snippets(q) for q in queries]
    )

    # Merge all snippets and deduplicate while preserving order
    return _deduplicate([s for snippets in results_per_query for s in snippets])


async def search_risk_news(
    ticker: str, company_name: str
) -> list[str]:
    """Search for recent risk events: lawsuits, regulatory actions, and financial distress signals.

    Fires multiple focused queries concurrently to surface SEC actions, legal issues,
    product recalls, fines, and bankruptcy signals. Always includes the current year.
    Returns a deduplicated merged list of snippets.
    """
    year = datetime.now().year

    # Each query targets a specific category of risk event
    queries = [
        f"{ticker} {company_name} lawsuit SEC investigation {year}",
        f"{ticker} {company_name} fraud recall fine penalty {year}",
        f"{ticker} {company_name} bankruptcy debt risk warning {year}",
    ]

    # Fire all queries concurrently
    results_per_query: list[list[str]] = await asyncio.gather(
        *[_search_snippets(q) for q in queries]
    )

    return _deduplicate([s for snippets in results_per_query for s in snippets])


async def _search_snippets(query: str) -> list[str]:
    """Run a single DuckDuckGo query and return body snippets.

    Gracefully returns an empty list on any error so one failed query never
    blocks the other concurrent queries in asyncio.gather().
    """
    try:
        results: list[dict] = await asyncio.to_thread(
            _ddgs_search, query, _RESULTS_PER_QUERY
        )
        return [r["body"] for r in results if r.get("body")]
    except Exception:
        return []


def extract_risk_flags(articles: list[str]) -> list[str]:
    """Filter snippets to only those containing a concrete risk keyword.

    Acts as a deterministic signal filter — removes noise snippets that mention
    the company without flagging a real risk event, so the LLM context window
    only receives confirmed risk signals. Matching is case-insensitive.
    Pure computation — no I/O, safe to call from both sync and async contexts.
    """
    # Lower-case once for efficiency rather than per-keyword per-article
    return [
        article for article in articles
        if any(kw.lower() in article.lower() for kw in RISK_KEYWORDS)
    ]


def _deduplicate(snippets: list[str]) -> list[str]:
    """Remove duplicate snippets while preserving insertion order."""
    seen: set[str] = set()
    unique: list[str] = []
    for s in snippets:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique


def _ddgs_search(query: str, max_results: int) -> list[dict]:
    """Synchronous helper that calls DuckDuckGo — intended for use via asyncio.to_thread() only."""
    return list(DDGS().text(query, max_results=max_results))
