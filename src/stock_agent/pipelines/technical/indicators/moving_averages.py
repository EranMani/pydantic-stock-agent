"""Moving average indicators for the technical analysis pipeline.

Appends SMA_50, SMA_150, SMA_200 columns to an OHLCV DataFrame using pandas-ta,
and provides a helper to extract 52-week high/low levels.

All functions follow the Chain of Responsibility pattern — each module appends
columns to the DataFrame and returns it, ready for the next indicator module.
"""

import pandas as pd
import pandas_ta as ta

# Number of trading days in one calendar year — used for 52-week level calculation
_TRADING_DAYS_PER_YEAR = 252


def add_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
    """Append SMA_50, SMA_150, and SMA_200 columns to the DataFrame using pandas-ta.

    Mutates and returns the input DataFrame so it can be chained with other
    indicator modules. Requires at least 200 rows of Close data (enforced upstream
    by validate_ohlcv).
    """
    df["SMA_50"] = ta.sma(df["Close"], length=50)
    df["SMA_150"] = ta.sma(df["Close"], length=150)
    df["SMA_200"] = ta.sma(df["Close"], length=200)
    return df


def calculate_52_week_levels(df: pd.DataFrame) -> tuple[float, float]:
    """Return (high_52w, low_52w) from the last 252 trading days of Close data.

    Uses the last _TRADING_DAYS_PER_YEAR rows so the result reflects the true
    rolling 52-week window rather than a calendar-year boundary.
    """
    window = df["Close"].iloc[-_TRADING_DAYS_PER_YEAR:]
    high_52w = float(window.max())
    low_52w = float(window.min())
    return high_52w, low_52w
