"""Prop simulation, calendar-honest cadence: combined NQ-004+005 book
trades ~6x/month. 12 real months funded phase. Sizing tiers."""
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


def main():
    events = add_derived_columns(load_events("NQ", research_only=True)[0])
    pb = PathBook(load_symbol("NQ", research_only=True))
    cost = CostModel(INSTRUMENTS["NQ"])

    def get(direction, col, op):
        hyp = {"obs_minute": 90, "direction": direction,
               "filters": [["on_position", op, col]],
               "stop": {"type": "atr", "mult": 1.0},
               "target": {"type": "rr", "rr": 99}, "time_stop_min": 100000}
        sel = apply_filters(events, hyp["filters"], obs_minute=90)
        specs = build_specs(hyp, sel)
        return run_backtest(pb, specs, cost_points=cost.cost_in_points(),
                            slippage_points=cost.slippage_points)

    t4 = get("long", 0.10, "<=")
    t5 = get("short", 0.90, ">=")
    a = t4[["trade_date", "r_net"]].rename(columns={"r_net": "r4"})
    b = t5[["trade_date", "r_net"]].rename(columns={"r_net": "r5"})
    comb = a.merge(b, on="trade_date", how="outer").fillna(0).sort_values("trade_date")
    comb["r"] = comb.r4 + comb.r5
    years = (pd.to_datetime(comb.trade_date).max() - pd.to_datetime(comb.trade_date).min()).days / 365
    print(f"combined trades: {len(comb)} over {years:.1f}y "
          f"({len(comb)/years:.1f}/month)")

    rules = FirmRules()
    results = {}
    for risk in [200, 400, 600, 800]:
        series = comb.r.values * risk
        mc = monte_carlo_journeys(series, rules, n_sims=5000,
                                  funded_months=12, trades_per_month=6, seed=42)
        results[f"risk{risk}"] = mc
        nf = mc["net_after_fees"]
        print(f"risk ${risk}/trade | 12 real months | pass={mc['pass_rate']:.0%} "
              f"net p5/med/p75 = ${nf['p5']:.0f} / ${nf['median']:.0f} / ${nf['p75']:.0f} "
              f"| P(neg)={nf['prob_negative']:.0%} blowup={mc['blowup_rate_funded']:.0%} "
              f"| $net per $1 fees = {mc['expected_net_per_dollar_fees']:.1f}")

    RESULTS = Path(__file__).resolve().parents[1] / "results"
    (RESULTS / "prop_simulation_calendar.json").write_text(
        json.dumps(results, indent=2, default=str))
    print("saved -> results/prop_simulation_calendar.json")


if __name__ == "__main__":
    main()
