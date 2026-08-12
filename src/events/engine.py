"""
EventEngine — touch detection and bounce/break classification.

Implements EXP-001 pre-registered parameters exactly.
Parameters are constants here — do not change after experiment is registered.

EXP-001 PRIMARY PARAMETERS (FROZEN):
    Touch:    bar close enters zone [zone_low, zone_high]
    Price:    Bank Nifty index close (not wick, not futures)
    Bounce:   MFE >= 1.0 × ATR(14) before MAE >= 0.5 × ATR(14), within 6 bars
    Break:    close beyond zone edge + 0.25 × ATR(14), holds for 2 bars
    Horizon:  6 bars
    Re-entry: new touch requires 1.0 × ATR distance from midpoint, then return
    Overlap:  not allowed

Causal invariant: the scan forward from t_touch uses bars t_touch+1 onward.
No data from the OHLCV series beyond what is available in live trading.

For daily bars:
    - MFE/MAE measured on close prices (not intrabar high/low)
    - 6 bars = 6 trading days
    - Break confirmation = 2 consecutive closes beyond threshold
"""

from __future__ import annotations

import logging
from enum import Enum

import numpy as np
import pandas as pd

from src.zones.atr import compute_atr

logger = logging.getLogger(__name__)

# ── EXP-001 frozen parameters ────────────────────────────────────────────────
ATR_PERIOD        = 14
BOUNCE_MFE_MULT   = 1.0   # MFE threshold = BOUNCE_MFE_MULT × ATR
BOUNCE_MAE_MULT   = 0.5   # MAE threshold = BOUNCE_MAE_MULT × ATR
HORIZON_BARS      = 6     # bars to evaluate after touch
BREAK_BUFFER_MULT = 0.25  # close beyond zone edge by BREAK_BUFFER_MULT × ATR
BREAK_CONFIRM_BARS= 2     # consecutive closes beyond threshold to confirm break
REENTRY_MULT      = 1.0   # must move REENTRY_MULT × ATR from midpoint before new touch
# ─────────────────────────────────────────────────────────────────────────────


class TouchDirection(Enum):
    SUPPORT    = "support"     # price at lower part of zone, expect bounce UP
    RESISTANCE = "resistance"  # price at upper part of zone, expect bounce DOWN


class EventResult(Enum):
    BOUNCE       = "bounce"
    BREAK        = "break"
    INCONCLUSIVE = "inconclusive"


