"""Probe: OR30 breakout with FIXED-POINT exits (owner request).

TP = 30 pts fixed; stops tested: 30 pts and 50 pts.
Uses the all-session first-breakout tracker on NQ research data.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.backtest.engine import PathBook
from src.data.loaders import load_symbol
from scripts.probe_or30_breakout import find_breakouts, report


def sim_fixed(pb, sigs, stop_pts, tgt_pts, slip=0.25):
    out = []
    for rec in sigs.itertuples(index=False):
        if rec.dir is None or pd.isna(rec.signal_i):
            continue
        d = pb.day_index.get(int(pd.Timestamp(rec.trade_date).value))
        s, e = pb.starts[d], pb.ends[d]
        smod, o, h, l, c = pb.smod[s:e], pb.o[s:e], pb.h[s:e], pb.l[s:e], pb.c[s:e]
        i0 = int(rec.signal_i)
        entry_i = i0 + 1
        if entry_i >= e - s:
            continue
        sign = 1.0 if rec.dir == "long" else -1.0
        entry = o[entry_i] + sign * slip
        stop_price = entry - sign * stop_pts
        target_price = entry + sign * tgt_pts
        last_i = min(int(np.searchsorted(smod, 1320, side="left")) - 1, e - s - 1)
        exit_px = exit_reason = None
        for i in range(entry_i, last_i + 1):
            stopped = l[i] <= stop_price if sign > 0 else h[i] >= stop_price
            hit = h[i] >= target_price if sign > 0 else l[i] <= target_price
            if stopped:
                fill = min(stop_price, o[i]) if sign > 0 else max(stop_price, o[i])
                exit_px, exit_reason = fill - sign * slip, "stop"
                break
            if hit:
                exit_px, exit_reason = target_price - sign * slip, "target"
                break
        if exit_px is None:
            exit_px, exit_reason = c[last_i] - sign * slip, "session_end"
        r = sign * (exit_px - entry) / stop_pts
        cost_r = (2 * 2.5 / 20.0 + 2 * slip) / stop_pts
        out.append({"trade_date": rec.trade_date, "dir": rec.dir,
                    "r_gross": r, "r_net": r - cost_r, "exit": exit_reason,
                    "signal_min": int(smod[i0] - 930)})
    return pd.DataFrame(out)


def main():
    pb = PathBook(load_symbol("NQ", research_only=True))
    sigs = find_breakouts(pb, 1290)

    for stop_pts, tgt_pts in [(30.0, 30.0), (50.0, 30.0)]:
        t = sim_fixed(pb, sigs, stop_pts, tgt_pts)
        report(t, f"NQ OR30 breakout | stop {stop_pts:.0f}pts TP {tgt_pts:.0f}pts")
        for dirn in ["long", "short"]:
            sub = t[t.dir == dirn]
            r = sub.r_net.values
            print(f"   {dirn}: n={len(r)} WR={(r>0).mean():.3f} "
                  f"E[R]={r.mean():.3f} PF={r[r>0].sum()/-r[r<0].sum():.2f}")
        print("   exits:", t.exit.value_counts().to_dict())
        # slippage stress
        for slip in [0.5, 0.75]:
            t2 = sim_fixed(pb, sigs, stop_pts, tgt_pts, slip=slip)
            print(f"   slip {slip}pt/fill: E[R]={t2.r_net.mean():.4f}")


if __name__ == "__main__":
    main()
