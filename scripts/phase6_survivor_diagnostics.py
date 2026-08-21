"""Phase 6a: survivor diagnostics BEFORE any holdout decision.

For the top-5 Discovery V1 candidates:
  1. Parameter-stability neighborhoods (obs_minute x stop_mult x rr)
  2. Monte Carlo drawdown/streak distributions
  3. Regime breakdowns (year, vol tercile, 2022 bear year)
  4. Drift baseline: same rules unconditional-long on the SAME trade dates,
     so we measure the conditional edge over just-being-long.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.backtest.costs import CostModel
from src.backtest.engine import PathBook, run_backtest
from src.backtest.metrics import core_stats
from src.data.instruments import INSTRUMENTS
from src.data.loaders import load_symbol
from src.discovery.families import add_derived_columns, generate_all
from src.discovery.hypotheses import apply_filters, build_specs
from src.discovery.runner import load_events
from src.validation.monte_carlo import bootstrap_expectancy, monte_carlo
from src.validation.parameter_stability import neighborhood_stability

TOP = ["pullback_up_90", "vwap_reclaim_90", "gap_rev_dn_g0.3_30",
       "mom_dn_m0.003_60", "pdh_accept_90"]


def eval_hyp(hyp, events, pb, cost, start=None, end=None):
    sel = apply_filters(events, hyp["filters"], obs_minute=hyp["obs_minute"])
    if start is not None or end is not None:
        td = pd.to_datetime(sel["trade_date"]).dt.tz_localize(None)
        if start is not None:
            sel = sel[td >= pd.Timestamp(start)]
        if end is not None:
            sel = sel[td < pd.Timestamp(end)]
    specs = build_specs(hyp, sel)
    trades = run_backtest(pb, specs, cost_points=cost.cost_in_points(),
                          slippage_points=cost.slippage_points)
    stats = core_stats(trades["r_net"].values) if len(trades) else {"n": 0}
    return stats, trades


def drift_baseline(hyp, events, pb, cost):
    """Unconditional long with identical exit rules on the SAME dates."""
    sel = apply_filters(events, hyp["filters"], obs_minute=hyp["obs_minute"])
    base = pd.DataFrame({
        "trade_date": sel["trade_date"].reset_index(drop=True),
        "obs_minute": hyp["obs_minute"],
        "direction": "long",
        "stop_points": sel["atr_prev"].reset_index(drop=True) * hyp["stop"]["mult"],
        "target_points": sel["atr_prev"].reset_index(drop=True) * hyp["stop"]["mult"] * hyp["target"]["rr"],
        "time_stop_min": float(hyp.get("time_stop_min", 240)),
    })
    trades = run_backtest(pb, base, cost_points=cost.cost_in_points(),
                          slippage_points=cost.slippage_points)
    return core_stats(trades["r_net"].values) if len(trades) else {"n": 0}


def main():
    events = add_derived_columns(load_events("NQ")[0])
    pb = PathBook(load_symbol("NQ", research_only=True))
    cost = CostModel(INSTRUMENTS["NQ"])
    all_hyps = {h["name"]: h for h in generate_all()}

    out = {}
    for name in TOP:
        h = all_hyps[name]
        print(f"\n{'='*70}\n{name}\n{'='*70}")

        # ---- 1. parameter neighborhoods ----
        neighbors = []
        for obs in [h["obs_minute"] - 30, h["obs_minute"], h["obs_minute"] + 30]:
            if obs < 15:
                continue
            for sm in [0.75, 1.0, 1.25]:
                for rr in [1.0, 1.5, 2.0]:
                    nh = {**h, "obs_minute": obs,
                          "stop": {"type": "atr", "mult": sm},
                          "target": {"type": "rr", "rr": rr}}
                    s, _ = eval_hyp(nh, events, pb, cost)
                    neighbors.append({"obs": obs, "sm": sm, "rr": rr,
                                      "er": s.get("expectancy_r", np.nan),
                                      "n": s.get("n", 0)})
        ndf = pd.DataFrame(neighbors)
        center_er = float(ndf[(ndf.obs == h["obs_minute"]) &
                              (ndf.sm == h["stop"]["mult"]) &
                              (ndf.rr == h["target"]["rr"])].er.iloc[0])
        near = ndf[np.abs(ndf.er - 0) >= 0]  # all
        frac_pos = float((ndf.er > 0).mean())
        print(f"neighborhood: {len(ndf)} variants, {frac_pos:.0%} profitable, "
              f"center E[R]={center_er:.3f}, range [{ndf.er.min():.3f}, {ndf.er.max():.3f}]")
        # stability excluding the center cell itself
        others = ndf[~((ndf.obs == h["obs_minute"]) & (ndf.sm == h["stop"]["mult"]) &
                       (ndf.rr == h["target"]["rr"]))]
        stab = neighborhood_stability(list(others.er), list(others.er),
                                      center=center_er, tolerance=10)
        print(f"  neighbors excl center: {(others.er > 0).mean():.0%} profitable")

        # ---- 2. Monte Carlo ----
        _, trades = eval_hyp(h, events, pb, cost)
        r = trades.r_net.values
        mc = monte_carlo(r, n_sims=5000, seed=42)
        be = bootstrap_expectancy(r, n_sims=5000, seed=42)
        print(f"MC: maxDD p50/p95 = {mc['max_dd_r']['median']:.1f}/"
              f"{mc['max_dd_r']['p95']:.1f}R | streak p95={mc['max_losing_streak']['p95']:.0f} | "
              f"P(total<0)={mc['prob_negative_total']:.2f}")
        print(f"bootstrap E[R]: {be['mean']:.4f} CI95={np.round(be['ci95'],4)} "
              f"P(E<=0)={be['prob_mean_le_0']:.2f}")

        # ---- 3. regime breakdowns ----
        td = pd.to_datetime(trades.trade_date).dt.tz_localize(None)
        trades2 = trades.assign(year=td.dt.year)
        by_year = trades2.groupby("year").agg(
            n=("r_net", "size"), er=("r_net", "mean"),
            wr=("r_net", lambda x: (x > 0).mean()))
        bear = trades2[trades2.year == 2022]
        bear_stats = (f"2022: n={len(bear)} E[R]={bear.r_net.mean():.3f}"
                      if len(bear) else "2022: no trades")
        print("by year:")
        print(by_year.round(3).to_string())
        print(f"  {bear_stats}")

        # ---- 4. drift baseline ----
        db = drift_baseline(h, events, pb, cost)
        edge = _full_stats(h, events, pb, cost) - db.get("expectancy_r", np.nan)
        print(f"drift baseline (unconditional long, same dates/rules): "
              f"E[R]={db.get('expectancy_r', np.nan):.4f} -> conditional edge = {edge:+.4f}R")

        out[name] = {
            "neighborhood_frac_profitable": frac_pos,
            "neighborhood_center_er": center_er,
            "monte_carlo": mc,
            "bootstrap": be,
            "by_year": by_year.reset_index().to_dict("records"),
            "drift_baseline_er": db.get("expectancy_r"),
            "conditional_edge_r": edge,
        }

    RESULTS = Path(__file__).resolve().parents[1] / "results"
    (RESULTS / "phase6_survivor_diagnostics.json").write_text(
        json.dumps(out, indent=2, default=str))
    print("\nsaved -> results/phase6_survivor_diagnostics.json")


def _full_stats(h, events, pb, cost):
    s, _ = eval_hyp(h, events, pb, cost)
    return s.get("expectancy_r", np.nan)


if __name__ == "__main__":
    main()
