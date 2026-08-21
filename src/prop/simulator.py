"""Prop-firm account economics simulator.

Consumes a chronological dollar-P&L trade series and simulates complete
prop-firm journeys:

    [eval attempts: pass/fail/reset] -> [funded account] -> [payouts]

Modelled rules (all configurable):
  - evaluation profit target, trailing drawdown (trade-time approximation),
    minimum trading days, per-attempt reset fee
  - funded phase: trailing drawdown until safety buffer, monthly payouts,
    profit split, consistency rule (best day share of recent profits)

Limitations (documented honestly):
  - drawdown tracked at TRADE-CLOSE granularity, not tick-by-tick;
    intraday spikes between trades are not seen (our strategies hold one
    position at a time and flatten daily, so this approximation is mild)
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class FirmRules:
    account_size: float = 50_000.0
    # evaluation
    eval_profit_target: float = 3_000.0
    eval_trailing_dd: float = 2_500.0
    eval_min_days: int = 5
    eval_reset_fee: float = 150.0
    eval_activation_fee: float = 150.0     # one-time on passing
    # funded
    funded_trailing_dd: float = 2_500.0    # trails until buffer reached
    dd_buffer_target: float = 2_500.0      # once profit exceeds this, DD stops trailing
    payout_min_profit: float = 500.0       # monthly minimum profit to request payout
    payout_split: float = 0.90             # trader keeps 90%
    consistency_max_day_share: float = 0.45  # best day <= 45% of payout-period profit
    max_attempts: int = 10


def _simulate_eval(trades: np.ndarray, idx: int, rules: FirmRules):
    """Run one evaluation attempt over the trade stream starting at idx.

    Returns (passed, days_traded, next_idx, pnl).
    """
    equity = 0.0
    hwm = 0.0
    days = set()
    i = idx
    while i < len(trades):
        equity += trades[i]
        days.add(i)
        hwm = max(hwm, equity)
        if equity >= rules.eval_profit_target and len(days) >= rules.eval_min_days:
            return True, len(days), i + 1, equity
        if equity <= hwm - rules.eval_trailing_dd:
            return False, len(days), i + 1, equity
        i += 1
    return False, len(days), i, equity  # ran out of trades


def _consistency_ok(day_pnls: dict, rules: FirmRules) -> bool:
    if not day_pnls:
        return True
    pos = {d: p for d, p in day_pnls.items() if p > 0}
    total = sum(pos.values())
    if total <= 0:
        return True
    best = max(pos.values())
    return best / total <= rules.consistency_max_day_share


def simulate_journey(trades: np.ndarray, rules: FirmRules,
                     funded_months: int = 6, trades_per_month: int = 20,
                     rng: np.random.Generator | None = None) -> dict:
    """One full journey: repeated eval attempts, then funded phase."""
    rng = rng or np.random.default_rng()
    fees = 0.0
    attempts = 0
    idx = 0
    passed_at = None
    while attempts < rules.max_attempts and idx < len(trades):
        attempts += 1
        fees += rules.eval_reset_fee
        passed, _, idx, _ = _simulate_eval(trades, idx, rules)
        if passed:
            fees += rules.eval_activation_fee
            passed_at = idx
            break
    if passed_at is None:
        return {"passed": False, "attempts": attempts, "fees": fees,
                "gross_funded_pnl": 0.0, "payouts": 0.0, "net": -fees}

    # ---- funded phase ----
    equity = 0.0
    hwm = 0.0
    dd_active = True          # trails until safety buffer reached, then static
    month_days: dict = {}
    payouts = 0.0
    gross = 0.0
    i = passed_at
    months_done = 0
    while months_done < funded_months and i < len(trades):
        m_trades = 0
        month_pnl = {}
        while m_trades < trades_per_month and i < len(trades):
            equity += trades[i]
            gross += trades[i]
            hwm = max(hwm, equity)
            month_pnl[i] = trades[i]
            m_trades += 1
            i += 1
            floor = (hwm - rules.funded_trailing_dd) if dd_active \
                else -rules.funded_trailing_dd
            if equity <= floor:
                return {"passed": True, "attempts": attempts, "fees": fees,
                        "gross_funded_pnl": gross, "payouts": payouts,
                        "net": payouts - fees, "blown_up": True}
        months_done += 1
        # monthly payout: everything above the safety buffer, if consistent
        if equity - rules.dd_buffer_target >= rules.payout_min_profit \
                and _consistency_ok(month_pnl, rules):
            withdrawable = (equity - rules.dd_buffer_target) * rules.payout_split
            payouts += withdrawable
            equity -= withdrawable / rules.payout_split
        if equity >= rules.dd_buffer_target:
            dd_active = False  # buffer secured -> static DD
    return {"passed": True, "attempts": attempts, "fees": fees,
            "gross_funded_pnl": gross, "payouts": payouts,
            "net": payouts - fees, "blown_up": False}


def monte_carlo_journeys(dollar_trades: np.ndarray, rules: FirmRules,
                         n_sims: int = 5000, funded_months: int = 6,
                         trades_per_month: int = 20, seed: int = 42) -> dict:
    """Bootstrap trade orderings; simulate journeys; aggregate distributions."""
    rng = np.random.default_rng(seed)
    t = dollar_trades[~np.isnan(dollar_trades)]
    res = []
    for s in range(n_sims):
        stream = rng.permutation(t)
        res.append(simulate_journey(stream, rules, funded_months=funded_months,
                                    trades_per_month=trades_per_month, rng=rng))
    df = pd.DataFrame(res)

    def pct(a, q):
        return float(np.percentile(a, q))

    passed = df[df.passed]
    return {
        "n_sims": n_sims,
        "pass_rate": float(df.passed.mean()),
        "avg_attempts_to_pass": float(passed.attempts.mean()) if len(passed) else np.nan,
        "fees": {"mean": float(df.fees.mean()), "p95": pct(df.fees, 95)},
        "payouts": {"p5": pct(df.payouts, 5), "p25": pct(df.payouts, 25),
                    "median": pct(df.payouts, 50), "p75": pct(df.payouts, 75),
                    "p95": pct(df.payouts, 95)},
        "net_after_fees": {"p5": pct(df.net, 5), "p25": pct(df.net, 25),
                           "median": pct(df.net, 50), "p75": pct(df.net, 75),
                           "p95": pct(df.net, 95),
                           "prob_negative": float((df.net < 0).mean())},
        "blowup_rate_funded": float(df.get("blown_up", pd.Series(False, index=df.index)).fillna(False).mean()),
        "expected_net_per_dollar_fees": float(df.net.sum() / max(df.fees.sum(), 1e-9)),
    }
