"""PydanticAI Agent definition for the stock analyst pipeline.

Initialises the cloud-model Agent with a strict system prompt that prohibits
the LLM from computing any numerical values — all indicators are pre-computed
by the deterministic pandas-ta pipeline before the agent is invoked.

Model selection at startup:
  - OPENAI_API_KEY set  → OpenAIModel (gpt-4o)
  - GEMINI_API_KEY set  → GeminiModel (gemini-1.5-pro)
  - Neither set         → raises RuntimeError to fail fast in development
"""

import os

from pydantic_ai import Agent
from pydantic_ai.models.gemini import GeminiModel
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from stock_agent.config import settings
from stock_agent.models.context import AgentDependencies
from stock_agent.models.report import StockReport

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
2. NEVER perform arithmetic on financial data. If a tool has not been called,
   request the data via the appropriate tool — do not guess.
3. Base your recommendation exclusively on the scores and flags returned by
   the registered tools. Your value is synthesising and narrating — not computing.
4. The summary field must explain the key drivers behind the recommendation in
   plain language suitable for a retail investor.
5. Recommendation mapping (use these thresholds exactly):
   - weighted_score >= 7.0  → "BUY"
   - weighted_score >= 4.0  → "WATCH"
   - weighted_score <  4.0  → "AVOID"
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


# Module-level agent instance — tools are registered in Step 26
agent: Agent[AgentDependencies, StockReport] = Agent(
    _resolve_model(),
    output_type=StockReport,
    deps_type=AgentDependencies,
    system_prompt=SYSTEM_PROMPT,
)
