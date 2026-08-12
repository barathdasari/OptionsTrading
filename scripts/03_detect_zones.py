"""
Script: Run zone detection on Bank Nifty daily OHLCV.

Usage
-----
    python scripts/03_detect_zones.py
    python scripts/03_detect_zones.py --start 2018-01-01 --k 0.5
    python scripts/03_detect_zones.py --start 2018-01-01 --k 0.25 0.5 0.75

What it does
------------
1. Loads raw BANKNIFTY daily data
2. Runs causal zone detection (all zone types)
3. Saves zone_frame to data/processed/zone_frame_EXP-001.parquet
4. Prints summary stats
5. If --k has multiple values, runs robustness grid

Run from project root:
    cd "c:/Users/DASABH3/Desktop/Bharath/Personal/Projects/F&O_Trading"
    python scripts/03_detect_zones.py
"""

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.storage import read_raw, write_processed
from src.zones.detector import build_zone_frame, K_PRIMARY

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Detect zones in Bank Nifty data")
    parser.add_argument("--start", default=None, help="Start date YYYY-MM-DD")
    parser.add_argument("--end",   default=None, help="End date YYYY-MM-DD")
    parser.add_argument(
        "--k", nargs="+", type=float, default=[K_PRIMARY],
        help="ATR multiplier(s) for zone width (default: 0.5). "
             "Multiple values run robustness grid.",
    )
    parser.add_argument(
        "--volume-profile", action="store_true",
        help="Include volume profile zones (requires non-zero volume data)",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Bank Nifty Zone Detection — EXP-001")
    logger.info("=" * 60)

    # Load data
    try:
        df = read_raw("BANKNIFTY", "1D", start=args.start, end=args.end)
    except FileNotFoundError:
        logger.error("Raw data not found. Run 01_download_banknifty_daily.py first.")
        sys.exit(1)

    logger.info("Loaded %d bars: %s to %s",
                len(df),
                df.index.min().strftime("%Y-%m-%d"),
                df.index.max().strftime("%Y-%m-%d"))

    # Run detection for each k value
    for k in args.k:
        label = "EXP-001" if k == K_PRIMARY else f"EXP-001-k{k}"
        logger.info("")
        logger.info("--- k = %.2f ---", k)

        zone_frame = build_zone_frame(
            df, k=k,
            include_volume_profile=args.volume_profile,
        )

        if zone_frame.empty:
            logger.error("No zones detected for k=%.2f", k)
            continue

        # Summary stats
        _print_summary(zone_frame, df, k)

        # Save
        path = write_processed(zone_frame, "zone_frame", experiment_id=label)
        logger.info("Saved: %s", path)

    logger.info("")
    logger.info("Next step: run scripts/04_detect_events.py")


def _print_summary(zone_frame, df, k):
    n_bars = df.index.nunique()
    n_zone_bars = zone_frame["timestamp"].nunique()
    total_zone_entries = len(zone_frame)
    avg_zones_per_bar = total_zone_entries / n_zone_bars if n_zone_bars > 0 else 0

    zone_type_counts = zone_frame["zone_type"].value_counts()

    logger.info("Bars with at least one zone : %d / %d (%.1f%%)",
                n_zone_bars, n_bars, n_zone_bars / n_bars * 100)
    logger.info("Total zone-bar entries      : %d", total_zone_entries)
    logger.info("Avg zones per bar           : %.1f", avg_zones_per_bar)
    logger.info("Zone type breakdown:")
    for ztype, cnt in zone_type_counts.items():
        logger.info("  %-35s : %d", ztype, cnt)

    # Score distribution
    score_q = zone_frame["score"].quantile([0.25, 0.5, 0.75])
    logger.info("Score distribution: p25=%.2f  p50=%.2f  p75=%.2f",
                score_q[0.25], score_q[0.5], score_q[0.75])


if __name__ == "__main__":
    main()
