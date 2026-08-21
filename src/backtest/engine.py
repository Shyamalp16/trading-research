"""Event-driven trade simulation on 1-minute bars.

Trade model:
  - Market entry at the OPEN of the first bar at/after the observation time,
    plus adverse slippage.
  - Protective stop and profit target as absolute prices derived from the
    entry and hypothesis-specified distances.
  - Conservative same-bar rule: if a bar touches BOTH stop and target, the
    STOP is assumed to fill first.
  - Time stop / session end: exit at that bar's close.

All exits pay slippage (stops additionally gap if the bar opens through them).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.sessions import add_session_cols


class PathBook:
    """Compact per-day RTH bar arrays for fast trade simulation."""

    def __init__(self, df: pd.DataFrame):
        s = add_session_cols(df)
        r = s[s["is_rth"]].copy()
        r["smod"] = (r["ts_et"].dt.hour * 60 + r["ts_et"].dt.minute + 360) % 1440
        r = r.sort_values(["trade_date", "ts"]).reset_index(drop=True)
        self.keys = r["trade_date"].astype("datetime64[ns, America/New_York]").astype("int64").values
        self.smod = r["smod"].values
        self.o = r["open"].values
        self.h = r["high"].values
        self.l = r["low"].values
        self.c = r["close"].values
        u = np.unique(self.keys)
        self.starts = np.searchsorted(self.keys, u, side="left")
        self.ends = np.searchsorted(self.keys, u, side="right")
        self.day_index = {int(k): i for i, k in enumerate(u)}

    def day_arrays(self, trade_date: pd.Timestamp):
        key = int(pd.Timestamp(trade_date).value)  # ns since epoch
        i = self.day_index.get(key)
        if i is None:
            return None
        s, e = self.starts[i], self.ends[i]
        return self.smod[s:e], self.o[s:e], self.h[s:e], self.l[s:e], self.c[s:e]


def simulate_trade(pb: PathBook, trade_date, obs_minute: int, direction: str,
                   stop_points: float, target_points: float | None,
                   time_stop_min: int | None, session_end_smod: int = 1320,
                   slippage_points: float = 0.0) -> dict | None:
    """Simulate one trade. Returns dict with entry/exit info and gross R."""
    arrs = pb.day_arrays(trade_date)
    if arrs is None:
        return None
    smod, o, h, l, c = arrs
    n = len(smod)
    t_key = 930 + obs_minute  # session-relative minute key of observation
    cut = int(np.searchsorted(smod, t_key, side="left"))
    if cut >= n:
        return None

    sign = 1.0 if direction == "long" else -1.0
    entry = o[cut] + sign * slippage_points
    stop_price = entry - sign * stop_points
    target_price = entry + sign * target_points if target_points else None

    exit_px = None
    exit_reason = None
    exit_i = None
    last_i = int(np.searchsorted(smod, session_end_smod, side="left")) - 1
    last_i = min(last_i, n - 1)

    for i in range(cut, last_i + 1):
        stopped = l[i] <= stop_price if sign > 0 else h[i] >= stop_price
        hit_tgt = target_price is not None and (
            h[i] >= target_price if sign > 0 else l[i] <= target_price)
        if stopped:  # conservative: stop checked before target
            # gap-through: fill at worse of stop_price and this bar's open
            fill = min(stop_price, o[i]) if sign > 0 else max(stop_price, o[i])
            exit_px = fill - sign * slippage_points
            exit_reason = "stop"
            exit_i = i
            break
        if hit_tgt:
            exit_px = target_price - sign * slippage_points
            exit_reason = "target"
            exit_i = i
            break
        if time_stop_min is not None and smod[i] >= t_key + time_stop_min:
            exit_px = c[i] - sign * slippage_points
            exit_reason = "time"
            exit_i = i
            break
    if exit_px is None:
        exit_px = c[last_i] - sign * slippage_points
        exit_reason = "session_end"
        exit_i = last_i

    r_multiple = sign * (exit_px - entry) / stop_points
    hold_min = int(smod[exit_i] - t_key)
    return {
        "entry": float(entry), "exit": float(exit_px),
        "stop_price": float(stop_price),
        "target_price": float(target_price) if target_price else np.nan,
        "r_multiple_gross": float(r_multiple),
        "exit_reason": exit_reason, "hold_min": hold_min,
    }


def run_backtest(pb: PathBook, specs: pd.DataFrame, cost_points: float = 0.0,
                 slippage_points: float = 0.0) -> pd.DataFrame:
    """specs: DataFrame with columns [trade_date, obs_minute, direction,
    stop_points, target_points, time_stop_min]. Returns per-trade results."""
    rows = []
    for rec in specs.itertuples(index=False):
        res = simulate_trade(
            pb, rec.trade_date, int(rec.obs_minute), rec.direction,
            float(rec.stop_points), float(rec.target_points)
            if rec.target_points and not np.isnan(rec.target_points) else None,
            int(rec.time_stop_min) if rec.time_stop_min and not np.isnan(rec.time_stop_min) else None,
            slippage_points=slippage_points,
        )
        if res is None:
            continue
        res["trade_date"] = rec.trade_date
        res["obs_minute"] = int(rec.obs_minute)
        rows.append(res)
    out = pd.DataFrame(rows)
    if len(out):
        out = out.merge(
            specs[["trade_date", "obs_minute", "stop_points"]],
            on=["trade_date", "obs_minute"], how="left")
        out["r_net"] = out["r_multiple_gross"] - cost_points / out["stop_points"]
    return out
