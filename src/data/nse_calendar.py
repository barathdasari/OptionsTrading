"""
NSE trading calendar utilities.

Uses pandas-market-calendars which includes the NSE holiday schedule.
Provides helpers for:
  - listing trading days in a date range
  - detecting gaps in a timeseries
  - tagging expiry days (loaded from contract metadata)
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import pandas as pd
import pandas_market_calendars as mcal

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_DIR = PROJECT_ROOT / "data" / "metadata" / "contract"

# NSE calendar name in pandas-market-calendars
_NSE_CAL_NAME = "NSE"


# ---------------------------------------------------------------------------
# Trading day queries
# ---------------------------------------------------------------------------

@lru_cache(maxsize=8)
def get_trading_days(start: str, end: str) -> pd.DatetimeIndex:
    """
    Return NSE trading days between start and end inclusive.

    Parameters
    ----------
    start, end : 'YYYY-MM-DD'
    """
    cal = mcal.get_calendar(_NSE_CAL_NAME)
    schedule = cal.schedule(start_date=start, end_date=end)
    days = mcal.date_range(schedule, frequency="1D")
    # mcal returns UTC timestamps at market-open; normalise to date only
    return pd.DatetimeIndex(
        pd.Series(days).dt.normalize().dt.tz_localize(None).unique()
    )


def is_trading_day(date: str | pd.Timestamp) -> bool:
    ts = pd.Timestamp(date).normalize()
    days = get_trading_days(
        ts.strftime("%Y-%m-%d"),
        ts.strftime("%Y-%m-%d"),
    )
    return len(days) > 0


def trading_days_between(start: str, end: str) -> int:
    return len(get_trading_days(start, end))


# ---------------------------------------------------------------------------
# Gap detection
# ---------------------------------------------------------------------------

def find_gaps(df: pd.DataFrame, start: str, end: str,
              timeframe: str = "1D") -> pd.DataFrame:
    """
    Find missing bars in df compared to expected trading schedule.

    Parameters
    ----------
    df        : DataFrame with DatetimeIndex (Asia/Kolkata or tz-naive dates)
    start/end : date range to check
    timeframe : '1D' for daily, '5min' for 5-minute bars

    Returns
    -------
    DataFrame with columns [expected_timestamp, gap_type]
    where gap_type is 'missing_day' or 'missing_bar'.
    """
    if timeframe == "1D":
        return _find_daily_gaps(df, start, end)
    elif timeframe == "5min":
        return _find_intraday_gaps(df, start, end, freq="5min")
    else:
        raise ValueError(f"Unsupported timeframe: {timeframe}")


def _find_daily_gaps(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    expected = get_trading_days(start, end)
    # Normalise df index to tz-naive dates for comparison
    actual_dates = df.index.normalize().tz_localize(None)
    missing = expected.difference(actual_dates)
    if len(missing) == 0:
        return pd.DataFrame(columns=["expected_timestamp", "gap_type"])
    return pd.DataFrame({
        "expected_timestamp": missing,
        "gap_type": "missing_day",
    })


def _find_intraday_gaps(df: pd.DataFrame, start: str, end: str,
                        freq: str = "5min") -> pd.DataFrame:
    """
    For intraday data: check each trading day has bars from 09:15 to 15:25.
    """
    trading_days = get_trading_days(start, end)
    missing_records = []

    for day in trading_days:
        day_str = day.strftime("%Y-%m-%d")
        session_start = pd.Timestamp(f"{day_str} 09:15:00", tz="Asia/Kolkata")
        session_end = pd.Timestamp(f"{day_str} 15:25:00", tz="Asia/Kolkata")
        expected_bars = pd.date_range(session_start, session_end, freq=freq,
                                      tz="Asia/Kolkata")

        mask = (df.index >= session_start) & (df.index <= session_end)
        actual_bars = df.index[mask]

        for bar in expected_bars:
            if bar not in actual_bars:
                missing_records.append({
                    "expected_timestamp": bar,
                    "gap_type": "missing_bar",
                })

    if not missing_records:
        return pd.DataFrame(columns=["expected_timestamp", "gap_type"])
    return pd.DataFrame(missing_records)


# ---------------------------------------------------------------------------
# Expiry tagging
# ---------------------------------------------------------------------------

def load_expiry_schedule() -> pd.DataFrame:
    """
    Load expiry schedule from data/metadata/contract/*.csv files.

    Expected CSV columns: instrument, expiry_date, expiry_type
    expiry_type: 'weekly' | 'monthly'

    If no files found, returns empty DataFrame and logs a warning.
    Expiry dates are instrument/date-specific — never hard-coded here.
    """
    files = sorted(CONTRACT_DIR.glob("expiry_schedule_*.csv"))
    if not files:
        logger.warning(
            "No expiry schedule files found in %s. "
            "Download from NSE and place as expiry_schedule_INSTRUMENT.csv",
            CONTRACT_DIR,
        )
        return pd.DataFrame(columns=["instrument", "expiry_date", "expiry_type"])

    frames = [pd.read_csv(f, parse_dates=["expiry_date"]) for f in files]
    df = pd.concat(frames, ignore_index=True)
    df["expiry_date"] = pd.to_datetime(df["expiry_date"]).dt.normalize()
    return df


def tag_expiry_days(df: pd.DataFrame, instrument: str) -> pd.Series:
    """
    Return a boolean Series aligned to df.index: True if the bar's date
    is an expiry day for the given instrument.

    df must have a DatetimeIndex.
    """
    schedule = load_expiry_schedule()
    inst_expiries = schedule[schedule["instrument"] == instrument]["expiry_date"]
    expiry_set = set(inst_expiries.dt.normalize())

    bar_dates = df.index.normalize().tz_localize(None)
    return pd.Series(
        bar_dates.isin(expiry_set),
        index=df.index,
        name="is_expiry_day",
    )
