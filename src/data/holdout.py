"""FINAL HOLDOUT VAULT.

The period [HOLDOUT_START, HOLDOUT_END] is SEALED for strategy selection.

Rules:
  - No research, feature analysis, parameter tuning, or model selection may
    use holdout data.
  - A frozen strategy may be evaluated on the holdout EXACTLY ONCE
    (record freeze timestamp first via registry.freeze()).
  - Any code path touching holdout data outside src/validation/holdout.py
    must call assert_not_holdout() / filter_holdout().

Sealed by decision of the project owner on 2026-08-21.
"""
from __future__ import annotations

import pandas as pd

HOLDOUT_START = pd.Timestamp("2026-01-01", tz="UTC")
HOLDOUT_END = None  # open-ended: all of 2026 onward

RESEARCH_END = HOLDOUT_START  # research data must be strictly < this


def is_holdout(ts: pd.Series) -> pd.Series:
    """Boolean mask marking holdout timestamps."""
    if HOLDOUT_END is None:
        return ts >= HOLDOUT_START
    return (ts >= HOLDOUT_START) & (ts < HOLDOUT_END)


def filter_holdout(df: pd.DataFrame, ts_col: str = "ts") -> pd.DataFrame:
    """Return only rows OUTSIDE the holdout vault (for research use)."""
    return df[~is_holdout(df[ts_col])].copy()


def assert_not_holdout(df: pd.DataFrame, ts_col: str = "ts") -> None:
    """Raise if any row falls inside the sealed holdout."""
    n = int(is_holdout(df[ts_col]).sum())
    if n > 0:
        raise ValueError(
            f"HOLDOUT VIOLATION: {n} rows inside sealed vault "
            f"(>= {HOLDOUT_START}). Research code may not access this data."
        )
