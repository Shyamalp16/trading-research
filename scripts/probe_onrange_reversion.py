"""Probe: Overnight-range morning-reversion (Discovery V2's headline finding).

Finding: at 11:00 ET, price position within the overnight range is
monotonically related to the close: morning weakness -> rally into close,
morning strength -> fade into close. Replicates on NQ and ES.

Tradeable versions tested here (train-only thresholds):
  LONG : on_position <= train 10th pct  (buy morning weakness)
  SHORT: on_position >= train 90th pct  (fade morning strength)
Rules: enter next-bar open after 11:00, stop = 1xATR(14d), NO target,
exit 15:45 ET. Flat by 16:00 always.
"""
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
from src.discovery.runner import load_events
from src.validation.monte_carlo import bootstrap_expectancy, monte_carlo

TRAIN_END = pd.Timestamp("2023-01-01")


def build_specs(ev, lo_thr, hi_thr, obs=90):
    sel = ev[(ev.obs_minute == obs) & ev.atr_prev.notna()].copy()
    td = pd.to_datetime(sel.trade_date).dt.tz_localize(None)
    longs = sel[sel.on_position <= lo_thr]
    shorts = sel[sel.on_position >= hi_thr]

    def mk(sub, direction):
        return pd.DataFrame({
            "trade_date": sub.trade_date.reset_index(drop=True),
            "obs_minute": obs,
            "direction": direction,
            "stop_points": sub.atr_prev.reset_index(drop=True),
            "target_points": np.nan,
            "time_stop_min": np.nan,  # exit handled by session end 15:45?
        })

    # time exit at 15:45: engine's session_end exits at 16:00; we accept
    # 16:00 flatten (owner allows anything closed by 16:00).
    return mk(longs, "long"), mk(shorts, "short")


def run(sym):
    ev = load_events(sym, research_only=True)[0]
    train = ev[pd.to_datetime(ev.trade_date).dt.tz_localize(None) < TRAIN_END]
    lo_thr = float(train[train.obs_minute == 90].on_position.quantile(0.10))
    hi_thr = float(train[train.obs_minute == 90].on_position.quantile(0.90))
    print(f"\n### {sym} | thresholds from train: long<= {lo_thr:.3f}, short>= {hi_thr:.3f}")

    pb = PathBook(load_symbol(sym, research_only=True))
    cost = CostModel(INSTRUMENTS[sym])
    longs, shorts = build_specs(ev, lo_thr, hi_thr)

    for label, specs in [("LONG weakness", longs), ("SHORT strength", shorts)]:
        trades = run_backtest(pb, specs, cost_points=cost.cost_in_points(),
                              slippage_points=cost.slippage_points)
        s = core_stats(trades.r_net.values)
        td = pd.to_datetime(trades.trade_date).dt.tz_localize(None)
        tr = trades.assign(year=td.dt.year)
        by_year = tr.groupby("year").agg(n=("r_net", "size"),
                                         er=("r_net", "mean"),
                                         wr=("r_net", lambda x: (x > 0).mean()))
        exits = trades.exit_reason.value_counts().to_dict()
        mc = monte_carlo(trades.r_net.values, n_sims=5000, seed=42)
        be = bootstrap_expectancy(trades.r_net.values, n_sims=5000, seed=42)
        print(f"\n--- {sym} {label} ---")
        print(f"n={s['n']} WR={s['win_rate']:.3f} E[R]={s['expectancy_r']:.3f} "
              f"PF={s['profit_factor']:.2f} maxDD={s['max_dd_r']:.1f}R")
        print(f"exits: {exits}")
        print(f"MC maxDD p50/p95: {mc['max_dd_r']['median']:.1f}/{mc['max_dd_r']['p95']:.1f}R "
              f"| P(total<0)={mc['prob_negative_total']:.2f}")
        print(f"bootstrap E[R] CI95: {np.round(be['ci95'],3)}")
        print(by_year.round(3).to_string())


if __name__ == "__main__":
    for sym in ["NQ", "ES"]:
        run(sym)
