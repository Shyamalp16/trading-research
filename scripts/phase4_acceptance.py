"""Phase 4 acceptance: full anti-overfitting pipeline on a real family.

Family: NQ opening-range breakout (long/short) at fixed observation times,
ATR stops, RR targets. Small grid (kept honest): 2 obs times x 2 directions
x 2 RR = 8 candidates.

Pipeline: expanding-window walk-forward (train 2017-2019, then yearly tests
2020..2025) -> OOS aggregate -> Monte Carlo -> bootstrap CI -> deflated
Sharpe with n_trials=8.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.backtest.costs import CostModel
from src.backtest.engine import PathBook
from src.backtest.metrics import core_stats
from src.data.instruments import INSTRUMENTS
from src.data.loaders import load_symbol
from src.discovery.hypotheses import apply_filters, build_specs, hypothesis_id
from src.discovery.runner import default_experiment_log, load_events
from src.validation.monte_carlo import bootstrap_expectancy, monte_carlo
from src.validation.parameter_stability import deflated_sharpe
from src.validation.walk_forward import oos_summary, walk_forward


def make_evaluate(events, pb, cost):
    def evaluate(hyp, start, end):
        sel = apply_filters(events, hyp["filters"], obs_minute=hyp["obs_minute"])
        td = pd.to_datetime(sel["trade_date"]).dt.tz_localize(None)
        sel = sel[(td >= pd.Timestamp(start)) & (td < pd.Timestamp(end))]
        specs = build_specs(hyp, sel)
        trades = run_bt(pb, specs, cost)
        stats = core_stats(trades["r_net"].values) if len(trades) else {"n": 0}
        return {"stats": stats, "trades": trades}
    return evaluate


def run_bt(pb, specs, cost):
    from src.backtest.engine import run_backtest
    return run_backtest(pb, specs, cost_points=cost.cost_in_points(),
                        slippage_points=cost.slippage_points)


def main():
    log = default_experiment_log("NQ")
    events, _ = load_events("NQ")
    pb = PathBook(load_symbol("NQ", research_only=True))
    cost = CostModel(INSTRUMENTS["NQ"])

    hyps = []
    for obs in [30, 90]:
        for direction in ["long", "short"]:
            for rr in [1.0, 2.0]:
                broke_col = "or30_broke_up" if direction == "long" else "or30_broke_dn"
                hyps.append({
                    "name": f"orb_{obs}m_{direction}_rr{rr}",
                    "market": "NQ",
                    "obs_minute": obs,
                    "direction": direction,
                    "filters": [[broke_col, "==", 1],
                                ["above_vwap", "==", 1] if direction == "long"
                                else ["above_vwap", "==", 0]],
                    "stop": {"type": "atr", "mult": 1.0},
                    "target": {"type": "rr", "rr": rr},
                    "time_stop_min": 240,
                })
    for h in hyps:
        log.register(h)

    dates = events["trade_date"]
    res = walk_forward(make_evaluate(events, pb, cost), hyps, dates,
                       first_train_years=3, test_years=1)

    print("=== fold history ===")
    for h in res["history"]:
        w = h["winner"]
        ts = h.get("test_stats", {})
        print(f"test {pd.Timestamp(h['test_start']).year}: "
              f"winner={w['name'] if w else None} "
              f"n={ts.get('n', 0)} E[R]={ts.get('expectancy_r', float('nan')):.3f}")

    oos = res["oos_trades"]
    summ = oos_summary(oos)
    print("\n=== OOS aggregate ===")
    for k, v in summ.items():
        print(f"  {k}: {v}")

    r = oos["r_net"].values
    mc = monte_carlo(r, n_sims=5000, seed=42)
    be = bootstrap_expectancy(r, n_sims=5000, seed=42)
    sr = summ["sharpe_trade"]
    dsr = deflated_sharpe(sr, n=len(r), n_trials=log.hypotheses_tested)
    print("\n=== Monte Carlo ===")
    print(f"  maxDD R p5/p50/p95: {mc['max_dd_r']['p5']:.1f}/"
          f"{mc['max_dd_r']['median']:.1f}/{mc['max_dd_r']['p95']:.1f}")
    print(f"  worst losing streak p95: {mc['max_losing_streak']['p95']:.0f}")
    print(f"  total R p5/p50/p95: {mc['total_r']['p5']:.0f}/"
          f"{mc['total_r']['median']:.0f}/{mc['total_r']['p95']:.0f}")
    print(f"  P(total<0): {mc['prob_negative_total']:.3f}")
    print("\n=== Bootstrap expectancy ===")
    print(f"  mean={be['mean']:.4f} CI95={be['ci95']} P(E<=0)={be['prob_mean_le_0']:.3f}")
    print(f"\n=== Deflated Sharpe (trials={log.hypotheses_tested}) ===")
    print(f"  SR={sr:.3f} -> DSR={dsr:.3f}")

    out = {
        "experiment_id": log.experiment_id,
        "hypotheses_tested": log.hypotheses_tested,
        "hypothesis_ids": log.ids,
        "fold_history": [
            {k: str(v) if k != "winner" and k != "winner_train_stats" and k != "test_stats" and k != "reason" else v
             for k, v in h.items()} for h in res["history"]],
        "oos_summary": summ,
        "monte_carlo": mc,
        "bootstrap_expectancy": be,
        "deflated_sharpe": dsr,
    }
    p = Path(__file__).resolve().parents[1] / "results" / "phase4_acceptance.json"
    p.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nsaved -> {p}")


if __name__ == "__main__":
    main()
