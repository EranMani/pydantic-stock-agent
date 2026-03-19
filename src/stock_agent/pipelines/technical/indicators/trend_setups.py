"""Minervini Trend Template checks and VCP detection for the technical analysis pipeline.

Each function in this module is a single boolean condition from Mark Minervini's
Trend Template. They are composed together in check_trend_template() (Step 23)
to produce a single True/False verdict.

All functions receive the enriched OHLCV DataFrame — SMA columns must have been
appended by add_moving_averages() before any function here is called.
"""

import pandas as pd

from stock_agent.pipelines.technical.indicators.moving_averages import calculate_52_week_levels


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


def detect_volume_dryup(df: pd.DataFrame, lookback: int = 50, threshold: float = 0.7) -> bool:
    """Return True if the latest volume is below threshold × mean volume over the lookback window.

    A volume dry-up signals that sellers have backed off — the stock is consolidating
    quietly, which is a prerequisite for a healthy VCP base before a breakout.
    """
    avg_volume = df["Volume"].iloc[-lookback:].mean()
    # Latest volume below threshold × average → dry-up confirmed
    return bool(df["Volume"].iloc[-1] < threshold * avg_volume)


def price_above_mas(df: pd.DataFrame) -> bool:
    """Return True if the latest close is strictly above both SMA_150 and SMA_200.

    Equal-to does not qualify — the price must have broken clear of both moving
    averages, not merely touched them.
    """
    close = df["Close"].iloc[-1]
    # Both conditions must hold — one MA above is not sufficient
    return bool(close > df["SMA_150"].iloc[-1] and close > df["SMA_200"].iloc[-1])


def check_trend_template(df: pd.DataFrame) -> bool:
    """Return True only if all five Minervini Trend Template conditions are met.

    All conditions must pass — a single failure disqualifies the stock.
    Requires SMA columns to have been appended by add_moving_averages() first.
    """
    close = df["Close"].iloc[-1]
    high_52w, low_52w = calculate_52_week_levels(df)

    conditions = [
        price_above_mas(df),                    # close > SMA_150 and SMA_200
        ma200_trending_up(df),                  # SMA_200 rising over last 20 days
        ma50_above_ma150_and_ma200(df),         # SMA_50 > SMA_150 and SMA_200
        close > high_52w * 0.75,                # not more than 25% below 52w high
        close > low_52w * 1.30,                 # at least 30% above 52w low
    ]
    # All five conditions must be True — any False disqualifies the stock
    return all(conditions)


def detect_vcp(df: pd.DataFrame, contractions: int = 3) -> bool:
    """Return True if the last 60 bars show successive price range contractions.

    Splits the last 60 bars into equal windows and checks that each window's
    price range (max Close - min Close) is strictly narrower than the previous.
    A shrinking range signals that selling pressure is drying up — the stock is
    coiling before a potential breakout.
    """
    last_60 = df["Close"].iloc[-60:]
    window_size = 60 // contractions

    ranges: list[float] = []
    for i in range(contractions):
        window = last_60.iloc[i * window_size: (i + 1) * window_size]
        ranges.append(float(window.max() - window.min()))

    # Each successive range must be strictly narrower than the one before it
    return all(ranges[i] > ranges[i + 1] for i in range(len(ranges) - 1))
