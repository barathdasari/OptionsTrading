"""
Matched control generation for EXP-001.

For each zone-touch event, sample one matched control observation from
non-zone moments in the same dataset.

Matching variables (pre-event confounders only — see EXP-001 spec):
    - time_of_day bucket      (daily bars: not applicable — skipped)
    - prior_vol_quintile      — realized volatility quintile over prior 14 bars
    - prior_trend_tertile     — ADX tertile (low/medium/high) over prior 14 bars
    - prior_return_quintile   — abs(return) quintile over prior 5 bars
    - prior_range_tertile     — bar range tertile over prior 5 bars
    - gap_direction           — gap-up / gap-down / flat at open vs prior close
    - day_type                — normal / expiry (from contract metadata if available)
    - expiry_distance_bucket  — 1-3d / 4-7d / 8-14d / 15+d (if expiry data available)

IMPORTANT: Do NOT match on:
    - current OI, IV, PCR (not in EXP-001 data, and potentially endogenous)
    - current distance to swing high/low (endogenous to zone algorithm)
    - volume at touch moment

One control per event. Sampling is stratified: controls drawn from same
stratum as the event, sampled uniformly without replacement.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from src.zones.atr import compute_atr

logger = logging.getLogger(__name__)

ATR_PERIOD = 14
PRIOR_RETURN_WINDOW = 5
PRIOR_RANGE_WINDOW  = 5
GAP_FLAT_THRESHOLD  = 0.001   # <0.1% gap = flat


def build_control_log(
    df: pd.DataFrame,
    event_log: pd.DataFrame,
    zone_frame: pd.DataFrame,
    random_seed: int = 42,
) -> pd.DataFrame:
    """
    Generate one matched control for each event in event_log.

    Returns a DataFrame with same schema as event_log plus column
    'matched_event_idx' linking back to the event.

    Only non-zone bars are eligible as controls (bars where price is NOT
    inside any active zone). This is critical — using zone bars as controls
    would bias the comparison.
    """
    rng = np.random.default_rng(random_seed)

    # Feature matrix for all bars
    features = _compute_features(df)

    # Identify non-zone bars: bars where price close is NOT in any active zone
    zone_bar_set = _get_zone_bar_set(df, zone_frame)
    non_zone_mask = ~features.index.isin(zone_bar_set)
    control_pool = features[non_zone_mask].copy()

    logger.info(
        "Control pool: %d non-zone bars (%.1f%% of total)",
        len(control_pool),
        len(control_pool) / len(features) * 100,
    )

    # Assign stratum to each bar in pool
    control_pool["stratum"] = _assign_stratum(control_pool)

    # Also assign stratum to events
    event_features = features.loc[
        features.index.isin(event_log["touch_timestamp"])
    ].copy()
    event_features["stratum"] = _assign_stratum(event_features)

    # For each event, sample a control from the same stratum
    controls = []
    unmatched = 0

    # Build stratum -> list of eligible control indices
    stratum_pool: dict[str, list] = {}
    for stratum, grp in control_pool.groupby("stratum"):
        stratum_pool[stratum] = list(grp.index)

    used_control_bars: set = set()

    for _, event_row in event_log.iterrows():
        ts = event_row["touch_timestamp"]
        stratum = event_features.loc[ts, "stratum"] if ts in event_features.index else None

        control_ts = _sample_control(
            stratum=stratum,
            stratum_pool=stratum_pool,
            used=used_control_bars,
            rng=rng,
            fallback_pool=list(control_pool.index),
        )

        if control_ts is None:
            unmatched += 1
            continue

        used_control_bars.add(control_ts)
        ctrl_features = control_pool.loc[control_ts]

        # Compute the same forward metrics for the control bar
        ctrl_result = _compute_control_outcome(
            df=df,
            ts=control_ts,
            direction=event_row["direction"],
            atr_val=ctrl_features.get("atr", event_row["atr_at_touch"]),
            bounce_thresh=event_row["bounce_threshold"],
            mae_thresh=event_row["mae_threshold"],
            break_thresh=event_row["break_threshold"],
        )

        ctrl_record = {
            "control_timestamp":    control_ts,
            "matched_event_idx":    event_row.name,
            "touch_timestamp":      event_row["touch_timestamp"],
            "stratum":              stratum,
            "direction":            event_row["direction"],
            "touch_price":          float(df.loc[control_ts, "close"]),
            "atr_at_touch":         float(ctrl_features.get("atr", np.nan)),
            "bounce_threshold":     event_row["bounce_threshold"],
            "mae_threshold":        event_row["mae_threshold"],
            "break_threshold":      event_row["break_threshold"],
            "forward_return_6bar":  ctrl_result["forward_return"],
            "result":               ctrl_result["result"],
            "mfe":                  ctrl_result["mfe"],
            "mae":                  ctrl_result["mae"],
        }
        controls.append(ctrl_record)

    if unmatched > 0:
        logger.warning("%d events could not be matched to a control.", unmatched)

    logger.info("Generated %d matched controls for %d events.",
                len(controls), len(event_log))

    if not controls:
        return pd.DataFrame()

    return pd.DataFrame(controls)


# ── Feature computation ───────────────────────────────────────────────────────

def _compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute matching features for all bars. All causal (shift=1)."""
    feat = pd.DataFrame(index=df.index)

    atr = compute_atr(df, period=ATR_PERIOD, shift=True)
    feat["atr"] = atr

    close = df["close"]
    high  = df["high"]
    low   = df["low"]
    open_ = df["open"] if "open" in df.columns else close

    # Prior realized volatility (std of returns over prior N bars)
    returns = close.pct_change()
    prior_vol = returns.rolling(ATR_PERIOD).std().shift(1)
    feat["prior_vol"] = prior_vol

    # Prior return magnitude
    prior_return = returns.rolling(PRIOR_RETURN_WINDOW).apply(
        lambda x: abs(x).mean(), raw=True
    ).shift(1)
    feat["prior_return_abs"] = prior_return

    # Prior bar range
    prior_range = (high - low).rolling(PRIOR_RANGE_WINDOW).mean().shift(1)
    feat["prior_range"] = prior_range

    # Gap direction: open vs prior close
    gap_pct = (open_ / close.shift(1) - 1).fillna(0)
    feat["gap_direction"] = np.where(
        gap_pct > GAP_FLAT_THRESHOLD, "gap_up",
        np.where(gap_pct < -GAP_FLAT_THRESHOLD, "gap_down", "flat")
    )

    # ADX-like trend strength: abs(close - close[N bars ago]) / (N × ATR)
    trend_strength = (
        (close - close.shift(ATR_PERIOD)).abs()
        / (ATR_PERIOD * atr)
    ).shift(1)
    feat["trend_strength"] = trend_strength

    feat["day_of_week"] = df.index.day_of_week

    return feat.dropna(subset=["prior_vol", "prior_return_abs"])


