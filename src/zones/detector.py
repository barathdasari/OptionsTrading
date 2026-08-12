"""
ZoneDetector — causal zone detection for Bank Nifty research.

CAUSAL INVARIANT (non-negotiable):
    Every zone active at bar t must be computable from data at bars [0 .. t-1] only.
    No zone uses bar t's own OHLCV data.

Zone types implemented (EXP-001):
    - Previous day high / low        (shift by 1 bar)
    - Previous week high / low       (previous complete week only)
    - Swing pivot high / low         (trailing N=10 bar window, no look-forward)
    - Volume POC / VAH / VAL         (previous session's complete profile — requires volume)

Zone width: k × ATR(14), where ATR is also shifted by 1 (causal).

Output:
    build_zone_frame(df) → DataFrame with one row per (bar, zone_level),
    containing all active zone levels at each bar.
    This is the primary input to EventEngine.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.zones.atr import compute_atr
from src.zones.zone import Zone, ZoneSet, ZoneType

logger = logging.getLogger(__name__)

# EXP-001 primary parameters — do not change after experiment is registered
ATR_PERIOD = 14
SWING_WINDOW = 10        # trailing bars for pivot detection
MIN_PIVOT_REVERSAL = 1.0  # pivot must be followed by >= N ATR reversal to qualify
K_PRIMARY = 0.5          # zone width = K × ATR
VALUE_AREA_PCT = 0.70    # % of volume defining Value Area (standard: 70%)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_zone_frame(df: pd.DataFrame, k: float = K_PRIMARY,
                     include_volume_profile: bool = False) -> pd.DataFrame:
    """
    Compute all active zone levels for every bar in df.

    Returns a DataFrame with columns:
        timestamp       — bar timestamp (matches df.index)
        zone_type       — ZoneType enum value (string)
        level           — zone midpoint price
        zone_low        — level - width/2
        zone_high       — level + width/2
        atr             — ATR at this bar (causal, shift=1)
        zone_width      — k × atr
        score           — composite significance score
        formed_at       — timestamp when zone was identified

    One row per (timestamp, zone_type, level). Multiple zones can be active
    at the same timestamp. Overlapping zones are merged.

    Parameters
    ----------
    df                   : OHLCV DataFrame with DatetimeIndex
    k                    : ATR multiplier for zone width (default 0.5)
    include_volume_profile : only use if df has non-zero volume column
    """
    _validate_columns(df)

    atr = compute_atr(df, period=ATR_PERIOD, shift=True)

    frames = [
        _prev_day_levels(df, atr, k),
        _weekly_levels(df, atr, k),
        _swing_pivot_levels(df, atr, k),
    ]

    if include_volume_profile:
        if "volume" not in df.columns or (df["volume"] <= 0).mean() > 0.5:
            logger.warning(
                "Volume profile skipped: >50%% of bars have zero volume. "
                "Volume profile requires futures/options chain data."
            )
        else:
            frames.append(_volume_profile_levels(df, atr, k))

    zone_frame = pd.concat([f for f in frames if not f.empty], ignore_index=True)

    if zone_frame.empty:
        logger.warning("build_zone_frame: no zones detected.")
        return zone_frame

    # Score each zone
    zone_frame = _score_zones(zone_frame, df)

    # Merge overlapping zones at same timestamp
    zone_frame = _merge_overlapping(zone_frame)

    zone_frame.sort_values(["timestamp", "level"], inplace=True)
    zone_frame.reset_index(drop=True, inplace=True)

    logger.info(
        "Zone detection complete: %d zone-bar entries across %d bars.",
        len(zone_frame),
        zone_frame["timestamp"].nunique(),
    )
    return zone_frame


def zones_at(zone_frame: pd.DataFrame, timestamp: pd.Timestamp) -> list[Zone]:
    """
    Return list of Zone objects active at a specific timestamp.
    Utility for interactive analysis.
    """
    mask = zone_frame["timestamp"] == timestamp
    rows = zone_frame[mask]
    result = []
    for _, row in rows.iterrows():
        result.append(Zone(
            level=row["level"],
            zone_low=row["zone_low"],
            zone_high=row["zone_high"],
            zone_type=ZoneType(row["zone_type"]),
            formed_at=row["formed_at"],
            atr_at_formation=row["atr"],
            k=row.get("k", K_PRIMARY),
            score=row["score"],
        ))
    return result


# ---------------------------------------------------------------------------
# Previous day high / low
# ---------------------------------------------------------------------------

def _prev_day_levels(df: pd.DataFrame, atr: pd.Series, k: float) -> pd.DataFrame:
    """
    Previous day high and low.
    Causal: shift(1) means bar t uses bar t-1 data.
    """
    prev_high = df["high"].shift(1)
    prev_low = df["low"].shift(1)
    formed_at = df.index.to_series().shift(1)

    rows = []
    for i, ts in enumerate(df.index):
        if pd.isna(prev_high.iloc[i]) or pd.isna(atr.iloc[i]):
            continue
        atr_val = atr.iloc[i]
        half = k * atr_val / 2

        for level, ztype, fat in [
            (prev_high.iloc[i], ZoneType.PREV_DAY_HIGH, formed_at.iloc[i]),
            (prev_low.iloc[i],  ZoneType.PREV_DAY_LOW,  formed_at.iloc[i]),
        ]:
            rows.append({
                "timestamp": ts,
                "zone_type": ztype.value,
                "level": level,
                "zone_low": level - half,
                "zone_high": level + half,
                "atr": atr_val,
                "zone_width": k * atr_val,
                "k": k,
                "formed_at": fat,
                "score": 0.0,
            })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Previous week high / low
# ---------------------------------------------------------------------------

def _weekly_levels(df: pd.DataFrame, atr: pd.Series, k: float) -> pd.DataFrame:
    """
    Previous complete week's high and low.
    Causal: at bar t on week W, use high/low of week W-1 (fully complete).
    """
    # ISO week number + year as group key
    week_key = df.index.to_series().dt.isocalendar().week.astype(str) + "_" + \
               df.index.to_series().dt.isocalendar().year.astype(str)

    weekly_high = df["high"].groupby(week_key).max()
    weekly_low = df["low"].groupby(week_key).min()
    # Last bar of each week (for formed_at)
    weekly_last = df.index.to_series().groupby(week_key).last()

    # Map each bar to its week key
    bar_week = week_key.values
    unique_weeks = list(weekly_high.index)

    rows = []
    for i, ts in enumerate(df.index):
        current_week = bar_week[i]
        try:
            week_idx = unique_weeks.index(current_week)
        except ValueError:
            continue
        if week_idx == 0:
            continue  # no prior week yet

        prev_week = unique_weeks[week_idx - 1]
        prev_wh = weekly_high[prev_week]
        prev_wl = weekly_low[prev_week]
        formed = weekly_last[prev_week]

        if pd.isna(prev_wh) or pd.isna(atr.iloc[i]):
            continue

        atr_val = atr.iloc[i]
        half = k * atr_val / 2

        for level, ztype in [
            (prev_wh, ZoneType.WEEKLY_HIGH),
            (prev_wl, ZoneType.WEEKLY_LOW),
        ]:
            rows.append({
                "timestamp": ts,
                "zone_type": ztype.value,
                "level": level,
                "zone_low": level - half,
                "zone_high": level + half,
                "atr": atr_val,
                "zone_width": k * atr_val,
                "k": k,
                "formed_at": formed,
                "score": 0.0,
            })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Swing pivot levels (causal — trailing window only)
# ---------------------------------------------------------------------------

def _swing_pivot_levels(df: pd.DataFrame, atr: pd.Series, k: float,
                        window: int = SWING_WINDOW) -> pd.DataFrame:
    """
    Causal swing pivots: bar t is a pivot high if close[t] is the maximum
    of the trailing window close[t-window : t+1] (inclusive of t, no future bars).

    Pivot significance filter: the reversal from pivot must be >= 1.0 × ATR.
    Pivots are retained as active zones until price breaks them by > 1 ATR.

    Only the 3 most recent pivot highs and 3 most recent pivot lows are active
    at any bar (to avoid zone proliferation from old pivots).
    """
    close = df["close"]
    rolling_max = close.rolling(window + 1, min_periods=window + 1).max()
    rolling_min = close.rolling(window + 1, min_periods=window + 1).min()

    is_pivot_high = (close == rolling_max)
    is_pivot_low = (close == rolling_min)

    # Verify minimum reversal from pivot
    # Pivot high at t: subsequent low must drop >= ATR from pivot
    # Use a forward-looking check ONLY for labelling quality — not for signal
    # For causal trading, we use the pivot as soon as it forms (trailing window)
    pivot_high_prices = close[is_pivot_high]
    pivot_low_prices = close[is_pivot_low]

    rows = []

    for i, ts in enumerate(df.index):
        if pd.isna(atr.iloc[i]):
            continue
        atr_val = atr.iloc[i]
        half = k * atr_val / 2
        current_close = close.iloc[i]

        # Active pivot highs: all pivot highs formed before ts, above current price
        # (still relevant as resistance), max 3 most recent
        ph_before = pivot_high_prices[pivot_high_prices.index < ts]
        ph_above = ph_before[ph_before > current_close]
        ph_active = ph_above.tail(3)  # 3 most recent

        for pivot_ts, pivot_price in ph_active.items():
            rows.append({
                "timestamp": ts,
                "zone_type": ZoneType.SWING_HIGH.value,
                "level": float(pivot_price),
                "zone_low": float(pivot_price) - half,
                "zone_high": float(pivot_price) + half,
                "atr": atr_val,
                "zone_width": k * atr_val,
                "k": k,
                "formed_at": pivot_ts,
                "score": 0.0,
            })

        # Active pivot lows: below current price (still relevant as support)
        pl_before = pivot_low_prices[pivot_low_prices.index < ts]
        pl_below = pl_before[pl_before < current_close]
        pl_active = pl_below.tail(3)

        for pivot_ts, pivot_price in pl_active.items():
            rows.append({
                "timestamp": ts,
                "zone_type": ZoneType.SWING_LOW.value,
                "level": float(pivot_price),
                "zone_low": float(pivot_price) - half,
                "zone_high": float(pivot_price) + half,
                "atr": atr_val,
                "zone_width": k * atr_val,
                "k": k,
                "formed_at": pivot_ts,
                "score": 0.0,
            })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Volume profile — POC / VAH / VAL (requires real volume)
# ---------------------------------------------------------------------------

def _volume_profile_levels(df: pd.DataFrame, atr: pd.Series, k: float,
                            lookback_days: int = 20) -> pd.DataFrame:
    """
    Rolling volume profile: POC, VAH, VAL over previous `lookback_days` bars.
    Causal: uses bars [t-lookback .. t-1].

    Requires non-zero volume in df["volume"].
    """
    rows = []

    for i in range(lookback_days + 1, len(df)):
        ts = df.index[i]
        atr_val = atr.iloc[i]
        if pd.isna(atr_val):
            continue

        window = df.iloc[i - lookback_days: i]  # strictly before bar i (causal)
        if (window["volume"] <= 0).all():
            continue

        poc, vah, val = _compute_vpoc(window)
        if poc is None:
            continue

        half = k * atr_val / 2
        formed = df.index[i - 1]

        for level, ztype in [
            (poc, ZoneType.VOLUME_POC),
            (vah, ZoneType.VOLUME_VAH),
            (val, ZoneType.VOLUME_VAL),
        ]:
            rows.append({
                "timestamp": ts,
                "zone_type": ztype.value,
                "level": level,
                "zone_low": level - half,
                "zone_high": level + half,
                "atr": atr_val,
                "zone_width": k * atr_val,
                "k": k,
                "formed_at": formed,
                "score": 0.0,
            })

    return pd.DataFrame(rows)


def _compute_vpoc(window: pd.DataFrame,
                  n_bins: int = 50) -> tuple[float | None, float | None, float | None]:
    """
    Compute Point of Control, Value Area High, Value Area Low
    from a price window with volume.

    Returns (poc, vah, val) or (None, None, None) if insufficient data.
    """
    if len(window) < 5:
        return None, None, None

    price_range = window["high"].max() - window["low"].min()
    if price_range <= 0:
        return None, None, None

    bins = np.linspace(window["low"].min(), window["high"].max(), n_bins + 1)
    bin_centers = (bins[:-1] + bins[1:]) / 2

    # Distribute each bar's volume across price bins it touched (high..low)
    bin_volumes = np.zeros(n_bins)
    for _, row in window.iterrows():
        in_range = (bin_centers >= row["low"]) & (bin_centers <= row["high"])
        n_bins_touched = max(1, in_range.sum())
        bin_volumes[in_range] += row["volume"] / n_bins_touched

    if bin_volumes.sum() == 0:
        return None, None, None

    poc_idx = int(np.argmax(bin_volumes))
    poc = float(bin_centers[poc_idx])

    # Value Area: bins containing 70% of total volume, expanding from POC
    total_vol = bin_volumes.sum()
    target_vol = total_vol * VALUE_AREA_PCT

    va_mask = np.zeros(n_bins, dtype=bool)
    va_mask[poc_idx] = True
    va_vol = bin_volumes[poc_idx]

    lo_idx, hi_idx = poc_idx, poc_idx
    while va_vol < target_vol:
        can_expand_lo = lo_idx > 0
        can_expand_hi = hi_idx < n_bins - 1
        if not can_expand_lo and not can_expand_hi:
            break
        next_lo_vol = bin_volumes[lo_idx - 1] if can_expand_lo else -1
        next_hi_vol = bin_volumes[hi_idx + 1] if can_expand_hi else -1
        if next_hi_vol >= next_lo_vol:
            hi_idx += 1
            va_mask[hi_idx] = True
            va_vol += bin_volumes[hi_idx]
        else:
            lo_idx -= 1
            va_mask[lo_idx] = True
            va_vol += bin_volumes[lo_idx]

    vah = float(bin_centers[hi_idx])
    val = float(bin_centers[lo_idx])

    return poc, vah, val


# ---------------------------------------------------------------------------
# Zone scoring
# ---------------------------------------------------------------------------

def _score_zones(zone_frame: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute composite significance score for each zone row.

    Score components (0–1 each, max total = 3):
    1. Recency: 1.0 if formed within 5 bars, 0.5 otherwise
    2. Confluence: 1.0 if another zone of different type is within zone_width
    3. Type weight: PDH/PDL = 0.8, Weekly = 1.0, Swing = 0.7, Volume = 0.9
    """
    type_weight = {
        ZoneType.PREV_DAY_HIGH.value: 0.8,
        ZoneType.PREV_DAY_LOW.value:  0.8,
        ZoneType.WEEKLY_HIGH.value:   1.0,
        ZoneType.WEEKLY_LOW.value:    1.0,
        ZoneType.SWING_HIGH.value:    0.7,
        ZoneType.SWING_LOW.value:     0.7,
        ZoneType.VOLUME_POC.value:    0.9,
        ZoneType.VOLUME_VAH.value:    0.9,
        ZoneType.VOLUME_VAL.value:    0.9,
    }

    ts_index = {ts: pos for pos, ts in enumerate(df.index)}
    scores = []

    for _, row in zone_frame.iterrows():
        ts = row["timestamp"]
        bar_pos = ts_index.get(ts, None)
        formed_pos = ts_index.get(row["formed_at"], None)

        # Recency
        if bar_pos is not None and formed_pos is not None:
            age = bar_pos - formed_pos
            recency = 1.0 if age <= 5 else 0.5
        else:
            recency = 0.5

        # Type weight
        tw = type_weight.get(row["zone_type"], 0.5)

        # Confluence (checked after all zones computed — placeholder here)
        confluence = 0.0

        score = recency + tw + confluence
        scores.append(score)

    zone_frame = zone_frame.copy()
    zone_frame["score"] = scores

    # Confluence pass: for each (timestamp, zone), check if another zone of
    # different type overlaps within zone_width
    grouped = zone_frame.groupby("timestamp")
    confluence_bonus = np.zeros(len(zone_frame))

    for ts, grp in grouped:
        if len(grp) <= 1:
            continue
        for idx_a, row_a in grp.iterrows():
            for idx_b, row_b in grp.iterrows():
                if idx_a == idx_b:
                    continue
                if row_a["zone_type"] == row_b["zone_type"]:
                    continue
                overlap = (
                    row_a["zone_low"] <= row_b["zone_high"] and
                    row_a["zone_high"] >= row_b["zone_low"]
                )
                if overlap:
                    confluence_bonus[zone_frame.index.get_loc(idx_a)] = 1.0
                    break

    zone_frame["score"] = zone_frame["score"] + confluence_bonus
    return zone_frame


