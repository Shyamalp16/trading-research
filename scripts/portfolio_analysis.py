"""Portfolio layer for the session-wide reversion book (#21).

Deliverables:
  1. Component correlation structure (16 slot x side x symbol sleeves)
  2. Same-day concurrency analysis (NQ vs ES, multiple slots)
  3. Combined equity curve + drawdown profile
  4. Bootstrap Monte Carlo of the combined book
  5. Concurrent-risk limits recommendation
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.discovery_v2 import TRAIN_END, load_symbol_events

SLOTS = [60, 90, 150, 210]


def build_book() -> pd.DataFrame:
    """Deduplicated chronological book with sleeve labels."""
    all_trades = []
    for sym in ["NQ", "ES"]:
        ev = load_symbol_events(sym)
        sigs = []
        for obs in SLOTS:
            t = ev[ev.obs_minute == obs].dropna(
                subset=["ret_atr", "on_position"]).copy()
            td = pd.to_datetime(t.trade_date).dt.tz_localize(None)
            tr = t[td < TRAIN_END]
            lo_t = float(tr.on_position.quantile(0.20))
            hi_t = float(tr.on_position.quantile(0.80))
            for _, row in t.iterrows():
                if row.on_position <= lo_t:
                    sigs.append({"symbol": sym, "td": row.trade_date,
                                 "obs": obs, "side": "long",
                                 "r": row.ret_atr})
                elif row.on_position >= hi_t:
                    sigs.append({"symbol": sym, "td": row.trade_date,
                                 "obs": obs, "side": "short",
                                 "r": -row.ret_atr})
        S = pd.DataFrame(sigs).sort_values(["td", "obs"])
        kept = S.drop_duplicates(subset=["symbol", "td"], keep="first")
        all_trades.append(kept)
    B = pd.concat(all_trades, ignore_index=True)
    B["year"] = pd.to_datetime(B.td).dt.tz_localize(None).dt.year
    B["sleeve"] = B.symbol + "_" + B.obs.astype(str) + "_" + B.side
    return B


def main():
    B = build_book()
    print(f"book: {len(B)} trades, {B.year.min()}-{B.year.max()}")

    # ---- 1. sleeve-level stats + correlation ----
    sleeve = B.groupby("sleeve").agg(n=("r", "size"), er=("r", "mean"),
                                     wr=("r", lambda x: (x > 0).mean()))
    print("\n=== sleeve stats ===")
    print(sleeve.round(3).to_string())

    # daily R pivot for correlations (components active on same days)
    B["date"] = pd.to_datetime(B.td).dt.tz_localize(None).dt.date
    daily = B.pivot_table(index="date", columns="sleeve", values="r", aggfunc="sum")
    corr = daily.corr(min_periods=100)
    # average pairwise correlation between sleeves
    mask = ~np.eye(len(corr), dtype=bool)
    _v = corr.values[mask]
    _v = _v[~np.isnan(_v)]
    print(f"\navg pairwise sleeve correlation: {_v.mean():+.3f} (n={len(_v)} pairs)")
    corr.to_csv(Path(__file__).resolve().parents[1] / "results" /
                "portfolio_sleeve_correlation.csv")

    # ---- 2. concurrency ----
    per_day = B.groupby(["date"]).size()
    nq_es_same = (B.groupby("date").symbol.nunique() > 1).mean()
    print("\n=== concurrency ===")
    print(f"distribution of signals/day: {per_day.value_counts().sort_index().to_dict()}")
    print(f"days with BOTH symbols active: {nq_es_same:.1%}")
    print(f"max concurrent positions: 2 by construction (1/symbol); "
          f"days using both: {nq_es_same:.1%}")

    # ---- 3. equity curve / drawdown ----
    eq = B.sort_values(["date", "obs"]).r.cumsum()
    dd = eq - eq.cummax()
    s = {"total_r": float(eq.iloc[-1]), "max_dd_r": float(-dd.min()),
         "er": float(B.r.mean()), "wr": float((B.r > 0).mean())}
    yearly = B.groupby("year").agg(n=("r", "size"), er=("r", "mean"),
                                   total_r=("r", "sum"))
    print("\n=== combined book ===")
    print(f"total {s['total_r']:.0f}R | E[R]={s['er']:.3f} | WR={s['wr']:.1%} "
          f"| maxDD={s['max_dd_r']:.1f}R")
    print(yearly.round(3).to_string())

    # ---- 4. bootstrap MC of ONE YEAR of the book (348 trades) ----
    rng = np.random.default_rng(42)
    r = B.r.values
    n_year = 348
    sims = rng.choice(r, size=(5000, n_year), replace=True)
    eqs = np.cumsum(sims, axis=1)
    dds = eqs - np.maximum.accumulate(eqs, axis=1)
    mc = {
        "trades_per_year": n_year,
        "annual_er_r": float(r.mean() * n_year),
        "ann_maxDD_p50": float(np.percentile(-dds.min(axis=1), 50)),
        "ann_maxDD_p95": float(np.percentile(-dds.min(axis=1), 95)),
        "ann_total_p5": float(np.percentile(eqs[:, -1], 5)),
        "ann_total_median": float(np.percentile(eqs[:, -1], 50)),
        "ann_total_p95": float(np.percentile(eqs[:, -1], 95)),
        "prob_negative_year": float((eqs[:, -1] < 0).mean()),
    }
    print("\n=== annualized bootstrap (348 trades) ===")
    for k, v in mc.items():
        print(f"  {k}: {v:.2f}" if isinstance(v, float) else f"  {k}: {v}")

    # ---- 5. risk-limit recommendation ----
    rec = {
        "max_concurrent_positions": 2,
        "same_symbol_second_signal": "skip (already enforced)",
        "both_symbols_same_day": "allowed; treat as 1.6x single risk (corr ~0.7)",
        "daily_stop_book": "2R",
        "weekly_stop_book": "5R",
    }
    print("\n=== recommended limits ===")
    for k, v in rec.items():
        print(f"  {k}: {v}")

    out = {"sleeve_stats": sleeve.reset_index().to_dict("records"),
           "avg_pairwise_corr": float(np.nanmean(corr.values[mask])),
           "days_both_symbols": float(nq_es_same),
           "combined": s, "yearly": yearly.reset_index().to_dict("records"),
           "bootstrap_annual": mc, "limits": rec}
    (Path(__file__).resolve().parents[1] / "results" / "portfolio_analysis.json"
     ).write_text(json.dumps(out, indent=2, default=str))
    print("\nsaved -> results/portfolio_analysis.json")


if __name__ == "__main__":
    main()
