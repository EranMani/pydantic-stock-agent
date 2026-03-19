"""Minervini Trend Template checks and VCP detection for the technical analysis pipeline.

Each function in this module is a single boolean condition from Mark Minervini's
Trend Template. They are composed together in check_trend_template() (Step 23)
to produce a single True/False verdict.

All functions receive the enriched OHLCV DataFrame — SMA columns must have been
appended by add_moving_averages() before any function here is called.
"""

import pandas as pd


def ma50_above_ma150_and_ma200(df: pd.DataFrame) -> bool:
    """Return True if SMA_50 is strictly above both SMA_150 and SMA_200 at the latest row.

    Confirms the moving averages are in correct bullish order across all timeframes —
    short-term trend leading medium and long-term trends upward.
    """
    sma_50 = df["SMA_50"].iloc[-1]
    return bool(sma_50 > df["SMA_150"].iloc[-1] and sma_50 > df["SMA_200"].iloc[-1])


def ma200_trending_up(df: pd.DataFrame, lookback_days: int = 20) -> bool:
    """Return True if SMA_200 today is strictly higher than it was lookback_days ago.

    A rising 200-day MA confirms sustained institutional accumulation over months.
    A flat or declining 200-day MA is a warning sign even if price is still above it.
    """
    # Requires at least lookback_days + 1 rows of SMA_200 data
    return bool(df["SMA_200"].iloc[-1] > df["SMA_200"].iloc[-lookback_days])


def price_above_mas(df: pd.DataFrame) -> bool:
    """Return True if the latest close is strictly above both SMA_150 and SMA_200.

    Equal-to does not qualify — the price must have broken clear of both moving
    averages, not merely touched them.
    """
    close = df["Close"].iloc[-1]
    # Both conditions must hold — one MA above is not sufficient
    return bool(close > df["SMA_150"].iloc[-1] and close > df["SMA_200"].iloc[-1])
