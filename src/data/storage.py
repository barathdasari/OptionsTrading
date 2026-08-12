"""
Parquet read/write utilities.

Raw data is immutable — never overwrite raw files.
All derived data written to data/processed/.
"""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
METADATA_DIR = PROJECT_ROOT / "data" / "metadata"


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def write_raw(df: pd.DataFrame, instrument: str, timeframe: str) -> Path:
    """
    Write raw OHLCV dataframe to Parquet. Never overwrites existing file.
    Returns path written.

    instrument : e.g. "BANKNIFTY"
    timeframe  : e.g. "1D", "5min"
    """
    path = _raw_path(instrument, timeframe)
    if path.exists():
        raise FileExistsError(
            f"Raw file already exists: {path}\n"
            "Raw files are immutable. To append new data use append_raw()."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_parquet(df, path)
    _write_checksum(path)
    logger.info("Written raw: %s  rows=%d", path, len(df))
    return path


def append_raw(df: pd.DataFrame, instrument: str, timeframe: str) -> Path:
    """
    Append new rows to existing raw Parquet file.
    Deduplicates on index (timestamp). Sorts by index after merge.
    """
    path = _raw_path(instrument, timeframe)
    if path.exists():
        existing = read_raw(instrument, timeframe)
        combined = pd.concat([existing, df])
        combined = combined[~combined.index.duplicated(keep="last")]
        combined.sort_index(inplace=True)
    else:
        combined = df.sort_index()

    path.parent.mkdir(parents=True, exist_ok=True)
    _write_parquet(combined, path)
    _write_checksum(path)
    logger.info("Appended raw: %s  total_rows=%d  new_rows=%d",
                path, len(combined), len(df))
    return path


def write_processed(df: pd.DataFrame, name: str, experiment_id: str = "") -> Path:
    """Write processed/derived data. Safe to overwrite."""
    suffix = f"_{experiment_id}" if experiment_id else ""
    path = PROCESSED_DIR / f"{name}{suffix}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_parquet(df, path)
    logger.info("Written processed: %s  rows=%d", path, len(df))
    return path


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def read_raw(instrument: str, timeframe: str,
             start: str = None, end: str = None) -> pd.DataFrame:
    """
    Read raw Parquet. Validates checksum before returning.
    start/end : 'YYYY-MM-DD' strings for date filtering (optional).
    """
    path = _raw_path(instrument, timeframe)
    if not path.exists():
        raise FileNotFoundError(f"Raw file not found: {path}")
    _verify_checksum(path)
    df = _read_parquet(path)
    if start:
        df = df[df.index >= pd.Timestamp(start, tz="Asia/Kolkata")]
    if end:
        df = df[df.index <= pd.Timestamp(end, tz="Asia/Kolkata")]
    return df


def read_processed(name: str, experiment_id: str = "") -> pd.DataFrame:
    suffix = f"_{experiment_id}" if experiment_id else ""
    path = PROCESSED_DIR / f"{name}{suffix}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Processed file not found: {path}")
    return _read_parquet(path)


# ---------------------------------------------------------------------------
# Metadata helpers
# ---------------------------------------------------------------------------

def list_raw_files() -> list[Path]:
    return sorted(RAW_DIR.rglob("*.parquet"))


def raw_info(instrument: str, timeframe: str) -> dict:
    """Return summary info about a raw file without loading all data."""
    path = _raw_path(instrument, timeframe)
    if not path.exists():
        return {"exists": False, "path": str(path)}
    meta = pq.read_metadata(path)
    schema = pq.read_schema(path)
    return {
        "exists": True,
        "path": str(path),
        "rows": meta.num_rows,
        "columns": schema.names,
        "size_mb": round(path.stat().st_size / 1e6, 2),
        "checksum_valid": _verify_checksum(path, raise_on_fail=False),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _raw_path(instrument: str, timeframe: str) -> Path:
    return RAW_DIR / instrument / timeframe / f"{instrument}_{timeframe}.parquet"


def _write_parquet(df: pd.DataFrame, path: Path) -> None:
    table = pa.Table.from_pandas(df, preserve_index=True)
    pq.write_table(table, path, compression="snappy")


def _read_parquet(path: Path) -> pd.DataFrame:
    table = pq.read_table(path)
    df = table.to_pandas()
    if df.index.name == "__null_dask_index__" or df.index.dtype == "int64":
        # index wasn't preserved — try to set timestamp column
        for col in ("timestamp", "Datetime", "Date"):
            if col in df.columns:
                df.set_index(col, inplace=True)
                break
    df.index = pd.to_datetime(df.index, utc=True).tz_convert("Asia/Kolkata")
    df.index.name = "timestamp"
    return df


def _checksum_path(parquet_path: Path) -> Path:
    return parquet_path.with_suffix(".sha256")


def _write_checksum(path: Path) -> None:
    digest = _sha256(path)
    meta = {
        "file": path.name,
        "sha256": digest,
        "written_at": datetime.utcnow().isoformat(),
    }
    _checksum_path(path).write_text(json.dumps(meta, indent=2))


def _verify_checksum(path: Path, raise_on_fail: bool = True) -> bool:
    cpath = _checksum_path(path)
    if not cpath.exists():
        if raise_on_fail:
            raise FileNotFoundError(f"Checksum file missing for {path}")
        return False
    stored = json.loads(cpath.read_text())["sha256"]
    actual = _sha256(path)
    if stored != actual:
        msg = f"Checksum mismatch for {path} — file may be corrupted."
        if raise_on_fail:
            raise ValueError(msg)
        logger.warning(msg)
        return False
    return True


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
