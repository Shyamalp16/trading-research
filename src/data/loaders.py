"""Loaders for raw 1-minute bar data.

Canonical in-memory schema (all loaders return this):
    ts        datetime64[ns, UTC]
    symbol    str
    open      float64
    high      float64
    low       float64
    close     float64
    volume    float64
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

CANONICAL_COLS = ["ts", "symbol", "open", "high", "low", "close", "volume"]

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df[CANONICAL_COLS].copy()
    if df["ts"].dt.tz is None:
        df["ts"] = df["ts"].dt.tz_localize("UTC")
    else:
        df["ts"] = df["ts"].dt.tz_convert("UTC")
    df = df.sort_values("ts").reset_index(drop=True)
    return df


def load_parquet(path: str | Path) -> pd.DataFrame:
    return _normalize(pd.read_parquet(path))


def load_symbol(symbol: str, raw_dir: str | Path | None = None,
                research_only: bool = False) -> pd.DataFrame:
    """Load the canonical 1m dataset for a continuous symbol (e.g. 'NQ', 'ES', 'GC').

    research_only=True strips the sealed holdout period (see src/data/holdout.py).
    """
    raw = Path(raw_dir) if raw_dir else RAW_DIR
    import re
    # Precise token match: 'NQ' must appear as a path token, not inside a word
    # (Windows globbing is case-insensitive: '*ES*' would match 'futures_GC').
    pat = re.compile(rf"(?:^|[_\-]){re.escape(symbol)}(?=[_\-.\d])", re.IGNORECASE)
    matches = [m for m in raw.glob("*.parquet")
               if not m.name.startswith("duplicate_") and pat.search(m.stem)]
    if not matches:
        raise FileNotFoundError(f"No parquet found for symbol {symbol} in {raw}")
    # Use the largest file as canonical full-history source
    path = max(matches, key=lambda p: p.stat().st_size)
    df = load_parquet(path)
    # Merge any supplementary history files (e.g. *_pre2021) for the same symbol.
    for extra in matches:
        if extra == path:
            continue
        part = load_parquet(extra)
        df = (pd.concat([part, df], ignore_index=True)
                .drop_duplicates(subset="ts", keep="last")
                .sort_values("ts").reset_index(drop=True))
    if research_only:
        from src.data.holdout import filter_holdout
        df = filter_holdout(df)
    return df


def dataset_version(path: str | Path) -> dict:
    """Fingerprint a raw dataset for reproducibility records."""
    import hashlib
    p = Path(path)
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return {"path": str(p), "size_bytes": p.stat().st_size, "sha256": h.hexdigest()}
