"""Minervini Trend Template checks and VCP detection for the technical analysis pipeline.

Each function in this module is a single boolean condition from Mark Minervini's
Trend Template. They are composed together in check_trend_template() (Step 23)
to produce a single True/False verdict.

All functions receive the enriched OHLCV DataFrame — SMA columns must have been
appended by add_moving_averages() before any function here is called.
"""

import pandas as pd


def price_above_mas(df: pd.DataFrame) -> bool:
    """Return True if the latest close is strictly above both SMA_150 and SMA_200.

    Equal-to does not qualify — the price must have broken clear of both moving
    averages, not merely touched them.
    """
    close = df["Close"].iloc[-1]
    # Both conditions must hold — one MA above is not sufficient
    return bool(close > df["SMA_150"].iloc[-1] and close > df["SMA_200"].iloc[-1])
