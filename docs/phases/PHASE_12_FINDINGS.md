# PHASE 12 FINDINGS — WIDENED BOOK LOCKED + HIGH-FREQUENCY DISCOVERY

Date: 2026-08-21
Status: COMPLETE

## 1. Registry updates (locked in)

- NQ-004 v1.1.0 / NQ-005 v1.1.0 — thresholds widened to ≤20% / ≥80%
- ES-001 v1.0.0 / ES-002 v1.0.0 — same rules on ES
- Status: VALIDATED. Deliberately NOT holdout-passed: the vault was already
  consumed by the strict v1.0.0 definitions; loosened variants are highly
  correlated with them and do not get their own shot (no multiple openings).

## 2. High-frequency research

### Probe A — 15:00 MOC continuation: REJECTED
Inverting the magic-hours "danger hour" (break of the 14:00–15:00 range
after 15:00 → continuation into close): ~218 signals/yr but WR ≈ 47%,
negative expectancy on both NQ and ES. The danger hour is chaos, not
tradable momentum.

### Probe B — session-wide reversion book: VALIDATED
The overnight-range reversion effect holds at ALL FOUR observation times
(10:00, 11:00, 12:30, 13:30 ET), both directions, both symbols —
16/16 symbol×time×direction cells positive in train AND test.

**Deduplicated book performance (one position at a time per symbol,
train-only thresholds, hold-to-close exits):**

| Metric | Value |
|---|---|
| Trades | 3,338 over 9.6y (**~348/yr**) |
| Expectancy | **+0.232 ATR/trade** |
| Win rate | 71.2% |
| Test-only (2023–25) | n=1,039, +0.227 ATR, 69.4% WR |
| Yearly range | +0.18 to +0.30 ATR — positive every year, both symbols |

## Context

- Frequency problem solved: 76/yr → **348/yr** with expectancy nearly
  unchanged (+0.32 → +0.23 ATR).
- Magic Hours variants remain rejected (breakeven at best after costs).
- Caveats: NQ/ES signals correlate on the same days; effect should be
  monitored forward for regime decay.

## Files

- scripts/register_widened_book.py, scripts/probe_hf_candidates.py
- configs/strategies/ (4 new versioned definitions)
