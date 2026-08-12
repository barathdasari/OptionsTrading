"""
Script: Validate raw Bank Nifty OHLCV data quality.

Usage
-----
    python scripts/02_validate_data.py
    python scripts/02_validate_data.py --start 2018-01-01 --end 2024-12-31
    python scripts/02_validate_data.py --save-report

What it does
------------
1. Loads raw data from data/raw/BANKNIFTY/1D/
2. Runs all quality checks (schema, OHLC integrity, gaps, outliers, stale prices)
3. Prints a validation report to console
4. Exits with code 1 if any CRITICAL issues found (fail-fast)
5. Optionally saves report to reports/EXP-001/data_quality_report.txt

Run from project root:
    cd "c:/Users/DASABH3/Desktop/Bharath/Personal/Projects/F&O_Trading"
    python scripts/02_validate_data.py
"""

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.storage import read_raw
from src.data.validator import validate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Validate Bank Nifty raw data")
    parser.add_argument("--start", default=None, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default=None, help="End date YYYY-MM-DD")
    parser.add_argument(
        "--save-report", action="store_true",
        help="Save report to reports/EXP-001/data_quality_report.txt",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Bank Nifty Data Quality Validation")
    logger.info("=" * 60)

    # Load raw data
    try:
        df = read_raw("BANKNIFTY", "1D", start=args.start, end=args.end)
    except FileNotFoundError:
        logger.error(
            "Raw data not found. Run scripts/01_download_banknifty_daily.py first."
        )
        sys.exit(1)

    logger.info("Loaded %d rows from raw store.", len(df))

    # Run validation
    report = validate(
        df,
        instrument="BANKNIFTY",
        timeframe="1D",
        start=args.start or df.index.min().strftime("%Y-%m-%d"),
        end=args.end or df.index.max().strftime("%Y-%m-%d"),
    )

    # Print report (encode to ascii, replacing any non-ascii chars)
    summary = report.summary().encode("ascii", errors="replace").decode("ascii")
    print("\n" + summary)

    # Save report
    if args.save_report:
        report_dir = PROJECT_ROOT / "reports" / "EXP-001"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "data_quality_report.txt"
        report_path.write_text(report.summary())
        logger.info("Report saved to %s", report_path)

    # Fail-fast on CRITICAL issues
    if not report.passed:
        logger.error(
            "%d CRITICAL issue(s) found. Fix data before proceeding to research.",
            len(report.critical_issues),
        )
        for issue in report.critical_issues:
            logger.error("  CRITICAL — %s: %s", issue.check, issue.message)
        sys.exit(1)

    logger.info("")
    logger.info("Validation PASSED. Data is ready for research.")
    logger.info(
        "Rows: %d  |  Date range: %s to %s",
        report.total_rows, report.date_range[0], report.date_range[1],
    )
    logger.info("")
    logger.info("Next step: open research/01_data_quality/ notebook for")
    logger.info("deeper exploratory analysis, then proceed to zone detection.")


if __name__ == "__main__":
    main()
