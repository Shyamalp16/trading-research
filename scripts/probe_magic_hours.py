"""Independent replication of the 'Magic Hours' mean-reversion study.

Methodology (per the gist):
  - Magic Hour H establishes a range [low, high] with midpoint mid.
  - During the NEXT 3 hours: first breakout beyond high (long) or low (short).
  - WIN: price returns to mid within the 3-hour window.
  - LOSS: no return to mid within window.
  - Track MAE (worst adverse excursion) as % of range.

We verify on OUR data (NQ 2016-2025, GC 2016-2025) and compare to the
published table. We also compute what the gist omits: EXPECTANCY with a
realistic stop, because win rate alone is meaningless without payoff.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.loaders import load_symbol


def day_magic_hours(sub: pd.DataFrame):
    """sub: one Globex trading day of 1m bars sorted by ts, with 'm' = ET minute."""
    out = {}
    rth_mask = (sub.m >= 570) & (sub.m < 960)
    for H in range(24):
        h_start, h_end = H * 60, H * 60 + 60
        # magic hour must be fully inside available data (skip maintenance break)
        if h_start >= 1020:  # 17:00+ ET never fully present
            continue
        mh = sub[(sub.m >= h_start) & (sub.m < h_end)]
        aw = sub[(sub.m >= h_end) & (sub.m < h_end + 180)]
        if len(mh) < 30 or len(aw) < 30:
            continue
        hi, lo = float(mh.high.max()), float(mh.low.min())
        if hi <= lo:
            continue
        mid = (hi + lo) / 2
        rng = hi - lo
        # first breakout
        bo_up = aw[aw.high > hi]
        bo_dn = aw[aw.low < lo]
        t_up = bo_up.ts.iloc[0] if len(bo_up) else None
        t_dn = bo_dn.ts.iloc[0] if len(bo_dn) else None
        direction = None
        if t_up is not None and (t_dn is None or t_up <= t_dn):
            direction = "long"
            entry_level = hi
            bo_time = t_up
        elif t_dn is not None:
            direction = "short"
            entry_level = lo
            bo_time = t_dn
        else:
            continue
        post = aw[aw.ts >= bo_time]
        if direction == "long":
            hit_mid = post[post.low <= mid]
            if len(hit_mid):
                live = post[post.ts <= hit_mid.ts.iloc[0]]  # while trade open
                mae = float((live.low.min() - entry_level) / rng)
            else:
                mae = float((post.low.min() - entry_level) / rng)
            ret = float((mid - entry_level) / rng)
        else:
            hit_mid = post[post.high >= mid]
            if len(hit_mid):
                live = post[post.ts <= hit_mid.ts.iloc[0]]
                mae = float((entry_level - live.high.max()) / rng)
            else:
                mae = float((entry_level - post.high.max()) / rng)
            ret = float((entry_level - mid) / rng)
        won = len(hit_mid) > 0
        if won:
            tt = int((hit_mid.ts.iloc[0] - bo_time).total_seconds() // 60)
        else:
            tt = np.nan
        out[H] = {"direction": direction, "won": won, "mae": mae,
                  "ret_if_win": ret, "time_min": tt,
                  "ext": float(max(abs(post.high.max() - hi),
                                   abs(lo - post.low.max())) / rng)}
    return out


def run(symbol: str):
    df = load_symbol(symbol, research_only=True)
    et = df.ts.dt.tz_convert("America/New_York")
    df["d"] = et.dt.date
    df["m"] = et.dt.hour * 60 + et.dt.minute

    rows = []
    for g, sub in df.groupby("d"):
        sub = sub.sort_values("ts")
        res = day_magic_hours(sub)
        for H, r in res.items():
            rows.append({"day": g, "hour": H, **r})
    df_res = pd.DataFrame(rows)
    print(f"\n{'='*72}\n{symbol} — Magic Hours replication (our data)\n{'='*72}")
    print(f"{'hr':>4} {'dir':>6} {'n':>6} {'win%':>7} {'medT':>6} {'MAE%':>7} "
          f"{'E[ret]%rng':>11}")
    agg = df_res.groupby("hour").agg(
        n=("won", "size"), win=("won", "mean"),
        medT=("time_min", "median"), mae=("mae", "mean"))
    # expectancy with stop at 100% of range beyond entry (gist suggestion 75-100%)
    for h, gsub in df_res.groupby("hour"):
        stopped = gsub.mae <= -1.0
        e = np.where(stopped, -1.0,
                     np.where(gsub.won, gsub.ret_if_win, gsub.mae))
        agg.loc[h, "E_stop100"] = float(np.mean(e))
    agg = agg.sort_values("win", ascending=False)
    for h, r in agg.iterrows():
        print(f"{h:>4} {'':>6} {r.n:>6} {r.win:>7.1%} {r.medT:>6.0f} "
              f"{r.mae:>7.1%} {r.E_stop100:>11.3f}")
    return df_res, agg


if __name__ == "__main__":
    for sym in ["NQ", "GC"]:
        run(sym)
