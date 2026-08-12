"""
Data quality validation for raw OHLCV data.

Checks performed:
  1. Schema — required columns present, correct dtypes
  2. Date coverage — no missing trading days vs NSE calendar
  3. OHLC integrity — high >= low, high >= open/close, low <= open/close
  4. Outliers — price moves > N sigma flagged
  5. Volume — zero/negative volume flagged
  6. Stale data — consecutive identical closes
  7. Summary report

Call validate() to get a structured ValidationReport.
Do not trust data for research until all CRITICAL checks pass.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.data.nse_calendar import find_gaps, get_trading_days

logger = logging.getLogger(__name__)

# Thresholds
OUTLIER_SIGMA = 5.0          # flag daily returns > N sigma
MAX_STALE_CONSECUTIVE = 3    # flag if close unchanged for this many days
MIN_ROWS_REQUIRED = 500      # minimum rows to consider dataset usable


@dataclass
class ValidationIssue:
    severity: str        # 'CRITICAL' | 'WARNING' | 'INFO'
    check: str
    message: str
    affected_rows: int = 0
    sample: list = field(default_factory=list)


@dataclass
class ValidationReport:
    instrument: str
    timeframe: str
    total_rows: int
    date_range: tuple[str, str]
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not any(i.severity == "CRITICAL" for i in self.issues)

    @property
    def critical_issues(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "CRITICAL"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "WARNING"]

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        lines = [
            f"=== Validation Report: {self.instrument} {self.timeframe} ===",
            f"Status      : {status}",
            f"Rows        : {self.total_rows}",
            f"Date range  : {self.date_range[0]} to {self.date_range[1]}",
            f"Critical    : {len(self.critical_issues)}",
            f"Warnings    : {len(self.warnings)}",
            "",
        ]
        for issue in self.issues:
            lines.append(f"[{issue.severity:8s}] {issue.check}: {issue.message}")
            if issue.sample:
                lines.append(f"           Sample: {issue.sample[:5]}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate(df: pd.DataFrame, instrument: str, timeframe: str = "1D",
             start: str = None, end: str = None) -> ValidationReport:
    """
    Run all data quality checks on df.

    Parameters
    ----------
    df         : raw OHLCV DataFrame with DatetimeIndex
    instrument : e.g. 'BANKNIFTY'
    timeframe  : '1D' or '5min'
    start/end  : date range for gap-checking (defaults to df range)
    """
    if df.empty:
        report = ValidationReport(
            instrument=instrument,
            timeframe=timeframe,
            total_rows=0,
            date_range=("N/A", "N/A"),
        )
        report.issues.append(ValidationIssue(
            severity="CRITICAL", check="empty_dataframe",
            message="DataFrame is empty.",
        ))
        return report

    date_start = start or df.index.min().strftime("%Y-%m-%d")
    date_end = end or df.index.max().strftime("%Y-%m-%d")

    report = ValidationReport(
        instrument=instrument,
        timeframe=timeframe,
        total_rows=len(df),
        date_range=(date_start, date_end),
    )

    _check_minimum_rows(df, report)
    _check_schema(df, report)
    _check_ohlc_integrity(df, report)
    _check_volume(df, report)
    _check_gaps(df, report, date_start, date_end, timeframe)
    _check_outliers(df, report)
    _check_stale_prices(df, report)

    return report


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def _check_minimum_rows(df: pd.DataFrame, report: ValidationReport) -> None:
    if len(df) < MIN_ROWS_REQUIRED:
        report.issues.append(ValidationIssue(
            severity="CRITICAL",
            check="minimum_rows",
            message=(
                f"Only {len(df)} rows. Need >= {MIN_ROWS_REQUIRED} "
                "for reliable research. Data history too short."
            ),
            affected_rows=len(df),
        ))
    else:
        report.issues.append(ValidationIssue(
            severity="INFO",
            check="minimum_rows",
            message=f"{len(df)} rows — sufficient.",
        ))


def _check_schema(df: pd.DataFrame, report: ValidationReport) -> None:
    required = ["open", "high", "low", "close", "volume"]
    missing_cols = [c for c in required if c not in df.columns]
    if missing_cols:
        report.issues.append(ValidationIssue(
            severity="CRITICAL",
            check="schema",
            message=f"Missing required columns: {missing_cols}",
        ))
        return

    null_counts = {c: int(df[c].isna().sum()) for c in required}
    total_nulls = sum(null_counts.values())
    if total_nulls > 0:
        report.issues.append(ValidationIssue(
            severity="CRITICAL",
            check="null_values",
            message=f"Null values found: {null_counts}",
            affected_rows=total_nulls,
        ))
    else:
        report.issues.append(ValidationIssue(
            severity="INFO",
            check="schema",
            message="Schema OK. No null values.",
        ))


def _check_ohlc_integrity(df: pd.DataFrame, report: ValidationReport) -> None:
    if not {"open", "high", "low", "close"}.issubset(df.columns):
        return

    violations = (
        (df["high"] < df["low"]) |
        (df["high"] < df["open"]) |
        (df["high"] < df["close"]) |
        (df["low"] > df["open"]) |
        (df["low"] > df["close"])
    )
    n = int(violations.sum())
    if n > 0:
        sample = df.index[violations].strftime("%Y-%m-%d").tolist()
        report.issues.append(ValidationIssue(
            severity="CRITICAL",
            check="ohlc_integrity",
            message=f"{n} bars violate OHLC rules (high < low or similar).",
            affected_rows=n,
            sample=sample,
        ))
    else:
        report.issues.append(ValidationIssue(
            severity="INFO",
            check="ohlc_integrity",
            message="OHLC integrity OK.",
        ))

    # Negative prices
    neg = (df[["open", "high", "low", "close"]] <= 0).any(axis=1)
    n_neg = int(neg.sum())
    if n_neg > 0:
        report.issues.append(ValidationIssue(
            severity="CRITICAL",
            check="negative_prices",
            message=f"{n_neg} bars with zero or negative prices.",
            affected_rows=n_neg,
            sample=df.index[neg].strftime("%Y-%m-%d").tolist(),
        ))


def _check_volume(df: pd.DataFrame, report: ValidationReport) -> None:
    if "volume" not in df.columns:
        return
    zero_vol = (df["volume"] <= 0)
    n = int(zero_vol.sum())
    pct = n / len(df) * 100
    if pct > 90:
        # Index instruments (e.g. Bank Nifty index via yfinance) report no volume.
        # This is expected — not a data error.
        report.issues.append(ValidationIssue(
            severity="INFO",
            check="volume",
            message=(
                f"{n} bars ({pct:.1f}%) have zero volume. "
                "Expected for index instruments (no traded volume). "
                "Volume data available from futures/options chain only."
            ),
            affected_rows=n,
        ))
    elif pct > 5:
        report.issues.append(ValidationIssue(
            severity="WARNING",
            check="volume",
            message=f"{n} bars ({pct:.1f}%) have zero/negative volume.",
            affected_rows=n,
            sample=df.index[zero_vol].strftime("%Y-%m-%d").tolist()[:5],
        ))
    else:
        report.issues.append(ValidationIssue(
            severity="INFO",
            check="volume",
            message=f"Volume OK. {n} zero-volume bars ({pct:.1f}%).",
        ))


def _check_gaps(df: pd.DataFrame, report: ValidationReport,
                start: str, end: str, timeframe: str) -> None:
    try:
        gaps = find_gaps(df, start, end, timeframe=timeframe)
    except Exception as exc:
        report.issues.append(ValidationIssue(
            severity="WARNING",
            check="gaps",
            message=f"Gap check failed (calendar error): {exc}",
        ))
        return

    n = len(gaps)
    total_expected = len(get_trading_days(start, end))
    gap_pct = n / max(total_expected, 1) * 100

    if n == 0:
        report.issues.append(ValidationIssue(
            severity="INFO",
            check="gaps",
            message="No missing trading days/bars.",
        ))
    elif gap_pct <= 1.0:
        # <= 1% missing: likely NSE special holidays not in calendar. Warning only.
        report.issues.append(ValidationIssue(
            severity="WARNING",
            check="gaps",
            message=(
                f"{n} missing bars ({gap_pct:.2f}% of expected). "
                "Likely NSE special holidays not in pandas-market-calendars. "
                "Acceptable for research."
            ),
            affected_rows=n,
            sample=gaps["expected_timestamp"].dt.strftime("%Y-%m-%d").tolist()[:10],
        ))
    else:
        report.issues.append(ValidationIssue(
            severity="CRITICAL",
            check="gaps",
            message=f"{n} missing bars ({gap_pct:.1f}%) — data has significant gaps.",
            affected_rows=n,
            sample=gaps["expected_timestamp"].dt.strftime("%Y-%m-%d").tolist()[:10],
        ))


def _check_outliers(df: pd.DataFrame, report: ValidationReport) -> None:
    if "close" not in df.columns or len(df) < 30:
        return
    returns = df["close"].pct_change().dropna()
    mu = returns.mean()
    sigma = returns.std()
    if sigma == 0:
        return
    z_scores = (returns - mu) / sigma
    outliers = z_scores.abs() > OUTLIER_SIGMA
    n = int(outliers.sum())
    if n > 0:
        sample_dates = returns.index[outliers].strftime("%Y-%m-%d").tolist()
        sample_vals = [round(float(returns[d]), 4) for d in returns.index[outliers]]
        report.issues.append(ValidationIssue(
            severity="WARNING",
            check="outliers",
            message=(
                f"{n} daily returns > {OUTLIER_SIGMA} sigma. "
                "Verify these are real events, not data errors."
            ),
            affected_rows=n,
            sample=list(zip(sample_dates, sample_vals)),
        ))
    else:
        report.issues.append(ValidationIssue(
            severity="INFO",
            check="outliers",
            message=f"No returns exceed {OUTLIER_SIGMA} sigma.",
        ))


def _check_stale_prices(df: pd.DataFrame, report: ValidationReport) -> None:
    if "close" not in df.columns:
        return
    consecutive_same = (df["close"] == df["close"].shift(1))
    # Find runs of consecutive identical closes
    runs = consecutive_same.astype(int)
    run_lengths = runs.groupby((runs != runs.shift()).cumsum()).sum()
    max_run = int(run_lengths.max()) if len(run_lengths) > 0 else 0

    if max_run >= MAX_STALE_CONSECUTIVE:
        report.issues.append(ValidationIssue(
            severity="WARNING",
            check="stale_prices",
            message=(
                f"Maximum consecutive identical close prices: {max_run} bars. "
                "May indicate stale/repeated data."
            ),
        ))
    else:
        report.issues.append(ValidationIssue(
            severity="INFO",
            check="stale_prices",
            message=f"No stale price runs >= {MAX_STALE_CONSECUTIVE} bars.",
        ))
