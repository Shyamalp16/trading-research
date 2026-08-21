"""Prop simulation for NQ-004 / NQ-005 (and combined) using full trade history.

Dollar sizing: registry risk = $200 per 1R. Each strategy trades ~25x/year,
so we also simulate a COMBINED book (both strategies, same account).
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.backtest.costs import CostModel
from src.backtest.engine import PathBook, run_backtest
from src.data.instruments import INSTRUMENTS
from src.data.loaders import load_symbol
from src.discovery.families import add_derived_columns
from src.discovery.hypotheses import apply_filters, build_specs
from src.discovery.runner import load_events
from src.prop.simulator import FirmRules, monte_carlo_journeys

RISK_PER_TRADE = 200.0


def strategy_trades(name: str):
    events = add_derived_columns(load_events("NQ", research_only=True)[0])
    pb = PathBook(load_symbol("NQ", research_only=True))
    cost = CostModel(INSTRUMENTS["NQ"])
    if name == "NQ-004":
        hyp = {"obs_minute": 90, "direction": "long",
               "filters": [["on_position", "<=", 0.10]],
               "stop": {"type": "atr", "mult": 1.0},
               "target": {"type": "rr", "rr": 99}, "time_stop_min": 100000}
    else:
        hyp = {"obs_minute": 90, "direction": "short",
               "filters": [["on_position", ">=", 0.90]],
               "stop": {"type": "atr", "mult": 1.0},
               "target": {"type": "rr", "rr": 99}, "time_stop_min": 100000}
    sel = apply_filters(events, hyp["filters"], obs_minute=hyp["obs_minute"])
    specs = build_specs(hyp, sel)
    trades = run_backtest(pb, specs, cost_points=cost.cost_in_points(),
                          slippage_points=cost.slippage_points)
    return trades


def main():
    t4 = strategy_trades("NQ-004")
    t5 = strategy_trades("NQ-005")
    print(f"NQ-004 trades: {len(t4)} | NQ-005 trades: {len(t5)}")

    # chronological combined book: sum R per date across strategies
    a = t4[["trade_date", "r_net"]].rename(columns={"r_net": "r4"})
    b = t5[["trade_date", "r_net"]].rename(columns={"r_net": "r5"})
    comb = a.merge(b, on="trade_date", how="outer").fillna(0).sort_values("trade_date")
    comb["r"] = comb.r4 + comb.r5

    rules = FirmRules()
    results = {}
    for label, series in [
        ("NQ-004 only", t4.r_net.values * RISK_PER_TRADE),
        ("NQ-005 only", t5.r_net.values * RISK_PER_TRADE),
        ("Combined NQ-004+005", comb.r.values * RISK_PER_TRADE),
    ]:
        mc = monte_carlo_journeys(series, rules, n_sims=5000,
                                  funded_months=6, seed=42)
        results[label] = mc
        print(f"\n=== {label} | {rules.account_size:.0f}k account ===")
        print(f"  eval pass rate: {mc['pass_rate']:.1%} "
              f"(avg attempts when passing: {mc['avg_attempts_to_pass']:.1f})")
        print(f"  fees mean/p95: ${mc['fees']['mean']:.0f} / ${mc['fees']['p95']:.0f}")
        print(f"  6-month payouts p5/median/p95: "
              f"${mc['payouts']['p5']:.0f} / ${mc['payouts']['median']:.0f} / "
              f"${mc['payouts']['p95']:.0f}")
        print(f"  NET after fees p25/median/p75: "
              f"${mc['net_after_fees']['p25']:.0f} / "
              f"${mc['net_after_fees']['median']:.0f} / "
              f"${mc['net_after_fees']['p75']:.0f}")
        print(f"  P(net negative): {mc['net_after_fees']['prob_negative']:.1%} | "
              f"funded blowup rate: {mc['blowup_rate_funded']:.1%}")
        print(f"  expected net per $1 of fees: "
              f"${mc['expected_net_per_dollar_fees']:.2f}")

    # ---- sizing tiers on the combined book (the real prop question) ----
    print("\n=== sizing tiers (combined book, $50k eval, $2.5k trailing DD) ===")
    for risk in [200, 400, 600, 800]:
        series = comb.r.values * risk
        mc = monte_carlo_journeys(series, rules, n_sims=5000,
                                  funded_months=6, seed=42)
        results[f"combined_risk{risk}"] = mc
        print(f"  risk ${risk}/trade: pass={mc['pass_rate']:.0%} "
              f"net p5/med/p75 = ${mc['net_after_fees']['p5']:.0f} / "
              f"${mc['net_after_fees']['median']:.0f} / "
              f"${mc['net_after_fees']['p75']:.0f} | "
              f"P(neg)={mc['net_after_fees']['prob_negative']:.0%} | "
              f"blowup={mc['blowup_rate_funded']:.0%}")

    RESULTS = Path(__file__).resolve().parents[1] / "results"
    (RESULTS / "prop_simulation.json").write_text(json.dumps(results, indent=2))
    print("\nsaved -> results/prop_simulation.json")


if __name__ == "__main__":
    main()
