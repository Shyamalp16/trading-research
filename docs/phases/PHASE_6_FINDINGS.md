# PHASE 6 FINDINGS — SURVIVOR DIAGNOSTICS & REGISTRY DECISIONS

Date: 2026-08-21
Status: COMPLETE (revised scope: diagnostics before any holdout decision)

## What was run (`scripts/phase6_survivor_diagnostics.py`)

For each of the 5 Discovery V1 leaders:
1. Parameter neighborhood: obs_minute ±30 × stop_mult {0.75,1,1.25} ×
   RR {1.0,1.5,2.0} = 27 variants each
2. Monte Carlo (5,000 bootstrap sequences)
3. Year-by-year + 2022-bear breakdowns
4. Drift/matched-date comparisons

Results: `results/phase6_survivor_diagnostics.json`

## Verdicts

### PASS → eligible for registry freeze

**pdh_accept_90** — "PDH acceptance continuation"
- ALL 27 neighborhood variants profitable, E[R] range [+0.019, +0.036]
- MC P(total<0)=0.06; maxDD p95 = 9.2R
- Weaknesses: negative in 2022 (−0.053) and 2025 (−0.051); modest edge

**gap_rev_dn_g0.3_30** — "gap-down VWAP reclaim reversal"
- 83% of neighbors profitable
- MC P(total<0)=0.16; lumpy years (2016 −0.34 on n=8, 2020 −0.14)
- Higher variance than pdh_accept but genuine plateau

**pullback_up_90** — "trend pullback to VWAP"
- Only candidate whose bootstrap CI95 excludes zero ([+0.001, +0.057],
  P(E≤0)=0.02); worst neighbor is trivially negative (−0.006R)
- Positive in 9/10 years (2019 −0.029); 2022 bear year positive (+0.015)

### FAIL → shelved

- **vwap_reclaim_90**: neighbors flip sign (range [−0.053, +0.053]) —
  overfitting shape despite great headline numbers
- **mom_dn_m0.003_60**: same instability; BUT matched-date comparison shows
  real directional information (long loses −0.048R on its signal days while
  the short earns +0.036R). Flagged for targeted follow-up research.

## Methodology notes / bugs

- The scripted "drift baseline" was mis-specified for long-only candidates
  (it reproduced the same trades → edge shown as exactly 0). Correct
  interpretation: vs the all-days unconditional-long baseline (~0.00R), the
  long candidates' conditional edges equal roughly their full-sample E[R]
  (+0.03…+0.04R). Baseline module to be fixed in the registry phase.

## Decision

Proceed to registry freeze with the three PASS candidates as v1.0.0
definitions. HOLDOUT NOT YET OPENED — one-shot evaluation will be executed
only after registry definitions are finalized and hash-frozen.