def _assign_stratum(features: pd.DataFrame) -> pd.Series:
    """
    Assign a stratum label to each bar based on matching variables.
    Stratum = string concatenation of bin labels.
    """
    labels = pd.Series("", index=features.index)

    for col, n_bins in [("prior_vol", 5), ("prior_return_abs", 5),
                        ("prior_range", 3), ("trend_strength", 3)]:
        if col not in features.columns:
            continue
        series = features[col].copy()
        # Replace inf with NaN, then fill with median
        series = series.replace([np.inf, -np.inf], np.nan)
        series = series.fillna(series.median())
        try:
            binned = pd.qcut(series, n_bins, labels=False, duplicates="drop")
        except Exception:
            binned = pd.cut(series, n_bins, labels=False)
        labels = labels + col[:4] + binned.fillna(0).astype(int).astype(str) + "_"

    if "gap_direction" in features.columns:
        labels = labels + features["gap_direction"].fillna("flat") + "_"

    if "day_of_week" in features.columns:
        labels = labels + "dow" + features["day_of_week"].astype(str)

    return labels


def _get_zone_bar_set(df: pd.DataFrame, zone_frame: pd.DataFrame) -> set:
    """
    Return set of timestamps where close price is inside at least one active zone.
    These bars are ineligible as controls.
    """
    zone_bar_set = set()
    close = df["close"]

    for ts, grp in zone_frame.groupby("timestamp"):
        if ts not in close.index:
            continue
        c = close[ts]
        for _, row in grp.iterrows():
            if row["zone_low"] <= c <= row["zone_high"]:
                zone_bar_set.add(ts)
                break

    return zone_bar_set


def _sample_control(
    stratum: str | None,
    stratum_pool: dict[str, list],
    used: set,
    rng: np.random.Generator,
    fallback_pool: list,
) -> pd.Timestamp | None:
    """Sample a control from the stratum pool. Falls back to full pool."""
    candidates = []
    if stratum and stratum in stratum_pool:
        candidates = [ts for ts in stratum_pool[stratum] if ts not in used]

    if not candidates:
        # Fallback: any unused control bar
        candidates = [ts for ts in fallback_pool if ts not in used]

    if not candidates:
        return None

    return rng.choice(candidates)


def _compute_control_outcome(
    df: pd.DataFrame,
    ts: pd.Timestamp,
    direction: str,
    atr_val: float,
    bounce_thresh: float,
    mae_thresh: float,
    break_thresh: float,
    horizon_bars: int = 6,
) -> dict:
    """Compute forward returns and outcome for a control bar using same thresholds."""
    from src.events.engine import _classify_outcome, TouchDirection, EventResult

    close = df["close"].values
    bar_positions = {t: i for i, t in enumerate(df.index)}

    i = bar_positions.get(ts)
    if i is None or i + horizon_bars >= len(close):
        return {"result": "inconclusive", "mfe": 0.0, "mae": 0.0, "forward_return": 0.0}

    td = TouchDirection.SUPPORT if direction == "support" else TouchDirection.RESISTANCE
    close_t = close[i]

    # Use dummy zone bounds (control has no zone — use ±large buffer)
    result, mfe, mae, _, _, _ = _classify_outcome(
        close=close,
        i_touch=i,
        close_t=close_t,
        direction=td,
        zone_low=close_t - 999999,
        zone_high=close_t + 999999,
        atr_val=atr_val if not np.isnan(atr_val) else 1.0,
        bounce_thresh=bounce_thresh,
        mae_thresh=mae_thresh,
        break_thresh=break_thresh,
        break_confirm_bars=2,
        horizon_bars=horizon_bars,
    )

    fwd_close = close[min(i + horizon_bars, len(close) - 1)]
    forward_return = (fwd_close - close_t) / close_t

    return {
        "result": result.value,
        "mfe": float(mfe),
        "mae": float(mae),
        "forward_return": float(forward_return),
    }
