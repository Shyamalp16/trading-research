# PHASE 4 FINDINGS — ANTI-OVERFITTING FRAMEWORK

Date: 2026-08-21
Status: COMPLETE

## What was built

### Walk-forward (`src/validation/walk_forward.py`)
- Expanding-window folds (default: 3 train years, then +1 test year per fold).
- Candidate selection uses TRAIN data only; the winner is frozen before the
  test window is touched.
- **Hard chronology assertion**: every OOS trade must fall inside its fold's
  test window or the engine raises.
- Selection history recorded per fold (who won, on what train stats).

### One-shot holdout protocol (`src/validation/holdout.py`)
- `freeze(definition)` → sha256 hash + UTC timestamp persisted.
- `evaluate_once(hash, fn)` → runs the evaluation ONCE; any second attempt
  raises. Ledger at `results/holdout_evaluations.json`.
- The vault itself remains sealed (2026+ excluded from all research loads).

### Monte Carlo (`src/validation/monte_carlo.py`)
- Bootstrap resampling of trade sequences: max-DD percentiles, losing-streak
  distributions, total-R bands, P(total<0), P(DD > X R).
- Bootstrap CI around expectancy. Seeded → fully reproducible.

### Parameter stability + multiple testing (`src/validation/parameter_stability.py`)
- Neighborhood analysis: fraction of nearby parameters that are also
  profitable (plateau vs spike detection).
- Deflated Sharpe Ratio (Bailey & López de Prado) penalizing N trials.
- Bonferroni note generator for family-wise significance.

## Acceptance run (`scripts/phase4_acceptance.py`)

Family: NQ opening-range breakout, grid of 8 candidates
(obs {30m, 90m} × direction × RR {1.0, 2.0}), walk-forward
train 2017–2019 → tests 2020…2025.

**Results (all OOS):**
- Aggregate: n=219, WR 56.2%, E[R] = +0.023R, PF 1.18, maxDD 7.1R
- Bootstrap 95% CI on expectancy: [−0.027, +0.071] → includes ZERO
- P(expectancy ≤ 0) = 18.5%
- Monte Carlo: median maxDD 4.4R, p95 8.8R; worst losing streak p95 = 9
- **Deflated Sharpe = 0.288** (after just 8 trials) — far below acceptance

**Verdict: REJECTED.** The OR-breakout family shows a hint of long-side drift
but does not survive multiple-testing adjustment. This is the framework
working as designed — most families will die here, and that is fine.

## Test status

31/31 passing (data 9, events 8, backtest 7, validation 7).

## Next: Phase 5 — Discovery V1

Generate ~100–300 economically sensible hypotheses across the feature
families (gap, overnight position, VWAP reclaim/reject, IB compression,
PDH/PDL tests, momentum, mean reversion), screen them through this exact
pipeline, rank by OOS robustness (not in-sample profit), and produce research
reports for survivors.
