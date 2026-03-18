"""Fundamental scoring algorithm — converts FundamentalData into a score in [1.0, 10.0].

Scoring flow:
  1. Compute a normalised sub-score (0.0–1.0) for each active metric
  2. Re-normalise the base weights of active metrics so they sum to 1.0
  3. Weighted sum → scale to [1.0, 10.0] → clamp

Only metrics listed in strategy.fundamental_metrics are included — excluding a
metric never affects the score of remaining metrics (dynamic routing via ScoringStrategy).
"""

from stock_agent.config import METRIC_NORMALISATION, METRIC_WEIGHTS
from stock_agent.models.context import ScoringStrategy
from stock_agent.models.report import FundamentalData


def calculate_fundamental_score(
    data: FundamentalData, strategy: ScoringStrategy
) -> float:
    """Compute a fundamental score in [1.0, 10.0] based on active strategy metrics.

    Dynamically routes calculations through only the metrics listed in
    strategy.fundamental_metrics — excluding a metric produces identical results
    regardless of its field value.
    """
    weighted_sum = 0.0

    # Fetch base weights for active metrics only, then re-normalise so they sum to 1.0
    active_weights = {
        metric: METRIC_WEIGHTS[metric]
        for metric in strategy.fundamental_metrics
        if metric in METRIC_WEIGHTS
    }
    total_weight = sum(active_weights.values())

    # Guard against empty or unknown metric lists
    if total_weight == 0.0:
        return 1.0

    for metric, base_weight in active_weights.items():
        normalised_weight = base_weight / total_weight  # re-normalise to sum to 1.0
        sub_score = _compute_sub_score(metric, data)
        weighted_sum += sub_score * normalised_weight

    # Scale from [0.0, 1.0] to [1.0, 10.0] then clamp as safety net
    final_score = 1.0 + weighted_sum * 9.0
    return max(1.0, min(10.0, final_score))


def _compute_sub_score(metric: str, data: FundamentalData) -> float:
    """Convert a single metric's raw value into a normalised sub-score in [0.0, 1.0].

    Returns 0.0 for None values — missing data is treated as worst-case signal.
    Uses normalisation ranges from METRIC_NORMALISATION in config.py.
    """
    value: float | None = getattr(data, metric, None)

    # Missing data scores 0.0 — unknown is treated conservatively
    if value is None:
        return 0.0

    max_val, higher_is_better = METRIC_NORMALISATION.get(metric, (1.0, True))

    # Clamp raw value to [0, max_val] before normalising
    clamped = max(0.0, min(float(value), max_val))

    if higher_is_better:
        # Higher raw value → higher sub-score (e.g. revenue_growth, market_cap)
        return clamped / max_val
    else:
        # Lower raw value → higher sub-score (e.g. pe_ratio, beta)
        return 1.0 - (clamped / max_val)
