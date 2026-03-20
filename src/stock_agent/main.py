"""CLI entry point for the Autonomous Stock Analyst Agent.

Parses user arguments (ticker, scoring weights, indicator list), constructs a
ScoringStrategy, and dispatches a full analysis via asyncio.run(run_analysis()).
The resulting StockReport is printed as indented JSON to stdout.

Usage:
    uv run python -m stock_agent.main AAPL
    uv run python -m stock_agent.main AAPL --fundamental-weight 0.6 --technical-weight 0.4
    uv run python -m stock_agent.main AAPL --indicators trend_template vcp
"""

import argparse
import asyncio
import json
import sys

from stock_agent.agent import run_analysis
from stock_agent.models.context import ScoringStrategy


def _build_parser() -> argparse.ArgumentParser:
    """Construct and return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="stock-agent",
        description="Autonomous PydanticAI stock analyst — deterministic pipelines + structured LLM reasoning.",
    )
    parser.add_argument(
        "ticker",
        type=str,
        help="Stock ticker symbol to analyse (e.g. AAPL, MSFT, NVDA).",
    )
    parser.add_argument(
        "--fundamental-weight",
        type=float,
        default=0.5,
        metavar="W",
        help="Weight applied to the fundamental score (0.0–1.0). Must sum to 1.0 with --technical-weight. Default: 0.5.",
    )
    parser.add_argument(
        "--technical-weight",
        type=float,
        default=0.5,
        metavar="W",
        help="Weight applied to the technical score (0.0–1.0). Must sum to 1.0 with --fundamental-weight. Default: 0.5.",
    )
    parser.add_argument(
        "--indicators",
        nargs="+",
        metavar="INDICATOR",
        default=None,
        help="Specific technical indicators to include (e.g. trend_template vcp macd). Defaults to strategy defaults.",
    )
    parser.add_argument(
        "--metrics",
        nargs="+",
        metavar="METRIC",
        default=None,
        help="Specific fundamental metrics to include (e.g. pe_ratio revenue_growth). Defaults to strategy defaults.",
    )
    return parser


def main() -> None:
    """Parse CLI arguments, build a ScoringStrategy, run the analysis, and print the StockReport as JSON."""
    parser = _build_parser()
    args = parser.parse_args()

    # Build ScoringStrategy from CLI args — validation (weights sum to 1.0) is
    # enforced by the model_validator in ScoringStrategy, so errors surface here
    # with a clean message before any network calls are made.
    strategy_kwargs: dict = {
        "fundamental_weight": args.fundamental_weight,
        "technical_weight": args.technical_weight,
    }
    if args.indicators is not None:
        strategy_kwargs["technical_indicators"] = args.indicators
    if args.metrics is not None:
        strategy_kwargs["fundamental_metrics"] = args.metrics

    try:
        strategy = ScoringStrategy(**strategy_kwargs)
    except ValueError as exc:
        # ScoringStrategy.weights_sum_to_one raised — surface cleanly without a traceback
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    ticker = args.ticker.upper()
    print(f"Analysing {ticker} with weights: fundamental={strategy.fundamental_weight}, technical={strategy.technical_weight}")

    report = asyncio.run(run_analysis(ticker, strategy))

    # Serialize StockReport to indented JSON for readable CLI output
    print(json.dumps(report.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
