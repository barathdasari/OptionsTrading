"""
Script: Run event detection (touch / bounce / break) and generate matched controls.
Saves results + 6 charts to reports/EXP-001/.

Usage
-----
    python scripts/04_detect_events.py
    python scripts/04_detect_events.py --start 2015-01-01
    python scripts/04_detect_events.py --no-controls   # skip control generation

Charts produced (reports/EXP-001/charts/):
    01_price_with_zones.png       — price series with zone bands
    02_event_outcomes_bar.png     — bounce/break/inconclusive counts
    03_bounce_rate_by_type.png    — bounce rate per zone type
    04_touch_count_decay.png      — bounce rate by touch count (1st, 2nd, 3rd+)
    05_mfe_mae_distributions.png  — MFE vs MAE histograms for bounces
    06_zones_vs_controls.png      — bounce rate: zones vs matched controls

Run from project root:
    cd "c:/Users/DASABH3/Desktop/Bharath/Personal/Projects/F&O_Trading"
    python scripts/04_detect_events.py
"""

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib
matplotlib.use("Agg")  # non-interactive backend for saving files
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

from src.data.storage import read_raw, read_processed, write_processed
from src.events.engine import build_event_log
from src.events.controls import build_control_log

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

CHARTS_DIR = PROJECT_ROOT / "reports" / "EXP-001" / "charts"

COLORS = {
    "bounce":       "#2ecc71",
    "break":        "#e74c3c",
    "inconclusive": "#95a5a6",
    "zone":         "#3498db",
    "control":      "#e67e22",
    "price":        "#2c3e50",
    "zone_band":    "#3498db",
}


def main():
    parser = argparse.ArgumentParser(description="Detect touch events + generate charts")
    parser.add_argument("--start",       default=None)
    parser.add_argument("--end",         default=None)
    parser.add_argument("--no-controls", action="store_true",
                        help="Skip matched control generation")
    args = parser.parse_args()

    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("EXP-001 Event Detection + Visual Output")
    logger.info("=" * 60)

    # ── Load data ────────────────────────────────────────────────────────────
    try:
        df = read_raw("BANKNIFTY", "1D", start=args.start, end=args.end)
        zone_frame = read_processed("zone_frame", experiment_id="EXP-001")
    except FileNotFoundError as e:
        logger.error("%s", e)
        logger.error("Run scripts 01, 02, 03 first.")
        sys.exit(1)

    # timestamp is the index after Parquet load — promote to column
    if "timestamp" not in zone_frame.columns:
        zone_frame = zone_frame.reset_index()
    zone_frame["timestamp"] = pd.to_datetime(zone_frame["timestamp"]).dt.tz_convert("Asia/Kolkata")
    if "formed_at" in zone_frame.columns:
        zone_frame["formed_at"] = pd.to_datetime(zone_frame["formed_at"]).dt.tz_convert("Asia/Kolkata")

    # Filter zone_frame to same date range as df
    zone_frame = zone_frame[zone_frame["timestamp"].isin(df.index)]

    logger.info("Loaded %d bars, %d zone entries.", len(df), len(zone_frame))

    # ── Run event detection ──────────────────────────────────────────────────
    logger.info("Running event detection...")
    event_log = build_event_log(df, zone_frame)

    if event_log.empty:
        logger.error("No events detected. Check data and zone_frame.")
        sys.exit(1)

    write_processed(event_log, "event_log", experiment_id="EXP-001")
    logger.info("Saved event_log: %d events", len(event_log))

    # ── Matched controls ─────────────────────────────────────────────────────
    control_log = pd.DataFrame()
    if not args.no_controls:
        logger.info("Generating matched controls...")
        control_log = build_control_log(df, event_log, zone_frame)
        if not control_log.empty:
            write_processed(control_log, "control_log", experiment_id="EXP-001")
            logger.info("Saved control_log: %d controls", len(control_log))

    # ── Charts ───────────────────────────────────────────────────────────────
    logger.info("Generating charts...")

    chart01_price_with_zones(df, zone_frame, event_log)
    chart02_outcome_bar(event_log)
    chart03_bounce_by_type(event_log)
    chart04_touch_count_decay(event_log)
    chart05_mfe_mae_distributions(event_log)
    if not control_log.empty:
        chart06_zones_vs_controls(event_log, control_log)

    logger.info("")
    logger.info("Charts saved to: %s", CHARTS_DIR)
    logger.info("Next step: run scripts/05_statistical_tests.py")


# ── Chart functions ───────────────────────────────────────────────────────────

