"""Daily context: previous-session levels, gap metrics, volatility regime.

All outputs are keyed by trade_date and contain ONLY information available
before that day's RTH open (previous-day and older data). Safe to broadcast
onto intraday events.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.sessions import daily_sessions


def build_daily_context(df: pd.DataFrame) -> pd.DataFrame:
    """df: canonical 1m bars with session cols added. Returns per-trade-date frame."""
    d = daily_sessions(df)

    # --- true range / ATR on RTH daily bars ---
    h, l, c = d["rth_high"], d["rth_low"], d["rth_close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    d["atr14"] = tr.rolling(14, min_periods=10).mean()
    # Volatility regime known BEFORE the session: yesterday's ATR + its
    # expanding percentile rank among all prior days.
    atr_prev = d["atr14"].shift(1)
    d["atr_prev"] = atr_prev
    d["atr_pctile"] = atr_prev.expanding(min_periods=60).apply(
        lambda arr: float((arr[-1] >= arr).mean()), raw=True
    )

    # --- previous-day levels (shift 1 = known at today's open) ---
    for src, dst in [
        ("rth_high", "pdh"), ("rth_low", "pdl"), ("rth_close", "pc"),
        ("rth_open", "po"), ("session_high", "pd_session_high"),
        ("session_low", "pd_session_low"), ("rth_volume", "pd_volume"),
        ("on_high", "pd_on_high"), ("on_low", "pd_on_low"),
    ]:
        d[dst] = d[src].shift(1)

    d["pd_range"] = d["pdh"] - d["pdl"]
    d["pd_return"] = d["rth_close"].pct_change().shift(1)
    # close location within previous day's range
    rng = d["pd_range"].replace(0, np.nan)
    d["pd_close_loc"] = ((d["pc"] - d["pdl"]) / rng).clip(0, 1)

    # --- overnight context for TODAY (complete before RTH open) ---
    on_rng = (d["on_high"] - d["on_low"]).replace(0, np.nan)
    d["on_range"] = d["on_high"] - d["on_low"]
    d["on_range_atr"] = d["on_range"] / d["atr_prev"]
    d["on_return"] = d["on_close"] / d["on_open"] - 1.0
    d["on_volume_atr_norm"] = d["on_volume"] / d["on_volume"].rolling(20, min_periods=10).mean().shift(1)
    d["on_direction"] = np.sign(d["on_close"] - d["on_open"])

    # --- opening gap (RTH open vs prior RTH close) ---
    d["gap"] = d["rth_open"] - d["pc"]
    d["gap_pct"] = d["gap"] / d["pc"]
    d["gap_atr"] = d["gap"] / d["atr_prev"]
    d["gap_dir"] = np.sign(d["gap"])
    d["gap_above_pdh"] = d["rth_open"] > d["pdh"]
    d["gap_below_pdl"] = d["rth_open"] < d["pdl"]

    return d
