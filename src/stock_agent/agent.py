"""PydanticAI Agent definition and run_analysis entry point.

Initialises the cloud-model Agent with a strict system prompt that prohibits
the LLM from computing any numerical values — all indicators are pre-computed
by the deterministic pandas-ta pipeline before the agent is invoked.

Model selection at startup:
  - OPENAI_API_KEY set  → OpenAIModel (gpt-4o)
  - GEMINI_API_KEY set  → GeminiModel (gemini-1.5-pro)
  - Neither set         → raises RuntimeError to fail fast in development

Public API:
  run_analysis(ticker, strategy) → StockReport
    The single entry point used by the CLI (main.py), FastAPI (api.py),
    and peer analysis (Step 30).
"""

import os
from datetime import datetime, timezone

from pydantic_ai import Agent
from pydantic_ai.models.gemini import GeminiModel
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from stock_agent.config import settings
from stock_agent.models.context import AgentDependencies, ScoringStrategy
from stock_agent.models.report import StockReport
from stock_agent.pipelines.fundamental.yf_client import fetch_company_name

# System prompt enforces the core architectural constraint: the LLM reasons
# over pre-computed data only — it NEVER estimates or calculates indicators.
SYSTEM_PROMPT: str = """You are an expert financial analyst assistant.

Your role is to reason over pre-computed fundamental and technical data and
produce a structured StockReport with a final recommendation.

STRICT RULES — violations invalidate the analysis:
1. ALL numerical values (scores, moving averages, P/E ratios, growth rates,
   pattern flags) are provided to you by the pipeline tools. You MUST use
   these values exactly as given — NEVER estimate, recalculate, or approximate
   any number yourself.
2. Call ALL available tools before producing the StockReport. Do not skip any tool.
3. Compute weighted_score using ONLY this formula — no approximations:
   weighted_score = (fundamental_score × fundamental_weight)
                  + (technical_score  × technical_weight)
   Both weights are provided in the analysis prompt for each run.
4. Recommendation mapping (apply these thresholds exactly to weighted_score):
   - weighted_score >= 7.0  → "BUY"
   - weighted_score >= 4.0  → "WATCH"
   - weighted_score <  4.0  → "AVOID"
5. The key_points field must contain 4–6 short, specific bullet points explaining
   the key drivers behind the recommendation. Each point must reference a concrete
   data value (e.g. "VCP detected", "P/E ratio of 18.2", "Trend Template PASS",
   "revenue growth of +42%"). Do not write generic statements — every point must
   be grounded in a specific number or signal from the tool results.
"""


def _resolve_model() -> OpenAIModel | GeminiModel:
    """Resolve the cloud model from environment configuration.

    OpenAI takes precedence over Gemini when both keys are present.
    Raises RuntimeError if neither key is configured — fail fast rather
    than silently falling back to an unconfigured state.
    """
    if settings.OPENAI_API_KEY:
        return OpenAIModel("gpt-4o", provider=OpenAIProvider(api_key=settings.OPENAI_API_KEY))
    if settings.GEMINI_API_KEY:
        # GeminiModel reads its key from GOOGLE_API_KEY env var via the default 'google-gla' provider
        os.environ.setdefault("GOOGLE_API_KEY", settings.GEMINI_API_KEY)
        return GeminiModel("gemini-1.5-pro")
    raise RuntimeError(
        "No cloud model API key configured. "
        "Set OPENAI_API_KEY or GEMINI_API_KEY in your .env file."
    )


# Module-level agent instance — tools registered below via side-effect imports
agent: Agent[AgentDependencies, StockReport] = Agent(
    _resolve_model(),
    output_type=StockReport,
    deps_type=AgentDependencies,
    system_prompt=SYSTEM_PROMPT,
)

# Tool registration — imported here to trigger @agent.tool decorators at module load time.
# Placed after `agent` is defined to avoid circular imports (tool modules import `agent`).
import stock_agent.tools.fundamental_tools  # noqa: F401, E402
import stock_agent.tools.technical_tools  # noqa: F401, E402


async def run_analysis(ticker: str, strategy: ScoringStrategy) -> StockReport:
    """Run a full stock analysis and return a structured StockReport.

    Constructs AgentDependencies from the given strategy, builds a prompt that
    instructs the agent to call all registered tools, and returns the validated
    StockReport produced by the cloud model.

    The weighted score formula and recommendation thresholds are embedded in the
    prompt so the LLM applies them to the exact pre-computed scores from the tools —
    it never estimates or re-derives any value.

    Used by:
      - CLI entry point (Step 28): asyncio.run(run_analysis(ticker, strategy))
      - FastAPI POST /analyze (Step 29): awaited directly in the route handler
      - Peer analysis tool (Step 30): called concurrently via asyncio.gather
    """
    deps = AgentDependencies(strategy=strategy)

    # Resolve company name and current timestamp before building the prompt.
    # company_name feeds into the news search queries — a placeholder would corrupt them.
    # analysis_date is pinned here so the LLM uses the exact run timestamp, not a guess.
    company_name = await fetch_company_name(ticker)
    analysis_date = datetime.now(timezone.utc).isoformat()

    # Embed the weights explicitly in the prompt so the LLM has the exact values
    # needed to apply the weighted_score formula from the system prompt.
    prompt = (
        f"Analyse the stock with ticker symbol '{ticker}' ({company_name}).\n\n"
        f"Analysis timestamp (use this exact value for analysis_date): {analysis_date}\n\n"
        f"Scoring weights for this run:\n"
        f"  fundamental_weight = {strategy.fundamental_weight}\n"
        f"  technical_weight   = {strategy.technical_weight}\n\n"
        f"Instructions:\n"
        f"1. Call get_fundamental_data('{ticker}') to retrieve fundamental metrics and score.\n"
        f"2. Call get_technical_data('{ticker}') to retrieve technical indicators and score.\n"
        f"3. Call get_peer_reports('{ticker}') to retrieve peer comparison data.\n"
        f"4. Call summarize_news_and_extract_risks('{ticker}', '{company_name}') for news context.\n"
        f"5. Compute weighted_score = (fundamental_score × {strategy.fundamental_weight}) "
        f"+ (technical_score × {strategy.technical_weight}).\n"
        f"6. Apply the recommendation thresholds from the system prompt.\n"
        f"7. Write 4–6 specific, data-driven key_points — each one referencing a concrete signal or value.\n"
        f"8. Produce the final StockReport."
    )

    result = await agent.run(prompt, deps=deps)
    return result.output
