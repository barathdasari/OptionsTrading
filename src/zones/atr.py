"""
Average True Range (ATR) — causal computation.

ATR at bar t uses only bars up to and including t-1.
Never uses bar t's own data — that would be look-ahead for intraday signals.

For daily bars this means: ATR on Monday = computed from data through Friday.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_atr(df: pd.DataFrame, period: int = 14,
                shift: bool = True) -> pd.Series:
    """
    Compute ATR series from OHLCV dataframe.

    Parameters
    ----------
    df     : DataFrame with columns [high, low, close]
    period : lookback (default 14, as per EXP-001 spec)
    shift  : if True (default), shift result by 1 so that ATR[t] uses
             data through t-1 only (causal mode).
             Set False only for research-discovery / visualisation purposes.

    Returns
    -------
    pd.Series of ATR values, same index as df.
    NaN for the first (period + 1) rows when shift=True.
    """
    high = df["high"]
    low = df["low"]
    close = df["close"]

    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)

    # Wilder's smoothed ATR (standard definition)
    atr = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    if shift:
        # Shift forward so ATR[t] reflects data through t-1 only
        atr = atr.shift(1)

    atr.name = f"atr_{period}"
    return atr


def compute_atr_percentile(atr: pd.Series, lookback: int = 252) -> pd.Series:
    """
    Compute rolling percentile rank of ATR over a lookback window.
    Used for volatility-regime classification.

    Returns values in [0, 1].
    """
    def pct_rank(x: np.ndarray) -> float:
        if len(x) < 2:
            return float("nan")
        return float(np.sum(x[:-1] < x[-1]) / (len(x) - 1))

    return atr.rolling(lookback, min_periods=lookback // 2).apply(
        pct_rank, raw=True
    ).rename("atr_percentile")
