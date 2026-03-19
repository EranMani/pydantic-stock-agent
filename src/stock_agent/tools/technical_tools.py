"""Technical analysis tools registered on the PydanticAI cloud agent.

get_technical_data runs the full indicator pipeline and returns a scored TechnicalData.
get_moving_average_signal is a lightweight agentic lookup — the LLM can request
current MA values mid-analysis without triggering the full scoring pipeline.
"""

from pydantic_ai import RunContext

from stock_agent.agent import agent
from stock_agent.models.context import AgentDependencies
from stock_agent.models.report import TechnicalData
from stock_agent.pipelines.technical.core_data import fetch_ohlcv
from stock_agent.pipelines.technical.indicators.moving_averages import add_moving_averages
from stock_agent.scoring.technical_scorer import calculate_technical_score


@agent.tool
async def get_technical_data(
    ctx: RunContext[AgentDependencies], ticker: str
) -> TechnicalData:
    """Fetch OHLCV data and run the full technical indicator pipeline for a ticker.

    fetch_ohlcv handles NaN validation and caching internally — the DataFrame
    returned is clean and ready for indicator computation.
    ScoringStrategy from ctx.deps controls which indicators are active.
    """
    df = await fetch_ohlcv(ticker)
    return calculate_technical_score(df, ctx.deps.strategy)


@agent.tool
async def get_moving_average_signal(
    ctx: RunContext[AgentDependencies], ticker: str
) -> dict:
    """Return current moving average values and price for a ticker.

    Lightweight alternative to get_technical_data — allows the agent to inspect
    MA levels mid-analysis without re-running the full scoring pipeline.
    Useful for validating trend template conditions or checking price positioning.
    """
    df = await fetch_ohlcv(ticker)
    df = add_moving_averages(df)

    return {
        "current_price": float(df["Close"].iloc[-1]),
        "sma_50": float(df["SMA_50"].iloc[-1]),
        "sma_150": float(df["SMA_150"].iloc[-1]),
        "sma_200": float(df["SMA_200"].iloc[-1]),
        # Positional flags — convenient for the LLM to reason over without arithmetic
        "price_above_sma_50": bool(df["Close"].iloc[-1] > df["SMA_50"].iloc[-1]),
        "price_above_sma_200": bool(df["Close"].iloc[-1] > df["SMA_200"].iloc[-1]),
        "sma_50_above_sma_200": bool(df["SMA_50"].iloc[-1] > df["SMA_200"].iloc[-1]),
    }