def chart01_price_with_zones(df, zone_frame, event_log):
    """Price series with zone bands and event markers. Show last 2 years."""
    path = CHARTS_DIR / "01_price_with_zones.png"

    cutoff = df.index.max() - pd.DateOffset(years=2)
    df2 = df[df.index >= cutoff]
    zf2 = zone_frame[zone_frame["timestamp"] >= cutoff]
    ev2 = event_log[event_log["touch_timestamp"] >= cutoff]

    fig, ax = plt.subplots(figsize=(16, 7))

    # Price line
    ax.plot(df2.index, df2["close"], color=COLORS["price"], lw=1.2,
            label="Bank Nifty Close", zorder=3)

    # Zone bands (sample: prev_day levels only to avoid clutter)
    pdh_zones = zf2[zf2["zone_type"].str.contains("prev_day_high")]
    for _, row in pdh_zones.iterrows():
        ax.axhspan(row["zone_low"], row["zone_high"],
                   xmin=_ts_to_xfrac(row["timestamp"], df2.index),
                   xmax=_ts_to_xfrac(row["timestamp"], df2.index, offset=1),
                   alpha=0.08, color=COLORS["zone_band"], zorder=1)

    # Event markers
    bounces = ev2[ev2["result"] == "bounce"]
    breaks  = ev2[ev2["result"] == "break"]
    incon   = ev2[ev2["result"] == "inconclusive"]

    ax.scatter(bounces["touch_timestamp"], bounces["touch_price"],
               marker="^", color=COLORS["bounce"], s=40, zorder=4,
               label=f"Bounce (n={len(bounces)})", alpha=0.8)
    ax.scatter(breaks["touch_timestamp"], breaks["touch_price"],
               marker="v", color=COLORS["break"], s=40, zorder=4,
               label=f"Break (n={len(breaks)})", alpha=0.8)
    ax.scatter(incon["touch_timestamp"], incon["touch_price"],
               marker="o", color=COLORS["inconclusive"], s=15, zorder=4,
               label=f"Inconclusive (n={len(incon)})", alpha=0.5)

    ax.set_title("Bank Nifty — Price with Zone Touch Events (Last 2 Years)",
                 fontsize=13, pad=12)
    ax.set_xlabel("Date")
    ax.set_ylabel("Index Level")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Chart 01 saved: %s", path.name)


def chart02_outcome_bar(event_log):
    """Bar chart: bounce / break / inconclusive counts + rates."""
    path = CHARTS_DIR / "02_event_outcomes_bar.png"

    counts = event_log["result"].value_counts()
    total  = len(event_log)
    labels = ["bounce", "break", "inconclusive"]
    values = [counts.get(l, 0) for l in labels]
    colors = [COLORS[l] for l in labels]
    rates  = [v / total * 100 for v in values]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Counts
    bars = ax1.bar(labels, values, color=colors, edgecolor="white", linewidth=0.8)
    for bar, v in zip(bars, values):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 5,
                 str(v), ha="center", va="bottom", fontsize=11, fontweight="bold")
    ax1.set_title(f"Event Outcomes (n={total})", fontsize=12)
    ax1.set_ylabel("Count")
    ax1.grid(axis="y", alpha=0.3)

    # Rates
    bars2 = ax2.bar(labels, rates, color=colors, edgecolor="white", linewidth=0.8)
    for bar, r in zip(bars2, rates):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                 f"{r:.1f}%", ha="center", va="bottom", fontsize=11, fontweight="bold")
    ax2.set_title("Outcome Rates (%)", fontsize=12)
    ax2.set_ylabel("Rate (%)")
    ax2.set_ylim(0, 100)
    ax2.grid(axis="y", alpha=0.3)

    fig.suptitle("EXP-001: Zone Touch Event Classification", fontsize=13,
                 fontweight="bold", y=1.01)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Chart 02 saved: %s", path.name)


def chart03_bounce_by_type(event_log):
    """Bounce rate per zone type (base types only, ignoring merged)."""
    path = CHARTS_DIR / "03_bounce_rate_by_type.png"

    # Expand merged zone types to base types
    base_types = ["prev_day_high", "prev_day_low", "weekly_high", "weekly_low",
                  "swing_high", "swing_low"]

    rows = []
    for base in base_types:
        subset = event_log[event_log["zone_type"].str.contains(base)]
        if len(subset) == 0:
            continue
        bounce_rate = (subset["result"] == "bounce").mean() * 100
        rows.append({
            "zone_type": base.replace("_", " ").title(),
            "bounce_rate": bounce_rate,
            "n": len(subset),
        })

    if not rows:
        return

    data = pd.DataFrame(rows).sort_values("bounce_rate", ascending=True)

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(data["zone_type"], data["bounce_rate"],
                   color=COLORS["zone"], edgecolor="white", linewidth=0.8)

    for bar, (_, row) in zip(bars, data.iterrows()):
        ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                f"{row['bounce_rate']:.1f}%  (n={row['n']})",
                va="center", fontsize=10)

    ax.set_xlabel("Bounce Rate (%)")
    ax.set_title("EXP-001: Bounce Rate by Zone Type", fontsize=13, pad=12)
    ax.set_xlim(0, 100)
    ax.axvline(50, color="gray", linestyle="--", alpha=0.5, label="50% baseline")
    ax.legend(fontsize=9)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Chart 03 saved: %s", path.name)


