# PHASE 5 FINDINGS — STRATEGY DISCOVERY V1

Date: 2026-08-21
Status: COMPLETE (first full screen)

## Scope

114 hypotheses across 9 economically motivated families on NQ
(2016-05 → 2025-12 research data; 2026 holdout untouched):

gap behavior, overnight-position extremes, VWAP reclaim/reject/extension,
IB compression/expansion, PDH/PDL accept/reject, momentum continuation,
failed breakouts, trend-pullback-to-VWAP, volatility-conditioned breakouts.

All hypothesis IDs + dataset sha256 fingerprints registered
(`results/discovery_v1_meta.json`, `results/discovery_v1_ranking.csv`).

## Protocol

Per candidate:
1. Full-sample stats (research period only).
2. Strict single split: train 2016–2022 vs test 2023–2025 — test touched
   exactly once per candidate.
3. Family-level expanding walk-forward with joint selection per fold
   (train-only selection; chronology asserted).

## Survivors (positive train AND positive test, n_test ≥ 30)

| Rank | Candidate | n_full | E[R] test | PF test | DSR |
|---|---|---|---|---|---|
| 1 | vwap_reclaim_90 (+rr/sm variants) | 205 | +0.076…+0.092 | 1.8–2.0 | ≤0.32 |
| 2 | pullback_up_90 (+variants) | 706 | +0.052…+0.069 | 1.4 | ≤0.30 |
| 3 | gap_rev_dn_g0.3_30 | 223 | +0.083 | 1.51 | 0.10 |
| 4 | mom_dn_m0.003_60 | 384 | +0.048 | 1.30 | 0.08 |
| 5 | pdh_accept_90 | 381 | +0.037 | 1.29 | 0.05 |

Family walk-forward OOS aggregates:
- **pullback: n=449, E[R]=+0.043R, PF=1.26, maxDD 4.8R** ← strongest
- ib: n=327, +0.030R · levels: n=281, +0.026R · momentum: n=288, +0.018R
- volatility: n=48, +0.057R (tiny sample) · gap: n=98, +0.011R
- vwap family-level flat (reclaim strength is recent-years concentrated)
- overnight: **−0.196R, maxDD 61R — catastrophic, rejected**

## Statistical honesty

- No candidate reaches DSR > 0.33 after accounting for 114 trials.
  These are CANDIDATE EDGES, not validated strategies.
- Parameter variants of the top ideas show near-identical results
  (RR/stop changes barely move outcomes → exits are mostly time-based;
  this is a plateau-like property, good).
- Top candidates' trade-date overlap is low (Jaccard ≤ 0.19) — potential
  portfolio diversification later.

## Notable negative result

Overnight-position extremes (>0.8/<0.2) traded WITH the crowd at the open
lose badly on NQ. If extreme overnight positioning has any information, it
is contrarian or conditional — worth one targeted follow-up, not a grid.

## Next: Phase 6

Freeze the top ~5 candidates into formal strategy definitions (registry),
run parameter-stability neighborhoods + Monte Carlo on each, then prepare
one-shot holdout evaluation definitions (to be executed once, after rules
are frozen and before any forward testing).
