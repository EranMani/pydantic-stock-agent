"""MACD indicator for the technical analysis pipeline.

Appends MACD line, signal line, and histogram columns to an OHLCV DataFrame
using pandas-ta with standard 12/26/9 parameters.

Column names follow pandas-ta's default convention:
  MACD_12_26_9  — MACD line (12-day EMA minus 26-day EMA)
  MACDs_12_26_9 — signal line (9-day EMA of the MACD line)
  MACDh_12_26_9 — histogram (MACD line minus signal line)
"""

import pandas as pd
import pandas_ta as ta


def add_macd(df: pd.DataFrame) -> pd.DataFrame:
    """Append MACD_12_26_9, MACDs_12_26_9, and MACDh_12_26_9 columns using pandas-ta.

    Uses standard parameters: fast=12, slow=26, signal=9.
    Mutates and returns the input DataFrame so it can be chained with other
    indicator modules.
    """
    # pandas_ta.macd() returns a DataFrame with all three columns — join onto main df
    macd_df = ta.macd(df["Close"], fast=12, slow=26, signal=9)
    df[macd_df.columns] = macd_df
    return df
