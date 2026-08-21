# PHASE 6b FINDINGS — REGISTRY FREEZE & ONE-SHOT HOLDOUT

Date: 2026-08-21
Status: COMPLETE — holdout vault opened exactly once per strategy, now re-sealed

## What happened

1. Three PASS candidates frozen as formal v1.0.0 definitions
   (`configs/strategies/NQ-00{1,2,3}_1.0.0_*.yaml`), sha256-hashed,
   recorded in both the registry and the vault ledger.
2. Evaluation code path dry-run verified on 2025 research data BEFORE the
   one-shot (matched known per-year numbers exactly).
3. One-shot holdout evaluation executed on 2026-01-02 → 2026-08-20
   (~155 trading days). Results are permanent (`results/holdout_results.json`,
   `results/holdout_evaluations.json`). Any re-evaluation attempt raises.

## HOLDOUT RESULTS (never seen by any research process)

| ID | Strategy | n | Win rate | E[R] | PF | MaxDD |
|---|---|---|---|---|---|---|
| NQ-001 | PDH Acceptance Continuation | 38 | 65.8% | **+0.014R** | 1.13 | 2.4R |
| NQ-002 | Gap-Down VWAP Reclaim Reversal | 23 | 56.5% | **+0.009R** | 1.06 | 1.7R |
| NQ-003 | Trend Pullback to VWAP | 54 | 57.4% | **+0.011R** | 1.09 | 2.1R |

All three positive out-of-sample. Status → HOLDOUT_PASSED (pre-registered
gate: n ≥ 20 and E[R] > 0).

## Honest interpretation

- This is genuine out-of-sample confirmation of DIRECTION for all three
  edges — the research pipeline produced something real, not pure artifacts.
- Magnitudes degraded vs in-sample (+0.03R → +0.01R), which is typical and
  expected. These are SMALL edges: roughly +0.01R per trade means ~$2 per
  $200-risked trade before slippage stress. Not life-changing money;
  potentially real money at scale with low costs.
- Individually, none reaches statistical significance (n = 23–54).
  The joint evidence (3/3 positive across independent setups) is more
  informative than any single result.
- NQ-002's sample is thin; treat it as the weakest of the three.

## Next: Phase 7 — Paper Forward Monitor

Run the live monitor against real-time data producing setup events for these
three frozen definitions only. No orders. Accumulate forward observations to
compare forward-paper vs holdout behavior. Rules are FROZEN: any change
creates v1.1.0 and resets forward statistics.
