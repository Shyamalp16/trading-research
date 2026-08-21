"""Phase 3 acceptance: known strategy end-to-end, reproducible.

Strategy under test (acceptance vehicle, NOT an approved strategy):
  NQ OR30 breakout continuation:
    at 10:00 ET, if price broke above the 30-min opening range high and
    trades above VWAP in a non-extreme volatility regime -> LONG.
    Stop = 1x ATR(14d), target = 1.5R, hard flatten by 16:00 ET.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.backtest.costs import CostModel, stress_costs
from src.data.instruments import INSTRUMENTS
from src.backtest.engine import PathBook
from src.data.loaders import load_symbol
from src.discovery.hypotheses import generate_candidates
from src.discovery.runner import default_experiment_log, evaluate_hypothesis, load_events

BASE = {
    "name": "or30_breakout_continuation",
    "family": "opening_behavior",
    "market": "NQ",
    "obs_minute": 30,
    "direction": "long",
    "filters": [
        ["or30_broke_up", "==", 1],
        ["above_vwap", "==", 1],
        ["atr_pctile", "between", [0.2, 0.9]],
    ],
    "stop": {"type": "atr", "mult": 1.0},
    "target": {"type": "rr", "rr": 1.5},
    "time_stop_min": 240,
}


def main():
    log = default_experiment_log("NQ")
    events, _outs = load_events("NQ")
    pb = PathBook(load_symbol("NQ", research_only=True))
    cost = CostModel(INSTRUMENTS["NQ"])

    results = []
    for rr in [1.0, 1.5, 2.0]:
        hyp = {**{k: v for k, v in BASE.items() if k != "target"},
               "target": {"type": "rr", "rr": rr}}
        res = evaluate_hypothesis(hyp, events, pb, cost, log=log)
        o = res["report"]["overall"]
        results.append((rr, o))
        print(f"\n=== RR target {rr} | n={o['n']} ===")
        for k in ["win_rate", "avg_win_r", "avg_loss_r", "expectancy_r",
                  "profit_factor", "max_dd_r", "sharpe_trade", "trades_per_year"]:
            print(f"  {k}: {o.get(k):.3f}" if isinstance(o.get(k), float) else f"  {k}: {o.get(k)}")
        print("  exits:", res["report"].get("exit_reason_counts"))
        print("  by_year:")
        for row in res["report"]["by_year"]:
            print(f"    {row['group']}: n={row['n']} E[R]={row['expectancy_r']:.3f} "
                  f"WR={row['win_rate']:.2f} PF={row['profit_factor']:.2f}")

    # slippage stress on the base hypothesis
    print("\n--- slippage stress (base) ---")
    for label, cm in stress_costs(INSTRUMENTS["NQ"]).items():
        r = evaluate_hypothesis(BASE, events, pb, cm)
        o = r["report"]["overall"]
        print(f"  {label}: n={o['n']} E[R]={o.get('expectancy_r', float('nan')):.3f} "
              f"PF={o.get('profit_factor', float('nan')):.2f}")

    # reproducibility check: rerun base, compare trade-by-trade
    r1 = evaluate_hypothesis(BASE, events, pb, cost)
    r2 = evaluate_hypothesis(BASE, events, pb, cost)
    same = r1["trades"].equals(r2["trades"])
    print(f"\nreproducible: {same}")
    print(f"hypotheses tested this experiment: {log.hypotheses_tested}")
    print(f"experiment_id: {log.experiment_id}")

    out = {
        "experiment_id": log.experiment_id,
        "dataset_versions": log.dataset_versions,
        "hypotheses_tested": log.hypotheses_tested,
        "results": [
            {"rr_target": rr, **{k: v for k, v in o.items()}} for rr, o in results
        ],
    }
    p = Path(__file__).resolve().parents[1] / "results" / "phase3_acceptance.json"
    p.write_text(json.dumps(out, indent=2, default=str))
    print(f"saved -> {p}")


if __name__ == "__main__":
    main()
