"""Expanding-window walk-forward validation.

Protocol:
  For each fold:
    TRAIN on [t0, t_k)  -> evaluate every candidate, select by metric
                            (min trades requirement), FREEZE the winner
    TEST  on [t_k, t_k+1) -> run the frozen winner once

Selection uses ONLY train data. Each test period is evaluated exactly once
per fold with a frozen candidate. All selections are recorded.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def make_folds(dates: pd.Series, first_train_years: int = 3,
               test_years: int = 1) -> list[dict]:
    """Expanding-window folds: train grows by test_years each fold.

    Returns [{train_start, train_end, test_start, test_end}] as Timestamps.
    """
    d = pd.to_datetime(dates).dt.tz_localize(None)
    start, end = d.min(), d.max()
    folds = []
    train_end = start.replace(month=1, day=1) + pd.DateOffset(years=first_train_years)
    while train_end < end:
        test_end = min(train_end + pd.DateOffset(years=test_years), end + pd.Timedelta(days=1))
        folds.append({
            "train_start": start,
            "train_end": train_end,
            "test_start": train_end,
            "test_end": test_end,
        })
        train_end = test_end
    return folds


def select_best(train_results: list[dict], metric: str = "expectancy_r",
                min_trades: int = 30) -> dict | None:
    """Pick the best candidate on TRAIN only. None if nothing qualifies."""
    ok = [r for r in train_results if r["stats"]["n"] >= min_trades]
    if not ok:
        return None
    return max(ok, key=lambda r: r["stats"].get(metric, -np.inf))


def walk_forward(evaluate_fn, hypotheses: list[dict], dates: pd.Series,
                 metric: str = "expectancy_r", min_trades: int = 30,
                 first_train_years: int = 3, test_years: int = 1) -> dict:
    """evaluate_fn(hyp, train_start, train_end) -> {'stats': {...}, 'trades': df}

    The callable MUST restrict evaluation to the given date window; the
    engine asserts chronology afterwards.
    """
    folds = make_folds(dates, first_train_years, test_years)
    oos_frames = []
    history = []
    for f in folds:
        train_results = []
        for h in hypotheses:
            res = evaluate_fn(h, f["train_start"], f["train_end"])
            train_results.append({"hyp": h, **res})
        winner = select_best(train_results, metric, min_trades)
        if winner is None:
            history.append({**f, "winner": None, "reason": "no_candidate_met_min_trades"})
            continue
        test_res = evaluate_fn(winner["hyp"], f["test_start"], f["test_end"])
        tr = test_res["trades"]
        if len(tr):
            td = pd.to_datetime(tr["trade_date"]).dt.tz_localize(None)
            # CHRONOLOGY ASSERTION: OOS trades must lie inside the test window
            assert (td >= f["test_start"]).all() and (td < f["test_end"]).all(), \
                "CHRONOLOGY VIOLATION: OOS trades outside test window"
        oos_frames.append(tr.assign(fold_test_end=f["test_end"]))
        history.append({
            **f,
            "winner": winner["hyp"],
            "winner_train_stats": winner["stats"],
            "test_stats": test_res["stats"],
        })
    oos = pd.concat(oos_frames, ignore_index=True) if oos_frames else pd.DataFrame()
    return {"oos_trades": oos, "history": history}


def oos_summary(oos: pd.DataFrame) -> dict:
    from src.backtest.metrics import core_stats
    if not len(oos):
        return {"n": 0}
    return core_stats(oos["r_net"].values)
