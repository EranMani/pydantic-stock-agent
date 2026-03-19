"""Manual test script for Step 26 — agent wiring and tool validation.

Run with:
    uv run python scripts/test_agent_wiring.py

Tests:
  1. Agent loads with all 5 tools registered
  2. TestModel run — verifies agent wiring, schema, and dependency injection
     without making any real API or network calls
  3. Direct tool calls — verifies each tool executes correctly end-to-end
     (these DO make real yfinance / DuckDuckGo calls for AAPL)
"""

import asyncio
import os
from unittest.mock import MagicMock

# Provide a dummy API key so _resolve_model() doesn't raise at import time
os.environ.setdefault("OPENAI_API_KEY", "test-key")

from pydantic_ai.models.test import TestModel

from stock_agent.agent import agent
from stock_agent.models.context import AgentDependencies, ScoringStrategy
from stock_agent.models.report import StockReport
from stock_agent.tools.fundamental_tools import (
    get_fundamental_data,
    get_peer_reports,
    summarize_news_and_extract_risks,
)
from stock_agent.tools.technical_tools import get_moving_average_signal, get_technical_data


def make_ctx(strategy: ScoringStrategy | None = None) -> MagicMock:
    """Build a minimal mock RunContext — tools only access ctx.deps.strategy."""
    ctx = MagicMock()
    ctx.deps = AgentDependencies(strategy=strategy or ScoringStrategy())
    return ctx

TICKER = "ONDS"
COMPANY = "Ondas Holdings"


# ---------------------------------------------------------------------------
# Test 1 — Tool registration
# ---------------------------------------------------------------------------
def test_tool_registration() -> None:
    """Verify all 5 tools are registered on the agent."""
    print("\n--- Test 1: Tool Registration ---")
    tools = agent._function_toolset.tools
    expected = {
        "get_fundamental_data",
        "get_technical_data",
        "get_peer_reports",
        "get_moving_average_signal",
        "summarize_news_and_extract_risks",
    }
    registered = set(tools.keys())
    missing = expected - registered
    assert not missing, f"Missing tools: {missing}"
    print(f"  PASS — {len(registered)} tools registered: {sorted(registered)}")


# ---------------------------------------------------------------------------
# Test 2 — TestModel run (no real API calls)
# ---------------------------------------------------------------------------
async def test_testmodel_run() -> None:
    """Run the agent with TestModel to verify schema and dependency injection.

    call_tools=[] skips tool invocations entirely — no network calls made.
    custom_output_args provides a valid StockReport so datetime/enum validation passes.
    This verifies: agent config, system prompt wiring, output_type schema, deps injection.
    """
    from datetime import datetime, timezone

    print("\n--- Test 2: TestModel Agent Run (no tool calls, no network) ---")
    deps = AgentDependencies(strategy=ScoringStrategy())

    valid_output = {
        "ticker": TICKER,
        "analysis_date": datetime.now(timezone.utc).isoformat(),
        "fundamental_score": 7.5,
        "technical_score": 8.0,
        "weighted_score": 7.75,
        "summary": "Test summary produced by TestModel.",
        "recommendation": "BUY",
        "peers": [],
    }

    with agent.override(model=TestModel(call_tools=[], custom_output_args=valid_output)):
        result = await agent.run(f"Analyse {TICKER}", deps=deps)

    assert isinstance(result.output, StockReport), f"Expected StockReport, got {type(result.output)}"
    print(f"  PASS — StockReport returned: ticker={result.output.ticker!r}, recommendation={result.output.recommendation!r}")
    print(f"         weighted_score={result.output.weighted_score}, peers={result.output.peers}")


# ---------------------------------------------------------------------------
# Test 3 — Direct tool calls (real network calls)
# ---------------------------------------------------------------------------
async def test_tool_get_fundamental_data() -> None:
    """Call get_fundamental_data directly — makes real yfinance call for AAPL."""
    print("\n--- Test 3a: get_fundamental_data (real yfinance) ---")
    result = await get_fundamental_data(make_ctx(), TICKER)
    print(f"  PASS — FundamentalData: pe_ratio={result.pe_ratio}, market_cap={result.market_cap:.2e}, score={result.score:.2f}")


async def test_tool_get_technical_data() -> None:
    """Call get_technical_data directly — makes real yfinance call for AAPL."""
    print("\n--- Test 3b: get_technical_data (real yfinance) ---")
    result = await get_technical_data(make_ctx(), TICKER)
    print(f"  PASS — TechnicalData: sma_50={result.sma_50:.2f}, trend_template={result.trend_template_passed}, vcp={result.vcp_detected}, score={result.score:.2f}")


async def test_tool_get_moving_average_signal() -> None:
    """Call get_moving_average_signal directly — makes real yfinance call for AAPL."""
    print("\n--- Test 3c: get_moving_average_signal (real yfinance) ---")
    result = await get_moving_average_signal(make_ctx(), TICKER)
    assert "current_price" in result and "sma_50" in result
    print(f"  PASS — MA signal: price={result['current_price']:.2f}, sma_50={result['sma_50']:.2f}, sma_200={result['sma_200']:.2f}")
    print(f"         above_sma_50={result['price_above_sma_50']}, above_sma_200={result['price_above_sma_200']}")


async def test_tool_get_peer_reports() -> None:
    """Call get_peer_reports directly — expect empty list (Step 30 stub)."""
    print("\n--- Test 3d: get_peer_reports (Step 30 stub) ---")
    result = await get_peer_reports(make_ctx(), TICKER)
    assert isinstance(result, list)
    print(f"  PASS — peer_reports returned: {result}")


async def test_tool_summarize_news() -> None:
    """Call summarize_news_and_extract_risks — real DuckDuckGo + Ollama llama3.2."""
    print("\n--- Test 3e: summarize_news_and_extract_risks (real DuckDuckGo + Ollama) ---")
    result = await summarize_news_and_extract_risks(make_ctx(), TICKER, COMPANY)
    print(f"  PASS — NewsSummary returned")
    print(f"\n  Summary:\n  {result.summary}")
    if result.risk_flags:
        print(f"\n  Risk flags ({len(result.risk_flags)}):")
        for flag in result.risk_flags:
            print(f"    • {flag[:120]}")
    else:
        print(f"\n  Risk flags: none detected")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
async def main() -> None:
    """Run all tests in sequence."""
    print("=" * 60)
    print("Step 26 — Agent Wiring & Tool Validation")
    print("=" * 60)

    test_tool_registration()
    await test_testmodel_run()
    await test_tool_get_fundamental_data()
    await test_tool_get_technical_data()
    await test_tool_get_moving_average_signal()
    await test_tool_get_peer_reports()
    await test_tool_summarize_news()

    print("\n" + "=" * 60)
    print("All tests passed.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
