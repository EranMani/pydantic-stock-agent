"""OHLCV data extraction and validation for the technical analysis pipeline.

Uses yfinance as the data source — replacing the original tvdatafeed plan.
yfinance returns capitalised column names (Open, High, Low, Close, Volume)
which all downstream indicator modules must reference accordingly.

All yfinance calls are synchronous and blocking — wrapped with asyncio.to_thread()
to keep the event loop free during network I/O.
"""

import asyncio

import pandas as pd
import yfinance as yf

# Minimum number of rows required after cleaning — SMA_200 needs at least 200 bars
_MIN_ROWS = 200

# Columns that must be present in every OHLCV DataFrame passed to indicator modules
_REQUIRED_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


async def fetch_ohlcv(ticker: str, n_bars: int = 300) -> pd.DataFrame:
    """Fetch daily OHLCV data for a ticker via yfinance and return a validated DataFrame.

    Wraps the synchronous yfinance call in asyncio.to_thread() to avoid blocking
    the event loop. Passes the raw DataFrame through validate_ohlcv() before returning.
    """
    # yfinance .history() is a blocking HTTP call — offload to thread pool
    df: pd.DataFrame = await asyncio.to_thread(_fetch_history, ticker)
    return validate_ohlcv(df)


def validate_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and clean a raw OHLCV DataFrame before passing it to indicator modules.

    Checks required columns exist, fills NaN values forward then backward,
    and raises ValueError if fewer than 200 rows remain after cleaning.
    """
    # Verify all required OHLCV columns are present
    missing = [c for c in _REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"OHLCV DataFrame missing required columns: {missing}")

    # Fill NaN forward then backward — handles missing trading sessions gracefully
    df = df.ffill().bfill()

    # Enforce minimum row count — SMA_200 requires at least 200 bars
    if len(df) < _MIN_ROWS:
        raise ValueError(
            f"Insufficient data: {len(df)} rows after cleaning, need at least {_MIN_ROWS}"
        )

    return df


def _fetch_history(ticker: str) -> pd.DataFrame:
    """Synchronous helper that calls yfinance — intended for use via asyncio.to_thread() only."""
    return yf.Ticker(ticker).history(period="2y")
