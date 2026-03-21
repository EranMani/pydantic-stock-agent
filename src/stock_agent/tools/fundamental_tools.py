"""Fundamental analysis tools registered on the PydanticAI cloud agent.

Each @agent.tool function is called by the cloud LLM during a run. Tools handle
all data fetching and computation — the LLM receives only structured results.

Ollama sub-agent pattern:
  get_ollama_agent() is lazy-initialised via @lru_cache so the module imports
  cleanly even when the Ollama server is offline. The cloud agent never sees raw
  article text — it only receives the structured NewsSummary produced by llama3.2.
"""

import asyncio
from functools import lru_cache

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from stock_agent.agent import agent
from stock_agent.config import settings
from stock_agent.models.context import AgentDependencies
from stock_agent.models.report import FundamentalData, PeerReport
from stock_agent.pipelines.fundamental.web_search import (
    extract_risk_flags,
    search_recent_catalysts,
    search_risk_news,
)
from stock_agent.pipelines.fundamental.yf_client import (
    fetch_earnings_growth,
    fetch_industry_peers,
    fetch_valuation_metrics,
)
from stock_agent.scoring.fundamental_scorer import calculate_fundamental_score


class NewsSummary(BaseModel):
    """Structured output produced by the local Ollama NLP sub-agent.

    Keeps raw article text out of the cloud model context — the main agent
    receives only this condensed, structured summary.
    """

    summary: str = Field(
        description="Concise narrative summary of recent company news, catalysts, and market-moving events.",
    )
    risk_flags: list[str] = Field(
        default_factory=list,
        description="Concrete risk signals extracted from articles (e.g. 'SEC investigation', 'class-action lawsuit').",
    )


# Prompt sent to the local llama3.2 model for NLP summarisation.
# Deliberately brief — Ollama is used for extraction speed, not deep reasoning.
_SUMMARIZE_PROMPT: str = (
    "You are a financial news analyst. Read the following news snippets about a company "
    "and produce:\n"
    "1. A brief one-paragraph summary of recent developments and catalysts.\n"
    "2. A list of concrete risk events (lawsuits, SEC investigations, recalls, fines, "
    "bankruptcy signals). Leave the list empty if none are found.\n\n"
    "Be factual and concise. Do not invent information not present in the snippets.\n\n"
    "Articles:\n{articles}"
)


@lru_cache(maxsize=1)
def get_ollama_agent() -> Agent:
    """Lazily construct the local Ollama sub-agent on first call.

    @lru_cache ensures a single instance is reused across tool calls.
    Deferred to first invocation so the module loads cleanly when Ollama is offline.

    Ollama exposes an OpenAI-compatible API — pydantic-ai connects via OpenAIProvider
    pointed at the Ollama base URL. api_key='ollama' is a required placeholder;
    Ollama does not enforce authentication but the provider requires a non-empty value.

    output_type is intentionally omitted (plain str) — small local models (3.2B params)
    struggle with pydantic-ai's structured output tool-calling protocol and produce
    malformed responses. The tool constructs NewsSummary manually from the text output.
    Risk flags are extracted deterministically before Ollama is called, so the model
    only needs to produce a readable summary paragraph.
    """
    ollama_model = OpenAIModel(
        "llama3.2",
        provider=OpenAIProvider(
            base_url=f"{settings.OLLAMA_HOST}/v1",
            api_key="ollama",  # placeholder — Ollama ignores auth but provider requires a value
        ),
    )
    return Agent(ollama_model)


