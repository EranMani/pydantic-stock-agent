"""Tests for the recruiter-friendly CLI demo path."""

import json
import subprocess
import sys

import pytest
from pydantic import ValidationError

from stock_agent.cli import validate_ticker
from stock_agent.mock_data import build_mock_report
from stock_agent.models.report import StockReport


def test_validate_ticker_accepts_common_symbols() -> None:
    """Ticker validation accepts and normalizes ordinary exchange symbols."""
    assert validate_ticker("aapl") == "AAPL"
    assert validate_ticker("brk.b") == "BRK.B"
    assert validate_ticker("rds-a") == "RDS-A"


@pytest.mark.parametrize("ticker", ["", "bad ticker", "$AAPL", "TOO-LONG-TICKER"])
def test_validate_ticker_rejects_bad_input(ticker: str) -> None:
    """Ticker validation rejects empty, spaced, symbolic, and overlong values."""
    with pytest.raises(ValueError):
        validate_ticker(ticker)


def test_mock_report_returns_expected_shape() -> None:
    """Mock mode returns a valid, deterministic StockReport."""
    report = build_mock_report("nvda")

    assert report.ticker == "NVDA"
    assert report.company_name == "NVIDIA Corporation"
    assert report.sources
    assert report.risks
    assert report.calculation == "(7.4 x 0.50) + (8.2 x 0.50) = 7.8"


def test_stock_report_validation_rejects_invalid_confidence() -> None:
    """The typed output contract rejects confidence values outside the schema."""
    payload = build_mock_report("NVDA").model_dump(mode="python")
    payload["confidence"] = "certain"

    with pytest.raises(ValidationError):
        StockReport(**payload)


def test_mock_report_serializes_to_json() -> None:
    """A StockReport can serialize to JSON for stable CLI output."""
    report = build_mock_report("AAPL")

    data = json.loads(report.model_dump_json())

    assert data["ticker"] == "AAPL"
    assert data["confidence"] == "medium"


def test_cli_mock_mode_runs_without_api_keys() -> None:
    """The mock CLI path runs in a subprocess without importing cloud agent setup."""
    result = subprocess.run(
        [sys.executable, "-m", "stock_agent.main", "--ticker", "NVDA", "--mock"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert '"ticker": "NVDA"' in result.stdout
    assert "Summary" in result.stdout
    assert "NVIDIA Corporation" in result.stdout
