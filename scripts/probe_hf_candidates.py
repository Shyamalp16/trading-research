"""High-frequency hunt: two probes.

PROBE A - 15:00 MOC continuation:
  Magic-hours data shows reversion FAILS at 15:00 ET (only 22% revert)
  because Market-On-Close flows create sustained directional pressure.
  Inversion: if price breaks the 14:00-15:00 range AFTER 15:00, go WITH
  the break into the close (16:00 flat). ~1 signal/day potential.

PROBE B - multi-time overnight-range reversion:
  The validated 11:00 effect also existed at other observation times in
  Discovery V2 survivors (obs 150, 270). Test a session-wide book:
  signals at 10:00 / 11:00 / 12:30 / 14:30 whenever on_position is
  extreme, one position at a time, all flat by 16:00.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.loaders import load_symbol
from scripts.discovery_v2 import load_symbol_events


def probe_a_moc_continuation(symbol: str):
    """Break of the 14:00-15:00 range after 15:00 -> continuation to close."""
    df = load_symbol(symbol, research_only=True)
    et = df.ts.dt.tz_convert("America/New_York")
    df["d"] = et.dt.date
    df["m"] = et.dt.hour * 60 + et.dt.minute

    rows = []
    for g, sub in df.groupby("d"):
        sub = sub.sort_values("ts")
        ref = sub[(sub.m >= 840) & (sub.m < 900)]   # 14:00-15:00
        aft = sub[(sub.m >= 900) & (sub.m < 955)]   # 15:00-15:55
        if len(ref) < 30 or len(aft) < 30:
            continue
        hi, lo = float(ref.high.max()), float(ref.low.min())
        if hi <= lo:
            continue
        # first break after 15:00
        up = aft[aft.high > hi]
        dn = aft[aft.low < lo]
        t_up = up.ts.iloc[0] if len(up) else None
        t_dn = dn.ts.iloc[0] if len(dn) else None
        if t_up is not None and (t_dn is None or t_up <= t_dn):
            direction, lvl, bt = "long", hi, t_up
        elif t_dn is not None:
            direction, lvl, bt = "short", lo, t_dn
        else:
            continue
        post = aft[aft.ts > bt]
        if len(post) == 0:
            continue
        entry = float(post.open.iloc[0])  # next bar open
        exit_px = float(post.close.iloc[-1])
        pnl = (exit_px - entry) if direction == "long" else (entry - exit_px)
        # adverse while live
        if direction == "long":
            adv = float((entry - post.low.min()))
            hit_stop = post[post.low <= entry - adv_stop_pts] if False else None
        rows.append({"day": g, "dir": direction, "pnl_pts": pnl,
                     "rng": hi - lo})
    r = pd.DataFrame(rows)
    r["year"] = pd.to_datetime(r.day).dt.year
    print(f"\n--- PROBE A [{symbol}] 15:00 MOC continuation ---")
    print(f"signals: {len(r)} ({len(r)/9.6:.0f}/yr)")
    for d, gsub in r.groupby("dir"):
        print(f"  {d}: n={len(gsub)} mean={gsub.pnl_pts.mean():+.2f}pts "
              f"WR={(gsub.pnl_pts>0).mean():.1%} "
              f"median={gsub.pnl_pts.median():+.2f}")
    both_pos = (r.groupby('year').apply(lambda x: (x.pnl_pts>0).mean(), include_groups=False))
    print(f"  yearly WR range: {both_pos.min():.0%} - {both_pos.max():.0%}")
    return r


def probe_b_multitime_reversion(symbol: str):
    """Session-wide reversion book at multiple observation times."""
    ev = load_symbol_events(symbol)
    slots = [(60, "10:00"), (90, "11:00"), (150, "12:30"), (210, "13:30")]
    rows = []
    for obs, lbl in slots:
        t = ev[(ev.obs_minute == obs)].dropna(subset=["ret_atr", "on_position"])
        td = pd.to_datetime(t.trade_date).dt.tz_localize(None)
        train_mask = td < pd.Timestamp("2023-01-01")
        tr = t[train_mask]
        lo_thr = float(tr.on_position.quantile(0.20))
        hi_thr = float(tr.on_position.quantile(0.80))
        for side, mask in [("long", t.on_position <= lo_thr),
                           ("short", t.on_position >= hi_thr)]:
            s = t[mask]
            rows.append({"obs": obs, "label": lbl, "side": side,
                         "thr": (lo_thr if side == "long" else hi_thr),
                         "n": len(s),
                         "er_train": float(s[td < TRAIN_END].ret_atr.mean()),
                         "er_test": float(s[td >= TRAIN_END].ret_atr.mean()),
                         "wr_test": float((s[td >= TRAIN_END].ret_atr > 0).mean()),
                         "n_test": int((td >= TRAIN_END).sum())})
    r = pd.DataFrame(rows)
    print(f"\n--- PROBE B [{symbol}] multi-time reversion book ---")
    print(r.round(3).to_string(index=False))
    viable = r[(r.er_train > 0.05) & (r.er_test > 0.03)]
    print(f"viable slots (train+test positive): {len(viable)} of {len(r)} "
          f"-> ~{viable.n.sum()/9.6:.0f} extra signals/yr")
    return r


TRAIN_END = pd.Timestamp("2023-01-01")

if __name__ == "__main__":
    for sym in ["NQ", "ES"]:
        probe_a_moc_continuation(sym)
        probe_b_multitime_reversion(sym)
