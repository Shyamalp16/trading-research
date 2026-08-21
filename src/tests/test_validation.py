"""Anti-overfitting framework tests: chronology, one-shot holdout, MC, stability."""
import numpy as np
import pandas as pd
import pytest

from src.validation.monte_carlo import bootstrap_expectancy, monte_carlo
from src.validation.parameter_stability import (deflated_sharpe,
                                                neighborhood_stability,
                                                plateau_ok)
from src.validation.walk_forward import make_folds, oos_summary, walk_forward


# ---------------- walk-forward ----------------

def _fake_evaluate(profitable_window):
    """Candidates: 'good' profits only in 2021-2022, 'bad' always loses."""
    def fn(hyp, start, end):
        start = pd.Timestamp(start); end = pd.Timestamp(end)
        if hyp["name"] == "good":
            overlap = max(0, (min(end, pd.Timestamp("2023-01-01"))
                              - max(start, pd.Timestamp("2021-01-01"))).days)
            r = np.full(100, 0.1) if overlap > 0 else np.full(10, -0.05)
        else:
            r = np.full(50, -0.02)
        dates = pd.date_range(start, end - pd.Timedelta(days=1), periods=len(r))
        trades = pd.DataFrame({"r_net": r, "trade_date": dates})
        return {"stats": {"n": len(r), "expectancy_r": float(r.mean())},
                "trades": trades}
    return fn


def test_walk_forward_selection_and_chronology():
    dates = pd.Series(pd.date_range("2019-01-01", "2025-12-31", freq="D", tz="UTC"))
    hyps = [{"name": "good"}, {"name": "bad"}]
    res = walk_forward(_fake_evaluate(None), hyps, dates,
                       first_train_years=2, test_years=1)
    hist = res["history"]
    assert len(hist) >= 3
    # folds are chronological and non-overlapping
    for a, b in zip(hist, hist[1:]):
        assert b["test_start"] >= a["test_end"]
    # every fold must have picked a winner and produced OOS stats
    for h in hist:
        assert h["winner"] is not None
        assert "test_stats" in h
    # OOS trades all lie within their fold's test window (asserted in engine)


def test_walk_forward_no_candidate_meets_min_trades():
    def fn(hyp, start, end):
        return {"stats": {"n": 5, "expectancy_r": 0.5}, "trades": pd.DataFrame()}
    dates = pd.Series(pd.date_range("2019-01-01", "2024-12-31", freq="D", tz="UTC"))
    res = walk_forward(fn, [{"name": "x"}], dates, min_trades=30,
                       first_train_years=2, test_years=1)
    assert all(h["winner"] is None for h in res["history"])
    assert oos_summary(res["oos_trades"])["n"] == 0


def test_make_folds_expanding():
    dates = pd.Series(pd.date_range("2018-01-01", "2025-12-31", freq="D", tz="UTC"))
    folds = make_folds(dates, first_train_years=3, test_years=1)
    # expanding train windows
    assert folds[0]["train_end"] < folds[-1]["train_end"]
    assert folds[0]["train_start"] == folds[-1]["train_start"]


# ---------------- holdout vault ----------------

def test_holdout_one_shot(tmp_path, monkeypatch):
    import src.validation.holdout as H
    monkeypatch.setattr(H, "LEDGER", tmp_path / "ledger.json")
    monkeypatch.setattr(H, "RESULTS", tmp_path)

    h = H.freeze({"name": "s1", "rules": [1]})
    called = []

    def eval_fn():
        called.append(1)
        return {"expectancy_r": 0.05}

    r1 = H.evaluate_once(h, eval_fn)
    assert r1["expectancy_r"] == 0.05
    with pytest.raises(RuntimeError):
        H.evaluate_once(h, eval_fn)  # second attempt forbidden
    assert len(called) == 1

    with pytest.raises(ValueError):
        H.evaluate_once("never-frozen", eval_fn)


# ---------------- monte carlo ----------------

def test_monte_carlo_deterministic_and_sane():
    rng = np.random.default_rng(7)
    r = rng.normal(0.05, 0.5, size=300)
    a = monte_carlo(r, n_sims=2000, seed=42)
    b = monte_carlo(r, n_sims=2000, seed=42)
    assert a == b  # deterministic with same seed
    assert a["max_dd_r"]["median"] > 0
    assert a["prob_negative_total"] > 0
    be = bootstrap_expectancy(r, n_sims=2000, seed=42)
    assert be["ci95"][0] <= be["mean"] <= be["ci95"][1]


# ---------------- parameter stability / DSR ----------------

def test_neighborhood_stability_plateau_vs_spike():
    pv = [0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5]
    plateau = [0.1, 0.12, 0.11, 0.13, 0.12, 0.14, 0.12]
    spike = [-0.1, -0.1, -0.1, 0.9, -0.1, -0.1, -0.1]
    s_ok = neighborhood_stability(pv, plateau, center=0.35, tolerance=0.1)
    s_bad = neighborhood_stability(pv, spike, center=0.35, tolerance=0.1)
    assert plateau_ok(s_ok)
    assert not plateau_ok(s_bad)


def test_deflated_sharpe_penalizes_trials():
    sr, n = 0.08, 500
    d1 = deflated_sharpe(sr, n, n_trials=1)
    d1000 = deflated_sharpe(sr, n, n_trials=1000)
    assert d1 > d1000  # more trials -> lower probability SR is real
    assert 0 <= d1000 <= 1