def chart04_touch_count_decay(event_log):
    """Bounce rate by touch count (1st, 2nd, 3rd, 4+)."""
    path = CHARTS_DIR / "04_touch_count_decay.png"

    max_show = 5
    rows = []
    for tc in range(1, max_show + 1):
        if tc < max_show:
            subset = event_log[event_log["touch_count_on_zone"] == tc]
            label = f"{tc}{'st' if tc == 1 else 'nd' if tc == 2 else 'rd' if tc == 3 else 'th'}"
        else:
            subset = event_log[event_log["touch_count_on_zone"] >= tc]
            label = f"{tc}+"
        if len(subset) < 5:
            continue
        bounce_rate = (subset["result"] == "bounce").mean() * 100
        rows.append({"touch_count": label, "bounce_rate": bounce_rate, "n": len(subset)})

    if not rows:
        return

    data = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(data["touch_count"], data["bounce_rate"],
                  color=COLORS["zone"], edgecolor="white")

    for bar, (_, row) in zip(bars, data.iterrows()):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                f"{row['bounce_rate']:.1f}%\n(n={row['n']})",
                ha="center", va="bottom", fontsize=9)

    ax.set_xlabel("Touch Count on Zone")
    ax.set_ylabel("Bounce Rate (%)")
    ax.set_title("EXP-001: Bounce Rate by Touch Count\n"
                 "(Does repeated testing weaken zones?)", fontsize=12)
    ax.set_ylim(0, 100)
    ax.axhline(50, color="gray", linestyle="--", alpha=0.5)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Chart 04 saved: %s", path.name)


def chart05_mfe_mae_distributions(event_log):
    """MFE and MAE distributions split by outcome."""
    path = CHARTS_DIR / "05_mfe_mae_distributions.png"

    bounces = event_log[event_log["result"] == "bounce"]
    breaks  = event_log[event_log["result"] == "break"]

    fig, axes = plt.subplots(2, 2, figsize=(14, 9))

    def plot_hist(ax, data, title, color, xlabel):
        if len(data) == 0:
            ax.set_title(title)
            return
        ax.hist(data, bins=40, color=color, edgecolor="white",
                alpha=0.8, density=True)
        ax.axvline(data.median(), color="black", linestyle="--",
                   label=f"Median: {data.median():.1f}")
        ax.set_title(title, fontsize=11)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Density")
        ax.legend(fontsize=9)
        ax.grid(alpha=0.3)

    plot_hist(axes[0, 0], bounces["mfe"],
              f"MFE — Bounces (n={len(bounces)})", COLORS["bounce"],
              "MFE (price units)")
    plot_hist(axes[0, 1], bounces["mae"],
              f"MAE — Bounces (n={len(bounces)})", "#a8d8a8",
              "MAE (price units)")
    plot_hist(axes[1, 0], breaks["mfe"],
              f"MFE — Breaks (n={len(breaks)})", "#f1948a",
              "MFE (price units)")
    plot_hist(axes[1, 1], breaks["mae"],
              f"MAE — Breaks (n={len(breaks)})", COLORS["break"],
              "MAE (price units)")

    fig.suptitle("EXP-001: MFE / MAE Distributions by Outcome", fontsize=13,
                 fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Chart 05 saved: %s", path.name)


def chart06_zones_vs_controls(event_log, control_log):
    """Side-by-side bounce rate: zone touches vs matched controls."""
    path = CHARTS_DIR / "06_zones_vs_controls.png"

    zone_bounce_rate    = (event_log["result"]   == "bounce").mean() * 100
    control_bounce_rate = (control_log["result"] == "bounce").mean() * 100
    zone_n    = len(event_log)
    control_n = len(control_log)

    lift = zone_bounce_rate - control_bounce_rate

    fig, ax = plt.subplots(figsize=(8, 6))
    bars = ax.bar(
        [f"Zone Touches\n(n={zone_n})", f"Matched Controls\n(n={control_n})"],
        [zone_bounce_rate, control_bounce_rate],
        color=[COLORS["zone"], COLORS["control"]],
        edgecolor="white", linewidth=0.8, width=0.4,
    )

    for bar, rate in zip(bars, [zone_bounce_rate, control_bounce_rate]):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.5,
                f"{rate:.1f}%",
                ha="center", va="bottom", fontsize=14, fontweight="bold")

    ax.set_ylabel("Bounce Rate (%)")
    ax.set_ylim(0, max(zone_bounce_rate, control_bounce_rate) * 1.25)
    ax.set_title(
        f"EXP-001: Zone Bounce Rate vs Matched Controls\nLift = {lift:+.1f} pp",
        fontsize=13, pad=12,
    )
    ax.grid(axis="y", alpha=0.3)

    # Annotation
    color = COLORS["bounce"] if lift > 0 else COLORS["break"]
    ax.annotate(
        f"Lift: {lift:+.1f} pp",
        xy=(0.5, max(zone_bounce_rate, control_bounce_rate) * 1.1),
        ha="center", fontsize=13, color=color, fontweight="bold",
        xycoords=("axes fraction", "data"),
    )

    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Chart 06 saved: %s", path.name)


# ── Utility ───────────────────────────────────────────────────────────────────

def _ts_to_xfrac(ts, index, offset=0):
    """Convert a timestamp to x-axis fraction for axhspan."""
    try:
        pos = index.get_loc(ts)
        return max(0.0, min(1.0, (pos + offset) / len(index)))
    except KeyError:
        return 0.0


if __name__ == "__main__":
    main()
