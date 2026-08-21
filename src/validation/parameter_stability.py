"""Parameter stability + multiple-testing adjustments.

Favor broad plateaus over sharp optima.
"""
from __future__ import annotations

import numpy as np


def neighborhood_stability(param_values: list[float], expectancies: list[float],
                           center: float, tolerance: float) -> dict:
    """How many neighbors of `center` (within +/- tolerance in parameter
    units) are also profitable?"""
    pv = np.asarray(param_values)
    ex = np.asarray(expectancies)
    near = np.abs(pv - center) <= tolerance
    if not near.any():
        return {"n_neighbors": 0}
    n = int(near.sum())
    prof = int((ex[near] > 0).sum())
    return {
        "n_neighbors": n,
        "n_profitable": prof,
        "frac_profitable": prof / n,
        "min_expectancy_nearby": float(ex[near].min()),
        "max_expectancy_nearby": float(ex[near].max()),
        "expectancy_spread_nearby": float(ex[near].max() - ex[near].min()),
    }


def plateau_ok(stability: dict, min_frac: float = 0.7,
               min_neighbors: int = 4) -> bool:
    """A candidate passes only if most nearby parameters are profitable too."""
    if stability.get("n_neighbors", 0) < min_neighbors:
        return False
    return stability["frac_profitable"] >= min_frac


def deflated_sharpe(sr: float, n: int, n_trials: int, skew: float = 0.0,
                    kurtosis: float = 3.0) -> float:
    """Probability that the true SR > 0 after accounting for N trials tried.

    Bailey & Lopez de Prado (2014). sr is per-trade Sharpe (mean/std).
    """
    from scipy.stats import norm
    if n < 2 or n_trials < 1:
        return np.nan
    # expected max SR under the null across n_trials independent trials
    gamma = 0.5772156649
    if n_trials == 1:
        sr0 = 0.0
    else:
        z1 = norm.ppf(1 - 1.0 / n_trials)
        z2 = norm.ppf(1 - 1.0 / (n_trials * np.e))
        var_sr = (1 - skew * sr + (kurtosis - 1) / 4.0 * sr ** 2) / max(n - 1, 1)
        sr0 = np.sqrt(max(var_sr, 1e-12)) * ((1 - gamma) * z1 + gamma * z2)
    denom = np.sqrt(max(1 - skew * sr + (kurtosis - 1) / 4.0 * sr ** 2, 1e-12))
    dsr = norm.cdf((sr - sr0) * np.sqrt(n - 1) / denom)
    return float(dsr)


def multiple_testing_note(n_hypotheses: int, alpha: float = 0.05) -> dict:
    """Bonferroni-adjusted significance threshold for N trials."""
    return {
        "n_hypotheses": n_hypotheses,
        "per_test_alpha": alpha / max(n_hypotheses, 1),
        "bonferroni_note": (
            f"With {n_hypotheses} hypotheses tested, each must show "
            f"p < {alpha / max(n_hypotheses, 1):.6f} to claim family-wise 5% significance."
        ),
    }
