# PHASE 6c FINDINGS — OVERNIGHT-RANGE MORNING REVERSION (NQ-004/005)

Date: 2026-08-21
Status: COMPLETE — HOLDOUT_PASSED

## The discovery

At 11:00 ET, price position within the overnight range (on_position) is
monotonically related to the remainder of the day on NQ:

- Bottom decile (price ≤ ON low region): +0.365% mean to 15:45, 75.5% WR
- Top decile (price ≥ ON high region): −0.275% mean to 15:45

Morning extremes mean-revert into the close. Replicates on ES.

## Verification chain (each step independent)

1. Wide-net screen: 2,898 conditionings across NQ/ES/GC → this family topped
   every ranking with consistent train AND test stats.
2. Decile curve: monotonic, not a tail artifact.
3. **Independent raw-bar recomputation** (zero pipeline code): confirmed
   (+0.365%, 75.5% WR). Note: an initial refutation was itself buggy
   (10:00 vs 11:00 window mismatch) — documented in MARKET_STATS.md.
4. Year-by-year: positive all 10 years, including 2022 bear.
5. Threshold plateau: ≤5% … ≤50% of range all profitable, graceful decay.
6. Exit-time monotonicity: 12:00 (+0.09%) < 13:30 (+0.21%) < 15:45 (+0.37%).
7. MAE profile benign: median −0.19%, P(MAE<−1%)=3.4%; 1×ATR stop hit once
   in 250 historical trades.
8. Costs: ~0.75 pt round trip vs ~90–140 pt average move — negligible.
9. Monte Carlo: P(total<0)=0.00 on research period; maxDD p95 ≈ 1R.
10. **SEALED HOLDOUT (2026-01-02 → 2026-08-20), one shot:**
    - NQ-004 LONG: n=20, WR 95.0%, E[R]=+0.236R, PF 446, maxDD 0.0R
    - NQ-005 SHORT: n=23, WR 82.6%, E[R]=+0.169R, PF 24, maxDD 0.1R

## Registry

- NQ-004 v1.0.0 (hash 678c7244adb3ebfb) — HOLDOUT_PASSED
- NQ-005 v1.0.0 (hash ae69169dd18fec93) — HOLDOUT_PASSED
- Definitions: configs/strategies/, evaluations ledgered permanently.

## Honest caveats

- Holdout n is small; expect forward regression toward smaller edges.
- PF 446 is a small-sample artifact.
- Combined portfolio note: NQ-004 and NQ-005 are two sides of ONE anomaly —
  they are mutually exclusive by construction (pos can't be both ≤0.10 and
  ≥0.90) but share the same underlying mechanism. Treat as one edge with
  long/short variants for diversification accounting.
- Owner has elected to skip forward paper validation for now; if that
  changes, these are the first candidates to monitor.

## Comparison to earlier candidates

NQ-001/002/003 (+0.01R holdout edges) are superseded in importance by
NQ-004/005 (~+0.2R holdout edges). All five remain registered.