def build_event_log(
    df: pd.DataFrame,
    zone_frame: pd.DataFrame,
    atr_period: int = ATR_PERIOD,
    bounce_mfe_mult: float = BOUNCE_MFE_MULT,
    bounce_mae_mult: float = BOUNCE_MAE_MULT,
    horizon_bars: int = HORIZON_BARS,
    break_buffer_mult: float = BREAK_BUFFER_MULT,
    break_confirm_bars: int = BREAK_CONFIRM_BARS,
    reentry_mult: float = REENTRY_MULT,
) -> pd.DataFrame:
    """
    Scan all bars in df, detect zone touches, and classify each as
    Bounce / Break / Inconclusive using EXP-001 parameters.

    Parameters
    ----------
    df         : OHLCV DataFrame with DatetimeIndex (causal ATR already applied)
    zone_frame : output of ZoneDetector.build_zone_frame()

    Returns
    -------
    DataFrame with one row per touch event. Columns:
        touch_timestamp, zone_type, zone_level, zone_low, zone_high,
        zone_score, touch_price, atr_at_touch, direction,
        bounce_threshold, mae_threshold, break_threshold,
        result, mfe, mae, mfe_bar, mae_bar, exit_bar,
        forward_return_6bar, day_of_week, touch_count_on_zone
    """
    atr = compute_atr(df, period=atr_period, shift=True)

    # Index lookup for fast bar position access
    bar_positions = {ts: i for i, ts in enumerate(df.index)}
    close = df["close"].values
    timestamps = df.index

    # Per-zone touch state: zone_key -> last_exit_bar_pos and last_exit_close
    # zone_key = (zone_level_rounded, zone_type)
    zone_touch_counts: dict[tuple, int]  = {}
    zone_last_exit: dict[tuple, dict]    = {}

    events = []

    # Pre-index zone_frame by timestamp for fast lookup
    zf_by_ts = zone_frame.groupby("timestamp")

    for i, ts in enumerate(timestamps):
        # Need at least HORIZON_BARS bars ahead to evaluate outcome
        if i + horizon_bars >= len(timestamps):
            break

        atr_val = atr.iloc[i]
        if pd.isna(atr_val) or atr_val <= 0:
            continue

        close_t = close[i]

        # Get active zones at this bar
        if ts not in zf_by_ts.groups:
            continue

        active_zones = zf_by_ts.get_group(ts)

        for _, zone_row in active_zones.iterrows():
            zone_key = (_round_level(zone_row["level"]), zone_row["zone_type"])
            zl  = zone_row["zone_low"]
            zh  = zone_row["zone_high"]
            mid = zone_row["level"]

            # Check if price is inside zone
            if not (zl <= close_t <= zh):
                # Update re-entry tracking: price has moved away from zone
                if zone_key in zone_last_exit:
                    state = zone_last_exit[zone_key]
                    dist = abs(close_t - mid)
                    if dist >= reentry_mult * atr_val:
                        state["moved_away"] = True
                continue

            # Price IS inside zone. Check re-entry rule.
            if zone_key in zone_last_exit:
                state = zone_last_exit[zone_key]
                if not state.get("moved_away", False):
                    # Still considered same touch (price hasn't left by 1 ATR)
                    continue
                # Re-entry valid: price moved away and returned

            # New touch event
            touch_count = zone_touch_counts.get(zone_key, 0) + 1
            zone_touch_counts[zone_key] = touch_count

            # Determine direction from position in zone
            direction = (
                TouchDirection.SUPPORT
                if close_t <= mid
                else TouchDirection.RESISTANCE
            )

            # Thresholds
            bounce_thresh = bounce_mfe_mult * atr_val
            mae_thresh    = bounce_mae_mult  * atr_val
            break_thresh  = break_buffer_mult * atr_val

            # Scan forward HORIZON_BARS bars to classify outcome
            result, mfe, mae, mfe_bar, mae_bar, exit_bar = _classify_outcome(
                close=close,
                i_touch=i,
                close_t=close_t,
                direction=direction,
                zone_low=zl,
                zone_high=zh,
                atr_val=atr_val,
                bounce_thresh=bounce_thresh,
                mae_thresh=mae_thresh,
                break_thresh=break_thresh,
                break_confirm_bars=break_confirm_bars,
                horizon_bars=horizon_bars,
            )

            # Forward return over horizon (for distribution analysis)
            fwd_close = close[min(i + horizon_bars, len(close) - 1)]
            forward_return = (fwd_close - close_t) / close_t

            events.append({
                "touch_timestamp":    ts,
                "zone_type":          zone_row["zone_type"],
                "zone_level":         zone_row["level"],
                "zone_low":           zl,
                "zone_high":          zh,
                "zone_score":         zone_row["score"],
                "zone_formed_at":     zone_row["formed_at"],
                "touch_price":        float(close_t),
                "atr_at_touch":       float(atr_val),
                "direction":          direction.value,
                "bounce_threshold":   float(bounce_thresh),
                "mae_threshold":      float(mae_thresh),
                "break_threshold":    float(break_thresh),
                "result":             result.value,
                "mfe":                float(mfe),
                "mae":                float(mae),
                "mfe_bar_offset":     mfe_bar,
                "mae_bar_offset":     mae_bar,
                "exit_bar_offset":    exit_bar,
                "forward_return_6bar": float(forward_return),
                "day_of_week":        ts.day_of_week,      # 0=Mon, 4=Fri
                "touch_count_on_zone": touch_count,
                "bar_position":       i,
            })

            # Mark this zone as "in touch" — prevent re-entry until moved away
            zone_last_exit[zone_key] = {"bar": i, "moved_away": False}

    if not events:
        logger.warning("No touch events detected.")
        return pd.DataFrame()

    event_log = pd.DataFrame(events)
    event_log.sort_values("touch_timestamp", inplace=True)
    event_log.reset_index(drop=True, inplace=True)

    logger.info(
        "Event detection complete: %d touch events  "
        "bounce=%d (%.1f%%)  break=%d (%.1f%%)  inconclusive=%d (%.1f%%)",
        len(event_log),
        (event_log["result"] == "bounce").sum(),
        (event_log["result"] == "bounce").mean() * 100,
        (event_log["result"] == "break").sum(),
        (event_log["result"] == "break").mean() * 100,
        (event_log["result"] == "inconclusive").sum(),
        (event_log["result"] == "inconclusive").mean() * 100,
    )
    return event_log


