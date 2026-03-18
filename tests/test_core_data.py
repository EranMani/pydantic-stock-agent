"""Unit tests for OHLCV data validation and NaN handling in core_data.py.

These tests cover Step 15 acceptance criteria:
- A DataFrame with NaN rows in the middle passes validation after ffill/bfill
- A DataFrame with fewer than 200 rows raises ValueError
- Missing required columns raise ValueError
"""

import numpy as np
import pandas as pd
import pytest

from stock_agent.pipelines.technical.core_data import validate_ohlcv


def _make_ohlcv(rows: int) -> pd.DataFrame:
    """Helper that builds a minimal valid OHLCV DataFrame of the requested size."""
    return pd.DataFrame({
        "Open":   [100.0] * rows,
        "High":   [105.0] * rows,
        "Low":    [95.0]  * rows,
        "Close":  [102.0] * rows,
        "Volume": [1_000_000] * rows,
    })


def test_nan_in_middle_is_filled():
    """DataFrame with NaN rows in the middle passes validation after ffill/bfill."""
    df = _make_ohlcv(250)
    # Inject NaN values in the middle rows
    df.loc[100:105, "Close"] = np.nan
    df.loc[50:52, "Volume"] = np.nan

    result = validate_ohlcv(df)

    assert result["Close"].isna().sum() == 0, "Close NaN not filled"
    assert result["Volume"].isna().sum() == 0, "Volume NaN not filled"
    # Filled values should match the surrounding known values (forward fill)
    assert result.loc[100, "Close"] == 102.0


def test_nan_at_start_is_filled_by_bfill():
    """NaN at the very start of the DataFrame is filled by bfill when ffill cannot help."""
    df = _make_ohlcv(250)
    df.loc[0:3, "Close"] = np.nan  # ffill has nothing to carry — bfill must handle this

    result = validate_ohlcv(df)

    assert result["Close"].isna().sum() == 0
    assert result.loc[0, "Close"] == 102.0  # filled backward from row 4


def test_insufficient_rows_raises_value_error():
    """DataFrame with fewer than 200 rows raises ValueError."""
    df = _make_ohlcv(150)

    with pytest.raises(ValueError, match="Insufficient data"):
        validate_ohlcv(df)


def test_exactly_200_rows_passes():
    """DataFrame with exactly 200 rows passes validation — boundary condition."""
    df = _make_ohlcv(200)
    result = validate_ohlcv(df)
    assert len(result) == 200


def test_missing_required_column_raises_value_error():
    """DataFrame missing a required column raises ValueError immediately."""
    df = _make_ohlcv(250)
    df = df.drop(columns=["Volume"])  # remove a required column

    with pytest.raises(ValueError, match="missing required columns"):
        validate_ohlcv(df)


def test_valid_dataframe_passes_unchanged():
    """A clean DataFrame with no NaN and sufficient rows passes through unchanged."""
    df = _make_ohlcv(300)
    result = validate_ohlcv(df)

    assert len(result) == 300
    assert result.isna().sum().sum() == 0
