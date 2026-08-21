"""Probe: all-session OR30 breakout tracking (user hypothesis).

Instead of checking a fixed observation time, track the opening-range
breakout continuously: the FIRST bar that trades above the OR30 high (long)
or below the OR30 low (short) triggers an entry, whenever it happens.

Variants measured:
  - signal cutoff: breakout must occur before 12:00 / 14:00 / 15:45 ET
  - direction split
  - stop = 1xATR(14d) with RR targets {1.0, 1.5, 2.0}
  - stop = OR30 midpoint (structural) with target = other side of range

This is IN-SAMPLE exploratory screening on research data (no holdout).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.backtest.engine import PathBook
from src.data.loaders import load_symbol


def find_breakouts(pb: PathBook, signal_cutoff_smod: int):
    """Per day: OR30 levels + first breakout info."""
    rows = []
    for d in range(len(pb.starts)):
        s, e = pb.starts[d], pb.ends[d]
        smod = pb.smod[s:e]
        h, l, o, c = pb.h[s:e], pb.l[s:e], pb.o[s:e], pb.c[s:e]
        n = len(smod)
        or_end = int(np.searchsorted(smod, 960, side="left"))
        start_i = or_end  # scan from 10:00
        if or_end == 0 or n - or_end < 10:
            continue
        or_h = float(h[:or_end].max())
        or_l = float(l[:or_end].min())
        day_key = int(pb.keys[s])
        td = pd.Timestamp(day_key, tz="America/New_York")

        up_i = dn_i = None
        for i in range(start_i, n):
            if smod[i] > signal_cutoff_smod:
                break
            up = h[i] > or_h
            dn = l[i] < or_l
            if up and dn:
                break  # same-bar both sides: ambiguous, skip day
            if up:
                up_i = i
                break
            if dn:
                dn_i = i
                break
        rows.append({
            "trade_date": td, "or_high": or_h, "or_low": or_l,
            "or_mid": (or_h + or_l) / 2,
            "dir": "long" if up_i is not None else ("short" if dn_i is not None else None),
            "signal_i": up_i if up_i is not None else dn_i,
            "signal_min": int(smod[up_i if up_i is not None else dn_i] - 930)
            if (up_i is not None or dn_i is not None) else np.nan,
            "n_bars": n,
        })
    return pd.DataFrame(rows)


def simulate_from_signal(pb, sigs, atr_by_day, stop_mode, rr, slip=0.0):
    out = []
    for rec in sigs.itertuples(index=False):
        if rec.dir is None or rec.signal_i is None or pd.isna(rec.signal_i):
            continue
        d = pb.day_index.get(int(pd.Timestamp(rec.trade_date).value))
        s, e = pb.starts[d], pb.ends[d]
        smod, o, h, l, c = pb.smod[s:e], pb.o[s:e], pb.h[s:e], pb.l[s:e], pb.c[s:e]
        i0 = int(rec.signal_i)
        entry_i = i0 + 1  # enter at next bar open
        if entry_i >= e - s:
            continue
        sign = 1.0 if rec.dir == "long" else -1.0
        entry = o[entry_i] + sign * slip
        atr = atr_by_day.get(rec.trade_date)
        if stop_mode == "atr":
            stop_pts = float(atr)
            tgt_pts = stop_pts * rr
        else:  # structural: stop at OR mid, target = opposite side
            if sign > 0:
                stop_pts = entry - rec.or_mid
                tgt_pts = max(rec.or_high - entry, 1e-9)
            else:
                stop_pts = rec.or_mid - entry
                tgt_pts = max(entry - rec.or_low, 1e-9)
        if stop_pts <= 0 or np.isnan(stop_pts):
            continue
        stop_price = entry - sign * stop_pts
        target_price = entry + sign * tgt_pts
        last_i = int(np.searchsorted(smod, 1320, side="left")) - 1
        exit_px = exit_reason = None
        for i in range(entry_i, min(last_i, e - s - 1) + 1):
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
            exit_px, exit_reason = c[min(last_i, e - s - 1)] - sign * slip, "session_end"
        r = sign * (exit_px - entry) / stop_pts
        cost_r = (2 * 2.5 / 20.0 + 2 * slip) / stop_pts  # NQ commissions approx
        out.append({"trade_date": rec.trade_date, "dir": rec.dir,
                    "r_gross": r, "r_net": r - cost_r, "exit": exit_reason,
                    "signal_min": int(smod[i0] - 930)})
    return pd.DataFrame(out)


def report(trades, label):
    if not len(trades):
        print(f"{label}: no trades")
        return
    r = trades.r_net.values
    yr = pd.to_datetime(trades.trade_date).dt.tz_localize(None).dt.year
    print(f"\n=== {label} ===")
    print(f"n={len(r)} WR={(r>0).mean():.3f} E[R]={r.mean():.3f} "
          f"PF={r[r>0].sum()/-r[r<0].sum():.2f} total_R={r.sum():.1f}")
    t = trades.assign(year=yr).groupby("year").agg(
        n=("r_net", "size"), eR=("r_net", "mean"), wr=("r_net", lambda x: (x > 0).mean()))
    print(t.round(3).to_string())


def main():
    pb = PathBook(load_symbol("NQ", research_only=True))

    # daily ATR(14) from RTH bars
    df = load_symbol("NQ", research_only=True)
    from src.data.sessions import add_session_cols, daily_sessions
    d = daily_sessions(add_session_cols(df))
    pc = d["rth_close"].shift(1)
    tr = pd.concat([d.rth_high - d.rth_low, (d.rth_high - pc).abs(),
                    (d.rth_low - pc).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14, min_periods=10).mean().shift(1)
    atr.index = atr.index.astype("datetime64[ns, America/New_York]")
    atr_by_day = atr.to_dict()

    # descriptive: when do breakouts happen?
    for cutoff, label in [(1080, "by 12:00"), (1260, "by 14:00"), (1290, "by 15:45")]:
        sigs = find_breakouts(pb, cutoff)
        have = sigs.dir.notna().mean()
        up = (sigs.dir == "long").mean()
        print(f"days with breakout {label}: {have:.1%} | up-first: {up:.1%} "
              f"of all days ({(sigs.dir=='long').sum()} up / {(sigs.dir=='short').sum()} dn)")

    sigs = find_breakouts(pb, 1290)
    med = sigs.dropna(subset=["dir"])
    med_t = med.signal_min if hasattr(med, "signal_min") else None
    print("\nsignal time (min after open): median="
          f"{int(med.signal_min.median())}, p25={int(med.signal_min.quantile(.25))}, "
          f"p75={int(med.signal_min.quantile(.75))}")

    for cutoff_label, cut in [("sig<=12:00", 1080), ("sig<=14:00", 1260), ("sig<=15:45", 1290)]:
        s = find_breakouts(pb, cut)
        for dirn in ["long", "short"]:
            sub = s[s.dir == dirn]
            t = simulate_from_signal(pb, sub, atr_by_day, "atr", 1.5)
            report(t, f"ATR stop RR1.5 {dirn} [{cutoff_label}]")

    # structural variant: best cutoff
    s = find_breakouts(pb, 1290)
    t = simulate_from_signal(pb, s, atr_by_day, "struct", 0)
    report(t, "STRUCTURAL stop@ORmid target=opposite side [sig<=15:45]")

    Path(__file__).resolve().parents[1].joinpath("results").mkdir(exist_ok=True)


if __name__ == "__main__":
    main()
