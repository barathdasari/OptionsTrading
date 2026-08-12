"""
Script: Download Bank Nifty daily OHLCV via yfinance.

Usage
-----
    python scripts/01_download_banknifty_daily.py
    python scripts/01_download_banknifty_daily.py --start 2018-01-01
    python scripts/01_download_banknifty_daily.py --start 2018-01-01 --end 2024-12-31

What it does
------------
1. Downloads ^NSEBANK daily OHLCV from yfinance
2. Saves to data/raw/BANKNIFTY/1D/BANKNIFTY_1D.parquet
3. On subsequent runs: auto-appends only new data (incremental update)
4. Writes SHA-256 checksum alongside the Parquet file

Run from project root:
    cd "c:/Users/DASABH3/Desktop/Bharath/Personal/Projects/F&O_Trading"
    python scripts/01_download_banknifty_daily.py
"""

import argparse
import logging
import sys
from pathlib import Path

# Make src importable from project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.downloader import download_banknifty_daily
from src.data.storage import raw_info

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Download Bank Nifty daily OHLCV")
    parser.add_argument(
        "--start", default="2000-01-01",
        help="Start date YYYY-MM-DD (default: 2000-01-01)",
    )
    parser.add_argument(
        "--end", default=None,
        help="End date YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--no-append", action="store_true",
        help="Force full re-download instead of incremental append",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Bank Nifty Daily Download — yfinance")
    logger.info("=" * 60)

    df = download_banknifty_daily(
        start=args.start,
        end=args.end,
        auto_append=not args.no_append,
    )

    if df.empty:
        logger.info("No new data downloaded (already up to date or empty response).")
    else:
        logger.info("Downloaded %d new rows.", len(df))
        logger.info("Date range: %s to %s",
                    df.index.min().strftime("%Y-%m-%d"),
                    df.index.max().strftime("%Y-%m-%d"))

    # Print summary of what's stored
    info = raw_info("BANKNIFTY", "1D")
    logger.info("")
    logger.info("--- Stored data summary ---")
    logger.info("Path       : %s", info.get("path"))
    logger.info("Total rows : %s", info.get("rows"))
    logger.info("Size       : %s MB", info.get("size_mb"))
    logger.info("Checksum   : %s", "OK" if info.get("checksum_valid") else "FAIL")
    logger.info("")
    logger.info("Next step: run scripts/02_validate_data.py")


if __name__ == "__main__":
    main()
