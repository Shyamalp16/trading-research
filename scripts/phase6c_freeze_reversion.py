"""Phase 6c: freeze Overnight-Range Morning-Reversion strategies (NQ-004/005)
and run their ONE-SHOT holdout evaluation.

Rules pre-registered BEFORE holdout evaluation:
  NQ-004 LONG : on_position <= 0.10 at 11:00 ET -> buy next bar open,
                stop 1xATR(14d), no target, flat by 16:00 ET.
  NQ-005 SHORT: on_position >= 0.90 at 11:00 ET -> sell next bar open,
                stop 1xATR(14d), no target, flat by 16:00 ET.
Thresholds = train-period deciles (2016-2022), chosen before any 2026 look.
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.backtest.costs import CostModel
from src.backtest.engine import PathBook, run_backtest
from src.backtest.metrics import core_stats
from src.data.holdout import HOLDOUT_START
from src.data.instruments import INSTRUMENTS
from src.data.loaders import load_symbol
from src.discovery.families import add_derived_columns
from src.discovery.hypotheses import apply_filters, build_specs
from src.features.event_builder import compute_events
from src.strategies import registry
from src.validation.holdout import evaluate_once, freeze

STRATEGIES = {
    "NQ-004": {
        "name": "Morning Weakness Reversal (Long)",
        "version": "1.0.0",
        "source_hypothesis": "discovery_v2 on_position bottom-decile",
        "family": "overnight_range_reversion",
        "markets": ["NQ"],
        "session_window": "signal 11:00 ET, flat by 16:00 ET",
        "conditions": [
            "on_position <= 0.10 at 11:00 ET (price in bottom 10% of overnight range)",
        ],
        "dsl": {
            "obs_minute": 90,
            "direction": "long",
            "filters": [["on_position", "<=", 0.10]],
            "stop": {"type": "atr", "mult": 1.0},
            "target": None,
            "time_stop_min": None,
            "session_exit": "15:45-16:00 ET",
        },
        "risk": {"max_risk_per_trade_usd": 200, "max_contracts": 2},
        "flatten_by_et": "16:00",
    },
    "NQ-005": {
        "name": "Morning Strength Reversal (Short)",
        "version": "1.0.0",
        "source_hypothesis": "discovery_v2 on_position top-decile",
        "family": "overnight_range_reversion",
        "markets": ["NQ"],
        "session_window": "signal 11:00 ET, flat by 16:00 ET",
        "conditions": [
            "on_position >= 0.90 at 11:00 ET (price in top 10% of overnight range)",
        ],
        "dsl": {
            "obs_minute": 90,
            "direction": "short",
            "filters": [["on_position", ">=", 0.90]],
            "stop": {"type": "atr", "mult": 1.0},
            "target": None,
            "time_stop_min": None,
            "session_exit": "15:45-16:00 ET",
        },
        "risk": {"max_risk_per_trade_usd": 200, "max_contracts": 2},
        "flatten_by_et": "16:00",
    },
}


def main():
    hashes = {}
    for sid, defn in STRATEGIES.items():
        h, path = registry.save_definition(sid, defn)
        vh = freeze(defn)
        assert vh == h
        registry.set_status(sid, defn["version"], h, "VALIDATED")
        hashes[sid] = h
        print(f"frozen {sid} v{defn['version']} -> {h}")

    print("building full-history events for holdout window ...", flush=True)
    feats, _ = compute_events(load_symbol("NQ", research_only=False))
    ev = add_derived_columns(feats)
    td = pd.to_datetime(ev["trade_date"]).dt.tz_localize(None)
    ho = ev[td >= pd.Timestamp(HOLDOUT_START.tz_localize(None))]
    print(f"holdout rows: {len(ho)} ({ho.trade_date.min()} -> {ho.trade_date.max()})")
    pb = PathBook(load_symbol("NQ", research_only=False))
    cost = CostModel(INSTRUMENTS["NQ"])

    results = {}
    for sid, defn in STRATEGIES.items():
        dsl = defn["dsl"]

        def eval_fn(dsl=dsl):
            sel = apply_filters(ho, dsl["filters"], obs_minute=dsl["obs_minute"])
            specs = build_specs({"obs_minute": dsl["obs_minute"],
                                 "direction": dsl["direction"],
                                 "stop": dsl["stop"],
                                 "target": {"type": "rr", "rr": 99} if dsl["target"] is None else dsl["target"],
                                 "time_stop_min": 100000 if dsl["time_stop_min"] is None else dsl["time_stop_min"]},
                                sel)
            trades = run_backtest(pb, specs, cost_points=cost.cost_in_points(),
                                  slippage_points=cost.slippage_points)
            stats = core_stats(trades["r_net"].values) if len(trades) else {"n": 0}
            return {"stats": stats}

        res = evaluate_once(hashes[sid], eval_fn)
        results[sid] = res
        s = res["stats"]
        print(f"\n=== {sid} {defn['name']} — HOLDOUT (2026) ===")
        print(f"  n={s.get('n')} WR={s.get('win_rate', float('nan')):.3f} "
              f"E[R]={s.get('expectancy_r', float('nan')):.4f} "
              f"PF={s.get('profit_factor', float('nan')):.2f} "
              f"maxDD={s.get('max_dd_r', float('nan')):.1f}R")
        status = "HOLDOUT_PASSED" if s.get("n", 0) >= 15 and s.get("expectancy_r", -9) > 0 else "VALIDATED"
        registry.set_status(sid, defn["version"], hashes[sid], status)
        print(f"  status -> {status}")

    Path(__file__).resolve().parents[1].joinpath("results", "holdout_results_v2.json").write_text(
        json.dumps({"strategies": {k: v["stats"] for k, v in results.items()}},
                   indent=2, default=str))


if __name__ == "__main__":
    main()
