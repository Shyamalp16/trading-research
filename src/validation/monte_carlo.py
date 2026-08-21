"""Monte Carlo analysis of trade sequences.

Historical trade ORDER will not repeat. We resample trade sequences to
estimate drawdown / streak / final-P&L distributions.
"""
from __future__ import annotations

import numpy as np


def monte_carlo(r: np.ndarray, n_sims: int = 10_000, seed: int = 42) -> dict:
    """Bootstrap resampling (with replacement) of the observed R series.

    Returns percentile bands for max drawdown, losing streak, total R,
    plus probability of X drawdown and risk-of-ruin style estimates.
    """
    rng = np.random.default_rng(seed)
    r = r[~np.isnan(r)]
    n = len(r)
    if n == 0:
        return {}
    sims_idx = rng.integers(0, n, size=(n_sims, n))
    sims = r[sims_idx]
    eq = np.cumsum(sims, axis=1)
    dd = eq - np.maximum.accumulate(eq, axis=1)
    max_dd = -dd.min(axis=1)
    totals = eq[:, -1]

    streaks = np.zeros(n_sims, dtype=int)
    for s in range(n_sims):
        mx = cur = 0
        for x in sims[s]:
            if x < 0:
                cur += 1
                mx = max(mx, cur)
            else:
                cur = 0
        streaks[s] = mx

    def pct(a, q):
        return float(np.percentile(a, q))

    return {
        "n_trades": n,
        "n_sims": n_sims,
        "max_dd_r": {"p5": pct(max_dd, 5), "p25": pct(max_dd, 25),
                     "median": pct(max_dd, 50), "p75": pct(max_dd, 75),
                     "p95": pct(max_dd, 95)},
        "max_losing_streak": {"p5": pct(streaks, 5), "median": pct(streaks, 50),
                              "p95": pct(streaks, 95)},
        "total_r": {"p5": pct(totals, 5), "p25": pct(totals, 25),
                    "median": pct(totals, 50), "p75": pct(totals, 75),
                    "p95": pct(totals, 95)},
        "prob_dd_exceeds": {f"{x}R": float((max_dd > x).mean())
                            for x in [5, 10, 20, 30]},
        "prob_negative_total": float((totals < 0).mean()),
    }


def bootstrap_expectancy(r: np.ndarray, n_sims: int = 10_000,
                         seed: int = 42) -> dict:
    """CI around mean R via bootstrap."""
    rng = np.random.default_rng(seed)
    r = r[~np.isnan(r)]
    n = len(r)
    means = r[rng.integers(0, n, size=(n_sims, n))].mean(axis=1)
    return {
        "mean": float(r.mean()),
        "ci90": [float(np.percentile(means, 5)), float(np.percentile(means, 95))],
        "ci95": [float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))],
        "prob_mean_le_0": float((means <= 0).mean()),
    }
