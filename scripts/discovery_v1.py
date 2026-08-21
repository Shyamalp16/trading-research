"""Discovery V1 screening run.

Protocol:
  1. Generate hypothesis families (~200 candidates), register all IDs.
  2. Per candidate: full-sample stats on research data (2016-2025).
  3. Strict single split per candidate: train 2016-2022, test 2023-2025
     (test touched exactly once per candidate).
  4. Family-level walk-forward (joint selection per fold, train-only).
  5. Rank by OOS robustness; flag DSR; save ranking CSV + JSON.
"""
import json
import sys
import time
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
from src.discovery.hypotheses import apply_filters, build_specs, hypothesis_id
from src.discovery.runner import default_experiment_log, load_events
from src.validation.parameter_stability import deflated_sharpe

SPLIT_TRAIN_END = pd.Timestamp("2023-01-01")


def eval_window(hyp, events, pb, cost, start=None, end=None):
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


def main():
    log = default_experiment_log("NQ")
    events = add_derived_columns(load_events("NQ")[0])
    pb = PathBook(load_symbol("NQ", research_only=True))
    cost = CostModel(INSTRUMENTS["NQ"])

    hyps = generate_all()
    print(f"candidates generated: {len(hyps)}")

    rows = []
    t0 = time.time()
    for i, h in enumerate(hyps):
        log.register(h)
        full_stats, _ = eval_window(h, events, pb, cost)
        tr_stats, _ = eval_window(h, events, pb, cost, end=SPLIT_TRAIN_END)
        te_stats, te_trades = eval_window(h, events, pb, cost, start=SPLIT_TRAIN_END)
        sr = te_stats.get("sharpe_trade", np.nan)
        dsr = deflated_sharpe(sr, n=te_stats.get("n", 0),
                              n_trials=len(hyps)) if te_stats.get("n", 0) > 10 else np.nan
        rows.append({
            "name": h["name"], "family": h["family"],
            "hyp_id": hypothesis_id(h),
            "obs_minute": h["obs_minute"], "direction": h["direction"],
            "n_full": full_stats.get("n", 0),
            "er_full": full_stats.get("expectancy_r", np.nan),
            "pf_full": full_stats.get("profit_factor", np.nan),
            "wr_full": full_stats.get("win_rate", np.nan),
            "n_train": tr_stats.get("n", 0),
            "er_train": tr_stats.get("expectancy_r", np.nan),
            "n_test": te_stats.get("n", 0),
            "er_test": te_stats.get("expectancy_r", np.nan),
            "pf_test": te_stats.get("profit_factor", np.nan),
            "wr_test": te_stats.get("win_rate", np.nan),
            "dsr_test": dsr,
        })
        if (i + 1) % 25 == 0:
            print(f"  {i+1}/{len(hyps)} screened ({time.time()-t0:.0f}s)")

    df = pd.DataFrame(rows)

    # OOS-robust ranking: require decent sample both periods,
    # positive expectancy in BOTH train and test
    df["oos_positive"] = (df.er_train > 0) & (df.er_test > 0) & (df.n_test >= 30)
    df = df.sort_values(["oos_positive", "er_test", "n_test"],
                        ascending=[False, False, False])

    RESULTS = Path(__file__).resolve().parents[1] / "results"
    df.to_csv(RESULTS / "discovery_v1_ranking.csv", index=False)

    print("\n=== top 20 by OOS (2023-2025) among train-positive ===")
    cols = ["name", "family", "n_full", "er_full", "er_train", "n_test",
            "er_test", "pf_test", "dsr_test"]
    top = df[df.oos_positive].head(20)
    print(top[cols].to_string(index=False))

    print("\n=== family summary (median er_test, count positive OOS) ===")
    fam = df.groupby("family").agg(
        n=("name", "size"),
        med_er_test=("er_test", "median"),
        pos_oos=("oos_positive", "sum"))
    print(fam.sort_values("pos_oos", ascending=False).to_string())

    meta = {
        "experiment_id": log.experiment_id,
        "dataset_versions": log.dataset_versions,
        "hypotheses_tested": log.hypotheses_tested,
        "split_train_end": str(SPLIT_TRAIN_END),
        "n_oos_positive": int(df.oos_positive.sum()),
    }
    (RESULTS / "discovery_v1_meta.json").write_text(json.dumps(meta, indent=2))
    print(f"\nsaved ranking + meta to results/  ({time.time()-t0:.0f}s total)")

    # ---- joint walk-forward over ALL candidates (selection on train only) ----
    from src.validation.walk_forward import oos_summary, walk_forward

    def wf_eval(hyp, start, end):
        s, t = eval_window(hyp, events, pb, cost, start=start, end=end)
        return {"stats": s, "trades": t}

    print("\n=== family-level walk-forward (joint selection) ===")
    for fam in df.family.unique():
        fam_hyps = [h for h in hyps if h["family"] == fam]
        res = walk_forward(wf_eval, fam_hyps, events["trade_date"],
                           first_train_years=4, test_years=1, min_trades=25)
        oos = res["oos_trades"]
        s = oos_summary(oos)
        if s.get("n", 0):
            print(f"  {fam}: OOS n={s['n']} E[R]={s['expectancy_r']:.3f} "
                  f"PF={s['profit_factor']:.2f} maxDD={s['max_dd_r']:.1f}R")
            oos.to_csv(RESULTS / f"discovery_v1_wf_{fam}.csv", index=False)


if __name__ == "__main__":
    main()
