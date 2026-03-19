"""Technical scoring pipeline — converts indicator results into a TechnicalData score.

Dynamically routes through only the indicators listed in ScoringStrategy.technical_indicators.
Each indicator produces a boolean signal (True=1.0, False=0.0) which is weighted,
summed, and scaled to [1.0, 10.0].

INDICATOR_MODULES maps strategy string names to scorer functions — each function
receives the enriched DataFrame and returns a bool. The adder functions
(add_moving_averages, add_macd) are run as preprocessing before scoring begins.
"""

from typing import Callable

import pandas as pd

from stock_agent.config import INDICATOR_WEIGHTS
from stock_agent.models.context import ScoringStrategy
from stock_agent.models.report import TechnicalData
from stock_agent.pipelines.technical.indicators.macd import add_macd
from stock_agent.pipelines.technical.indicators.moving_averages import (
    add_moving_averages,
    calculate_52_week_levels,
)
from stock_agent.pipelines.technical.indicators.trend_setups import (
    check_trend_template,
    detect_vcp,
    ma50_above_ma150_and_ma200,
)

# Maps strategy indicator names to boolean scorer functions.
# add_macd is run as preprocessing; macd entry checks MACD line above signal.
INDICATOR_MODULES: dict[str, Callable[[pd.DataFrame], bool]] = {
    "trend_template": check_trend_template,
    "vcp": detect_vcp,
    # macd: True if MACD line is above signal line (bullish momentum)
    "macd": lambda df: bool(df["MACD_12_26_9"].iloc[-1] > df["MACDs_12_26_9"].iloc[-1]),
    # moving_averages: True if MAs are in correct bullish order
    "moving_averages": ma50_above_ma150_and_ma200,
}


def calculate_technical_score(df: pd.DataFrame, strategy: ScoringStrategy) -> TechnicalData:
    """Score the technical setup and return a populated TechnicalData instance.

    Runs only the indicator modules listed in strategy.technical_indicators.
    Weights are re-normalised so excluding an indicator never shrinks the score range.
    Output score is always clamped to [1.0, 10.0].
    """
    # Step 1 — enrich DataFrame with all required columns upfront
    df = add_moving_averages(df)
    # Only run add_macd if macd is an active indicator — avoids unnecessary computation
    if "macd" in strategy.technical_indicators:
        df = add_macd(df)

    # Step 2 — compute boolean signal for each active indicator
    active_signals: dict[str, float] = {}
    for name in strategy.technical_indicators:
        scorer_fn = INDICATOR_MODULES[name]
        # Convert bool to float: True → 1.0, False → 0.0
        active_signals[name] = 1.0 if scorer_fn(df) else 0.0

    # Step 3 — re-normalise weights of active indicators so they sum to 1.0
    active_weights = {name: INDICATOR_WEIGHTS[name] for name in active_signals}
    total_weight = sum(active_weights.values())
    normalised = {name: w / total_weight for name, w in active_weights.items()}

    # Step 4 — weighted sum → scale to [1.0, 10.0] → clamp
    weighted_sum = sum(active_signals[n] * normalised[n] for n in active_signals)
    raw_score = 1.0 + weighted_sum * 9.0
    final_score = max(1.0, min(10.0, raw_score))

    # Step 5 — extract point-in-time values for TechnicalData fields
    high_52w, low_52w = calculate_52_week_levels(df)

    return TechnicalData(
        sma_50=float(df["SMA_50"].iloc[-1]),
        sma_150=float(df["SMA_150"].iloc[-1]),
        sma_200=float(df["SMA_200"].iloc[-1]),
        high_52w=high_52w,
        low_52w=low_52w,
        trend_template_passed=check_trend_template(df),
        vcp_detected=detect_vcp(df),
        score=final_score,
    )