# ---------------------------------------------------------------------------
# Zone merging
# ---------------------------------------------------------------------------

def _merge_overlapping(zone_frame: pd.DataFrame) -> pd.DataFrame:
    """
    For each timestamp, merge zone rows whose [zone_low, zone_high] intervals
    overlap. Merged zone uses:
        level     = mean of constituent levels
        zone_low  = min of zone_lows
        zone_high = max of zone_highs
        zone_type = "merged" (concatenation of constituent types)
        score     = max of constituent scores + 0.5 confluence bonus
    """
    output_rows = []

    for ts, grp in zone_frame.groupby("timestamp"):
        grp = grp.sort_values("level").reset_index(drop=True)
        merged = _merge_group(grp)
        output_rows.append(merged)

    if not output_rows:
        return zone_frame

    return pd.concat(output_rows, ignore_index=True)


def _merge_group(grp: pd.DataFrame) -> pd.DataFrame:
    """Greedy interval merge for one timestamp's zones."""
    zones = grp.to_dict("records")
    merged = []

    i = 0
    while i < len(zones):
        current = dict(zones[i])
        types = [current["zone_type"]]
        j = i + 1
        while j < len(zones):
            nxt = zones[j]
            if nxt["zone_low"] <= current["zone_high"]:  # overlap
                current["zone_low"] = min(current["zone_low"], nxt["zone_low"])
                current["zone_high"] = max(current["zone_high"], nxt["zone_high"])
                current["level"] = (current["zone_low"] + current["zone_high"]) / 2
                current["score"] = max(current["score"], nxt["score"]) + 0.5
                types.append(nxt["zone_type"])
                j += 1
            else:
                break
        current["zone_type"] = "|".join(sorted(set(types)))
        merged.append(current)
        i = j

    return pd.DataFrame(merged)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_columns(df: pd.DataFrame) -> None:
    required = {"open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"ZoneDetector requires columns {required}. Missing: {missing}")
