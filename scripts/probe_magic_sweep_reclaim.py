"""Owner's Magic-Hours variant — sweep + reclaim confirmation + limit entry.

Rules (as specified by owner):
  1. Mark magic-hour range high/low (hour H, ET).
  2. Wait for a sweep: price trades beyond high (short setup) or low (long).
  3. Wait for a 5-MINUTE candle to CLOSE back inside the range -> confirmation.
  4. Place LIMIT order at the boundary (sell at high / buy at low).
  5. Take profit at 50% of range (midpoint).

Stop variants tested (owner left stop open):
  - sweep_extreme : beyond the sweep's extreme touch
  - fixed X       : X % of range beyond boundary
  - time          : flat at end of 3h analysis window
Fill never happening = no trade. One setup per day per hour.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.loaders import load_symbol


def day_setup(sub, H, g=None):
    hs, he = H * 60, H * 60 + 60
    mh = sub[(sub.m >= hs) & (sub.m < he)]
    aw = sub[(sub.m >= he) & (sub.m < he + 180)]
    if len(mh) < 30 or len(aw) < 30:
        return None
    hi, lo = float(mh.high.max()), float(mh.low.min())
    if hi <= lo:
        return None
    mid = (hi + lo) / 2
    rng = hi - lo

    # --- sweep: first 1m bar beyond either boundary (skip ambiguous huge bars)
    sweep_t = sweep_side = None
    for r in aw.itertuples(index=False):
        up, dn = r.high > hi, r.low < lo
        if up and dn:
            return None
        if up:
            sweep_t, sweep_side = r.ts, "short"
            break
        if dn:
            sweep_t, sweep_side = r.ts, "long"
            break
    if sweep_t is None:
        return None

    # --- 5-minute candles after sweep; find first closing back inside ---
    aw5 = aw[aw.ts >= sweep_t].copy()
    aw5["bucket"] = aw5.m // 5
    conf_t = None
    for b, g5 in aw5.groupby("bucket"):
        if g5.ts.iloc[-1] <= sweep_t:
            continue
        c = float(g5.close.iloc[-1])
        if sweep_side == "short" and c < hi:
            conf_t = g5.ts.iloc[-1]
            break
        if sweep_side == "long" and c > lo:
            conf_t = g5.ts.iloc[-1]
            break
    if conf_t is None:
        return None

    # sweep extreme while waiting (used for sweep_extreme stop)
    pre = aw[aw.ts <= conf_t]
    ext = float(pre.high.max()) if sweep_side == "short" else float(pre.low.min())

    # --- limit fill at boundary ---
    post = aw[aw.ts > conf_t]
    if sweep_side == "short":
        fill = post[post.high >= hi]
    else:
        fill = post[post.low <= lo]
    if len(fill) == 0:
        return None
    fill_t = fill.ts.iloc[0]

    # --- manage position ---
    live = post[post.ts >= fill_t]
    if sweep_side == "short":
        tp = live[live.low <= mid]
        adverse = live.high  # against short
    else:
        tp = live[live.high >= mid]
        adverse = live.low

    res = {"day": g, "hour": H, "dir": sweep_side, "rng": rng,
           "filled": len(live) > 0}
    if len(live) == 0:
        return res | {"won": False, "exit": "no_fill", "pnl": 0.0,
                      "stop_hit": None}
    # conservative: check stop before TP within each bar via variants outside
    res["sweep_ext"] = abs(ext - lvl_bound(sweep_side, hi, lo)) / rng
    res["tp_time"] = tp.ts.iloc[0] if len(tp) else None
    # adverse excursion only while trade is LIVE (until TP touch)
    live_u = live[live.ts <= res["tp_time"]] if res["tp_time"] is not None else live
    if sweep_side == "short":
        res["max_adverse"] = float((live_u.high.max() - lvl_bound(sweep_side, hi, lo)) / rng)
    else:
        res["max_adverse"] = float((lvl_bound(sweep_side, hi, lo) - live_u.low.min()) / rng)
    res["end_pnl"] = float(((lvl_bound(sweep_side, hi, lo) - live.close.iloc[-1]) / rng)
                           if sweep_side == "short" else
                           ((live.close.iloc[-1] - lvl_bound(sweep_side, hi, lo)) / rng))
    res["won"] = len(tp) > 0
    return res


def lvl_bound(side, hi, lo):
    return hi if side == "short" else lo


def main():
    df = load_symbol("NQ", research_only=True)
    et = df.ts.dt.tz_convert("America/New_York")
    df["d"] = et.dt.date
    df["m"] = et.dt.hour * 60 + et.dt.minute

    rows = []
    for g, sub in df.groupby("d"):
        sub = sub.sort_values("ts")
        for H in range(24):
            r = day_setup(sub, H, g=g)
            if r:
                rows.append(r)
    R = pd.DataFrame(rows)
    R = R[R.filled]
    print(f"setups with limit FILLED: {len(R)} of {len(pd.DataFrame(rows))} signals\n")

    print(f"{'hr':>4} {'n':>6} {'win%':>7} {'medAdv':>8} {'E@swext':>9} "
          f"{'E@50%':>8} {'E@75%':>8} {'E@100%':>8} {'E@time':>8}")
    for H, g in R.groupby("hour"):
        if len(g) < 100:
            continue
        pnl_swext = []
        pnl_fixed = {0.5: [], 0.75: [], 1.0: []}
        pnl_time = []
        for rec in g.itertuples(index=False):
            sign = 1.0 if rec.dir == "short" else -1.0
            # sweep-extreme stop
            if rec.max_adverse >= rec.sweep_ext:
                pnl_swext.append(-rec.sweep_ext)
            elif rec.won:
                pnl_swext.append(0.5)
            else:
                pnl_swext.append(rec.end_pnl)
            # fixed stops
            for X in pnl_fixed:
                if rec.max_adverse >= X:
                    pnl_fixed[X].append(-X)
                elif rec.won:
                    pnl_fixed[X].append(0.5)
                else:
                    pnl_fixed[X].append(rec.end_pnl)
            pnl_time.append(0.5 if rec.won else rec.end_pnl)
        print(f"{H:>4} {len(g):>6} {(g.won).mean():>7.1%} "
              f"{g.max_adverse.median():>8.2f} "
              f"{np.mean(pnl_swext):>+9.3f} "
              f"{np.mean(pnl_fixed[0.5]):>+8.3f} "
              f"{np.mean(pnl_fixed[0.75]):>+8.3f} "
              f"{np.mean(pnl_fixed[1.0]):>+8.3f} "
              f"{np.mean(pnl_time):>+8.3f}")


if __name__ == "__main__":
    main()