# ── Outcome classification ────────────────────────────────────────────────────

def _classify_outcome(
    close: np.ndarray,
    i_touch: int,
    close_t: float,
    direction: TouchDirection,
    zone_low: float,
    zone_high: float,
    atr_val: float,
    bounce_thresh: float,
    mae_thresh: float,
    break_thresh: float,
    break_confirm_bars: int,
    horizon_bars: int,
) -> tuple[EventResult, float, float, int, int, int]:
    """
    Scan forward from i_touch over horizon_bars bars.
    Returns (result, mfe, mae, mfe_bar_offset, mae_bar_offset, exit_bar_offset).

    For SUPPORT touch (expect price to go UP):
        Bounce: close rises >= bounce_thresh above close_t BEFORE falling >= mae_thresh
        Break:  close falls to <= zone_low - break_thresh for break_confirm_bars consecutive

    For RESISTANCE touch (expect price to go DOWN):
        Bounce: close falls >= bounce_thresh below close_t BEFORE rising >= mae_thresh
        Break:  close rises to >= zone_high + break_thresh for break_confirm_bars consecutive
    """
    n = len(close)
    is_support = (direction == TouchDirection.SUPPORT)

    mfe = 0.0         # max favorable excursion (positive = good)
    mae = 0.0         # max adverse excursion (positive = bad, i.e. abs value)
    mfe_bar = -1
    mae_bar = -1
    exit_bar = horizon_bars

    bounce_hit = False
    bounce_bar = -1
    break_consecutive = 0
    break_start_bar = -1

    for offset in range(1, horizon_bars + 1):
        j = i_touch + offset
        if j >= n:
            exit_bar = offset - 1
            break

        c = close[j]

        if is_support:
            favorable = c - close_t    # positive = price went up (good for long)
            adverse   = close_t - c    # positive = price went down (bad for long)
            break_condition = c <= zone_low - break_thresh
        else:
            favorable = close_t - c    # positive = price went down (good for short)
            adverse   = c - close_t    # positive = price went up (bad for short)
            break_condition = c >= zone_high + break_thresh

        # Track MFE
        if favorable > mfe:
            mfe = favorable
            mfe_bar = offset

        # Track MAE
        if adverse > mae:
            mae = adverse
            mae_bar = offset

        # Check bounce condition (MFE threshold reached first)
        if not bounce_hit and mfe >= bounce_thresh and mae < mae_thresh:
            bounce_hit = True
            bounce_bar = offset

        # Check break condition
        if break_condition:
            break_consecutive += 1
            if break_consecutive == 1:
                break_start_bar = offset
            if break_consecutive >= break_confirm_bars:
                # Break confirmed — but only if bounce not already established
                if not bounce_hit:
                    return EventResult.BREAK, mfe, mae, mfe_bar, mae_bar, offset
                else:
                    # Bounce was already confirmed before break — count as bounce
                    return EventResult.BOUNCE, mfe, mae, mfe_bar, mae_bar, bounce_bar
        else:
            break_consecutive = 0
            break_start_bar = -1

        # Check MAE threshold (adverse exceeds limit — count as break/failed bounce)
        if mae >= mae_thresh and not bounce_hit:
            return EventResult.BREAK, mfe, mae, mfe_bar, mae_bar, offset

    # Horizon elapsed without decisive outcome
    if bounce_hit:
        return EventResult.BOUNCE, mfe, mae, mfe_bar, mae_bar, bounce_bar

    return EventResult.INCONCLUSIVE, mfe, mae, mfe_bar, mae_bar, exit_bar


def _round_level(level: float, decimals: int = 1) -> float:
    """Round zone level for use as dict key (avoids float precision issues)."""
    return round(level, decimals)
