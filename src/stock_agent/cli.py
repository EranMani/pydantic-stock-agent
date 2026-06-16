"""Command-line interface for the Pydantic Stock Agent demo.

Provides one obvious command for real analysis and a deterministic mock mode
that can run from a fresh clone without API keys or network access.
"""

import argparse
import asyncio
import json
import re
import sys

from stock_agent.mock_data import build_mock_report
from stock_agent.models.context import ScoringStrategy
from stock_agent.models.report import StockReport

TICKER_PATTERN = re.compile(r"^[A-Z][A-Z0-9.-]{0,9}$")


def validate_ticker(ticker: str) -> str:
    """Validate and normalize a ticker symbol for CLI use."""
    normalized = ticker.strip().upper()
    if not TICKER_PATTERN.fullmatch(normalized):
        raise ValueError(
            "ticker must be 1-10 characters using letters, numbers, '.', or '-'"
        )
    return normalized


def _build_parser() -> argparse.ArgumentParser:
    """Construct and return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="stock-agent",
        description="PydanticAI stock research demo with typed output and optional deterministic mock mode.",
    )
    parser.add_argument(
        "ticker_arg",
        nargs="?",
        help="Stock ticker symbol to analyse. Kept for compatibility with python -m stock_agent.main AAPL.",
    )
    parser.add_argument(
        "--ticker",
        dest="ticker",
        default=None,
        help="Stock ticker symbol to analyse (e.g. NVDA, AAPL, MSFT).",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run with bundled deterministic demo data. No API keys, network, yfinance, or LLM required.",
    )
    parser.add_argument(
        "--fundamental-weight",
        type=float,
        default=0.5,
        metavar="W",
        help="Weight applied to the fundamental score. Must sum to 1.0 with --technical-weight. Default: 0.5.",
    )
    parser.add_argument(
        "--technical-weight",
        type=float,
        default=0.5,
        metavar="W",
        help="Weight applied to the technical score. Must sum to 1.0 with --fundamental-weight. Default: 0.5.",
    )
    parser.add_argument(
        "--indicators",
        nargs="+",
        metavar="INDICATOR",
        default=None,
        help="Specific technical indicators to include (e.g. trend_template vcp macd).",
    )
    parser.add_argument(
        "--metrics",
        nargs="+",
        metavar="METRIC",
        default=None,
        help="Specific fundamental metrics to include (e.g. pe_ratio revenue_growth).",
    )
    return parser


def _build_strategy(args: argparse.Namespace) -> ScoringStrategy:
    """Build and validate the scoring strategy from parsed CLI args."""
    strategy_kwargs: dict[str, object] = {
        "fundamental_weight": args.fundamental_weight,
        "technical_weight": args.technical_weight,
    }
    if args.indicators is not None:
        strategy_kwargs["technical_indicators"] = args.indicators
    if args.metrics is not None:
        strategy_kwargs["fundamental_metrics"] = args.metrics
    return ScoringStrategy(**strategy_kwargs)


def _print_report(report: StockReport) -> None:
    """Print the structured report as JSON followed by a compact summary."""
    print(json.dumps(report.model_dump(mode="json"), indent=2))
    print()
    print("Summary")
    print(f"{report.ticker} ({report.company_name}) - {report.recommendation}")
    print(f"Weighted score: {report.weighted_score:.1f} | Confidence: {report.confidence}")
    if report.market_summary:
        print(report.market_summary)


def main() -> None:
    """Parse CLI arguments, run analysis, and print a validated StockReport."""
    parser = _build_parser()
    args = parser.parse_args()

    ticker_input = args.ticker or args.ticker_arg or "NVDA"

    try:
        ticker = validate_ticker(ticker_input)
        strategy = _build_strategy(args)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.mock:
        report = build_mock_report(ticker)
    else:
        from stock_agent.agent import run_analysis

        print(
            f"Analysing {ticker} with weights: "
            f"fundamental={strategy.fundamental_weight}, technical={strategy.technical_weight}"
        )
        report = asyncio.run(run_analysis(ticker, strategy))

    _print_report(report)


if __name__ == "__main__":
    main()
