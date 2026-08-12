"""
yfinance-based downloader for Bank Nifty daily OHLCV.

Ticker : ^NSEBANK  (Bank Nifty index)
Data   : daily OHLCV, adjusted, back to ~2000

Note on 5-min data:
  yfinance caps intraday history at 60 days. Use this module for daily data now.
  5-min pipeline will be added once Shoonya API account is active.
"""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

from src.data.storage import append_raw, raw_info

logger = logging.getLogger(__name__)

BANKNIFTY_TICKER = "^NSEBANK"
INSTRUMENT = "BANKNIFTY"
TIMEFRAME = "1D"

# Earliest reliable date for ^NSEBANK on yfinance
EARLIEST_START = "2000-01-01"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def download_banknifty_daily(
    start: str = EARLIEST_START,
    end: str | None = None,
    auto_append: bool = True,
) -> pd.DataFrame:
    """
    Download Bank Nifty daily OHLCV from yfinance and persist to raw Parquet.

    Parameters
    ----------
    start       : 'YYYY-MM-DD' start date
    end         : 'YYYY-MM-DD' end date (defaults to today)
    auto_append : if True, only downloads data newer than last stored date

    Returns
    -------
    DataFrame with columns [open, high, low, close, volume]
    and DatetimeIndex (Asia/Kolkata timezone, daily frequency).
    """
    if end is None:
        end = date.today().strftime("%Y-%m-%d")

    if auto_append:
        info = raw_info(INSTRUMENT, TIMEFRAME)
        if info["exists"]:
            existing = _load_existing_last_date()
            if existing is not None:
                new_start = (existing + timedelta(days=1)).strftime("%Y-%m-%d")
                if new_start > end:
                    logger.info("Data already up to date (last date: %s)", existing)
                    return pd.DataFrame()
                logger.info("Auto-append: downloading %s to %s", new_start, end)
                start = new_start

    logger.info("Downloading ^NSEBANK daily: %s to %s", start, end)
    df = _fetch_yfinance(start, end)

    if df.empty:
        logger.warning("yfinance returned empty dataframe for %s to %s", start, end)
        return df

    df = _clean(df)
    append_raw(df, INSTRUMENT, TIMEFRAME)
    logger.info("Saved %d rows to raw store", len(df))
    return df


def download_banknifty_intraday_recent(timeframe: str = "5m") -> pd.DataFrame:
    """
    Download recent intraday data (max 60 days for 5m from yfinance).
    Used only for pipeline testing until Shoonya account is ready.
    NOT suitable for research — history is too short.
    """
    logger.warning(
        "Intraday yfinance data limited to 60 days. "
        "Use Shoonya API for research-grade 5-min history."
    )
    ticker = yf.Ticker(BANKNIFTY_TICKER)
    raw = ticker.history(period="60d", interval=timeframe, auto_adjust=True)
    if raw.empty:
        return raw
    df = _clean(raw)
    logger.info("Downloaded %d intraday bars (last 60 days only)", len(df))
    return df


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fetch_yfinance(start: str, end: str, retries: int = 3) -> pd.DataFrame:
    """Download with simple retry logic."""
    for attempt in range(1, retries + 1):
        try:
            ticker = yf.Ticker(BANKNIFTY_TICKER)
            # end date is exclusive in yfinance — add 1 day
            end_exclusive = (
                pd.Timestamp(end) + pd.Timedelta(days=1)
            ).strftime("%Y-%m-%d")
            df = ticker.history(
                start=start,
                end=end_exclusive,
                interval="1d",
                auto_adjust=True,
                actions=False,
            )
            return df
        except Exception as exc:
            logger.warning("yfinance attempt %d/%d failed: %s", attempt, retries, exc)
            if attempt < retries:
                time.sleep(2 ** attempt)
    logger.error("All %d yfinance attempts failed", retries)
    return pd.DataFrame()


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """Standardise column names, timezone, and remove bad rows."""
    # yfinance columns: Open, High, Low, Close, Volume (capitalised)
    df = df.rename(columns={
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    })
    cols = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
    df = df[cols].copy()

    # Ensure Asia/Kolkata timezone
    if df.index.tz is None:
        df.index = df.index.tz_localize("Asia/Kolkata")
    else:
        df.index = df.index.tz_convert("Asia/Kolkata")
    df.index.name = "timestamp"

    # Drop rows where close is NaN or zero
    before = len(df)
    df = df[df["close"].notna() & (df["close"] > 0)]
    dropped = before - len(df)
    if dropped:
        logger.warning("Dropped %d rows with null/zero close", dropped)

    # Drop duplicates
    df = df[~df.index.duplicated(keep="last")]
    df.sort_index(inplace=True)

    return df


def _load_existing_last_date() -> date | None:
    from src.data.storage import read_raw
    try:
        df = read_raw(INSTRUMENT, TIMEFRAME)
        if df.empty:
            return None
        return df.index.max().date()
    except Exception:
        return None
