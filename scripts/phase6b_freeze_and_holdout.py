"""Phase 6b: freeze the three PASS candidates into the registry, then run
the ONE-SHOT holdout evaluation on sealed 2026 data.

This is the moment of truth. Each frozen definition gets exactly one
evaluation on 2026-01-01 → present. Results are permanent.
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
from src.discovery.runner import load_events
from src.strategies import registry
from src.validation.holdout import evaluate_once, freeze

STRATEGIES = {
    "NQ-001": {
        "name": "PDH Acceptance Continuation",
        "version": "1.0.0",
        "source_hypothesis": "pdh_accept_90",
        "family": "levels",
        "markets": ["NQ"],
        "session_window": "09:30-12:00 ET (obs 09:30+90m)",
        "conditions": [
            "price > previous day high at 11:00 ET",
            "ret_5m > 0",
        ],
        "dsl": {
            "obs_minute": 90,
            "direction": "long",
            "filters": [["px_vs_pdh", "==", 1], ["ret_5m", ">", 0]],
            "stop": {"type": "atr", "mult": 1.0},
            "target": {"type": "rr", "rr": 1.5},
            "time_stop_min": 240,
        },
        "risk": {"max_risk_per_trade_usd": 200, "max_contracts": 2},
        "flatten_by_et": "16:00",
        "historical_stats_ref": "results/discovery_v1_ranking.csv#pdh_accept_90",
    },
    "NQ-002": {
        "name": "Gap-Down VWAP Reclaim Reversal",
        "version": "1.0.0",
        "source_hypothesis": "gap_rev_dn_g0.3_30",
        "family": "gap",
        "markets": ["NQ"],
        "session_window": "09:30-12:00 ET (obs 10:00)",
        "conditions": [
            "opening gap < -0.3 ATR",
            "price above VWAP at 10:00 ET",
        ],
        "dsl": {
            "obs_minute": 30,
            "direction": "long",
            "filters": [["gap_atr", "<", -0.3], ["above_vwap", "==", 1]],
            "stop": {"type": "atr", "mult": 1.0},
            "target": {"type": "rr", "rr": 1.5},
            "time_stop_min": 240,
        },
        "risk": {"max_risk_per_trade_usd": 200, "max_contracts": 2},
        "flatten_by_et": "16:00",
        "historical_stats_ref": "results/discovery_v1_ranking.csv#gap_rev_dn_g0.3_30",
    },
    "NQ-003": {
        "name": "Trend Pullback to VWAP",
        "version": "1.0.0",
        "source_hypothesis": "pullback_up_90",
        "family": "pullback",
        "markets": ["NQ"],
        "session_window": "09:30-12:00 ET (obs 11:00)",
        "conditions": [
            "ret_30m > 0.001",
            "distance to VWAP between -0.6 and +0.1 ATR",
            "price above VWAP at 11:00 ET",
        ],
        "dsl": {
            "obs_minute": 90,
            "direction": "long",
            "filters": [["ret_30m", ">", 0.001],
                        ["d_vwap", "between", [-0.6, 0.1]],
                        ["above_vwap", "==", 1]],
            "stop": {"type": "atr", "mult": 1.0},
            "target": {"type": "rr", "rr": 1.5},
            "time_stop_min": 240,
        },
        "risk": {"max_risk_per_trade_usd": 200, "max_contracts": 2},
        "flatten_by_et": "16:00",
        "historical_stats_ref": "results/discovery_v1_ranking.csv#pullback_up_90",
    },
}


def main():
    # ---- freeze into registry AND vault ledger (same hash both places) ----
    from src.validation.holdout import freeze as vault_freeze
    hashes = {}
    for sid, defn in STRATEGIES.items():
        h, path = registry.save_definition(sid, defn)
        vh = vault_freeze(defn)
        assert vh == h, f"hash mismatch {vh} != {h}"
        registry.set_status(sid, defn["version"], h, "VALIDATED")
        hashes[sid] = h
        print(f"frozen {sid} v{defn['version']} -> {h} ({path.name})")

    # ---- build holdout evaluation context (2026 only, in memory) ----
    from src.features.event_builder import compute_events
    print("building full-history events for holdout window ...", flush=True)
    full_feats, _ = compute_events(load_symbol("NQ", research_only=False))
    full_events = add_derived_columns(full_feats)
    td = pd.to_datetime(full_events["trade_date"]).dt.tz_localize(None)
    ho_events = full_events[td >= pd.Timestamp(HOLDOUT_START.tz_localize(None))]
    print(f"holdout events rows: {len(ho_events)} "
          f"({ho_events.trade_date.min()} -> {ho_events.trade_date.max()})")
    pb_full = PathBook(load_symbol("NQ", research_only=False))
    cost = CostModel(INSTRUMENTS["NQ"])

    # ---- one-shot evaluations ----
    results = {}
    for sid, defn in STRATEGIES.items():
        dsl = defn["dsl"]

        def eval_fn(dsl=dsl):
            sel = apply_filters(ho_events, dsl["filters"], obs_minute=dsl["obs_minute"])
            specs = build_specs({"obs_minute": dsl["obs_minute"],
                                 "direction": dsl["direction"],
                                 "stop": dsl["stop"], "target": dsl["target"],
                                 "time_stop_min": dsl["time_stop_min"]}, sel)
            trades = run_backtest(pb_full, specs,
                                  cost_points=cost.cost_in_points(),
                                  slippage_points=cost.slippage_points)
            stats = core_stats(trades["r_net"].values) if len(trades) else {"n": 0}
            return {"stats": stats,
                    "trades_preview": trades.head(5).to_dict("records") if len(trades) else []}

        res = evaluate_once(hashes[sid], eval_fn)
        results[sid] = res
        s = res["stats"]
        print(f"\n=== {sid} {defn['name']} — HOLDOUT (2026) ===")
        print(f"  n={s.get('n')} WR={s.get('win_rate', float('nan')):.3f} "
              f"E[R]={s.get('expectancy_r', float('nan')):.4f} "
              f"PF={s.get('profit_factor', float('nan')):.2f} "
              f"maxDD={s.get('max_dd_r', float('nan')):.1f}R")
        if s.get("n", 0) >= 20 and s.get("expectancy_r", -9) > 0:
            registry.set_status(sid, defn["version"], hashes[sid], "HOLDOUT_PASSED")
            print("  status -> HOLDOUT_PASSED")
        else:
            print("  status stays VALIDATED (insufficient/failed holdout evidence)")

    Path(__file__).resolve().parents[1].joinpath("results", "holdout_results.json").write_text(
        json.dumps({"strategies": {k: v["stats"] for k, v in results.items()}},
                   indent=2, default=str))


if __name__ == "__main__":
    main()