@agent.tool
async def get_fundamental_data(
    ctx: RunContext[AgentDependencies], ticker: str
) -> FundamentalData:
    """Fetch and score fundamental metrics for a ticker.

    Runs valuation and earnings fetches concurrently via asyncio.gather, then
    applies the ScoringStrategy weights from ctx.deps to produce the final score.
    """
    # Fire both yfinance calls concurrently — no reason to wait sequentially
    valuation, growth = await asyncio.gather(
        fetch_valuation_metrics(ticker),
        fetch_earnings_growth(ticker),
    )

    # FundamentalData is frozen — assemble a temporary instance to pass to the scorer,
    # then reconstruct with the real score. score=0.0 satisfies the ge=0.0 constraint.
    temp = FundamentalData(
        pe_ratio=valuation["pe_ratio"],
        beta=valuation["beta"],
        market_cap=valuation["market_cap"],
        revenue_growth=growth["revenue_growth"],
        score=0.0,
    )
    score = calculate_fundamental_score(temp, ctx.deps.strategy)

    return FundamentalData(
        pe_ratio=valuation["pe_ratio"],
        beta=valuation["beta"],
        market_cap=valuation["market_cap"],
        revenue_growth=growth["revenue_growth"],
        score=score,
    )


@agent.tool
async def get_peer_reports(
    ctx: RunContext[AgentDependencies], ticker: str
) -> list[PeerReport]:
    """Return peer stock analysis results for the given ticker.

    Fetches up to 5 industry peers via yfinance, then runs run_analysis() on each
    concurrently via asyncio.gather. Returns only the lightweight PeerReport fields
    (ticker, weighted_score, recommendation) — not the full StockReport.

    run_analysis is imported lazily inside the function body to break the circular
    import: agent.py imports this module at the bottom (after agent is defined),
    and this module imports agent at the top. A top-level import of run_analysis
    would fail because run_analysis is defined after the tool imports in agent.py.
    """
    # Lazy import — run_analysis is defined after tool module imports in agent.py,
    # so it is not available at module load time. Import here at call time instead.
    from stock_agent.agent import run_analysis  # noqa: PLC0415

    peers = await fetch_industry_peers(ticker)

    if not peers:
        return []

    # Cap at 5 peers and run all analyses concurrently
    reports = await asyncio.gather(
        *[run_analysis(peer, ctx.deps.strategy) for peer in peers[:5]],
        return_exceptions=True,
    )

    # Filter out any peers that failed (network error, bad ticker, etc.)
    return [
        PeerReport(
            ticker=peer,
            weighted_score=report.weighted_score,
            recommendation=report.recommendation,
        )
        for peer, report in zip(peers[:5], reports)
        if not isinstance(report, Exception)
    ]


@agent.tool
async def summarize_news_and_extract_risks(
    ctx: RunContext[AgentDependencies], ticker: str, company_name: str
) -> NewsSummary:
    """Fetch recent news and extract a structured summary using the local Ollama model.

    Fires catalyst and risk searches concurrently, then delegates NLP to llama3.2.
    The cloud agent receives only the structured NewsSummary — raw article text never
    enters the cloud model context, keeping token costs low and privacy high.
    """
    # Fire both search categories concurrently
    catalysts, risks = await asyncio.gather(
        search_recent_catalysts(ticker, company_name),
        search_risk_news(ticker, company_name),
    )
    all_articles = catalysts + risks

    # Deterministic risk flag extraction — runs before LLM to provide a ground-truth baseline
    deterministic_flags = extract_risk_flags(all_articles)

    if not all_articles:
        return NewsSummary(summary="No recent news found.", risk_flags=deterministic_flags)

    # Cap at 20 snippets to stay within llama3.2 context limits
    prompt = _SUMMARIZE_PROMPT.format(articles="\n---\n".join(all_articles[:20]))

    try:
        result = await get_ollama_agent().run(prompt)
        summary = result.output
    except Exception:
        # Ollama unavailable or model not loaded — fall back to raw article snippets.
        # The cloud agent still receives useful context; summarization is degraded, not lost.
        summary = "Ollama unavailable — raw headlines:\n" + "\n".join(
            f"• {a[:150]}" for a in all_articles[:10]
        )

    # result.output is plain text — the model writes a summary paragraph.
    # Risk flags come entirely from deterministic extraction above; the small
    # local model is not asked to classify risk events (unreliable at 3.2B params).
    return NewsSummary(summary=summary, risk_flags=deterministic_flags)
