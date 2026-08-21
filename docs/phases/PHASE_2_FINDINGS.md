# PHASE 2 FINDINGS — MARKET EVENT ENGINE

Date: 2026-08-21
Status: COMPLETE

## What was built

### Daily context (`src/features/daily_context.py`)
Per trade_date, strictly pre-open information:
- Previous-day levels: PDH, PDL, PC, PO, range, return, close-location-in-range
- ATR(14) of RTH daily bars + **yesterday's** ATR and its expanding percentile
  rank (volatility regime known before the open)
- Overnight: ONH/ONL/ON open/close, range (ATR-normalized), return, direction,
  relative volume
- Opening gap: absolute, %, ATR-normalized, direction, above-PDH/below-PDL flags

### Event tables (`src/features/event_builder.py`)
One row per (trade_date, observation_time); observation times 09:35 → 14:00 ET.
Features (causal only): price, session VWAP (cumulative from RTH open),
OR5/OR15/OR30 high/low/range/direction/breakouts, IB60, returns over
5/15/30/60m, up-bar streaks, cumulative volume, relative volume (vs same-time
prior-20-session mean), distances to PDH/PDL/PC/ONH/ONL/ON-mid/VWAP in ATR
units, on_position, weekday.

Outcomes (separate table): fwd returns 15/30/60m, return-to-12:00,
return-to-15:45, MFE/MAE over 60m and to session end, and first-touch races
(PDH-vs-PDL, ONH-vs-ONL, IBH-vs-IBL; cutoffs 12:00 and close;
+1 upper first / -1 lower first / 0 neither-or-same-bar).

## Output volumes

| Symbol | Events | Range |
|---|---|---|
| NQ | 22,207 | 2016-05-31 → 2025-12-31 |
| ES | 22,256 | 2016-05-31 → 2025-12-31 |
| GC | 22,445 | 2016-05-01 → 2025-12-31 |

Holdout (2026+) excluded at load time via `research_only=True`.

## Bugs the test suite caught (this is why tests exist)

1. **Globex day ordering**: wall-clock minute-of-day is not monotonic within a
   Globex trading day (18:00–23:59 evening bars precede midnight). Replaced
   with a session-relative minute key. Would have silently corrupted every
   searchsorted-based feature.
2. **REAL LOOK-AHEAD BUG**: opening-range features (OR30, IB) computed at an
   early observation used bars AFTER that observation (e.g., OR30 "known" at
   09:45). The automated leakage test caught it; windows are now truncated to
   available data. This validates the leakage-test design.

## Test coverage (`src/tests/test_event_engine.py`, 8 tests)

- Synthetic two-day fixture with hand-computed expectations: PDH/PDL/PC/gap ✓
- VWAP causality vs hand-computed mean of typical prices ✓
- Overnight position bounds + value ✓
- First-touch race directionality ✓
- **Leakage test**: perturbing all bars after T leaves every feature at
  observations ≤ T bit-identical, while later features and outcomes change ✓

Full suite: 15/15 passing.

## Sanity checks on real data (NQ @ 10:00)

- P(PDH touched before PDL by 12:00) = 0.453 vs PDL first = 0.315 (23% neither)
- Conditioning works as expected: gap-up days skew toward PDH-first,
  gap-down days toward PDL-first
- Mean 60-min forward return above/below VWAP differs in sign — plausible,
  NOT yet evidence of tradability (no costs, no validation)

## Notes / limitations

- Race ties (both levels touched within the same 1-minute bar) recorded as 0
  (ambiguous). At NQ tick sizes this is rare but nonzero.
- MFE/MAE currently expressed as % returns relative to entry; ATR-normalized
  variants can be derived downstream.
- VWAP uses typical price × volume (standard approximation without tick data).
