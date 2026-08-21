# PHASE 1 FINDINGS — DATA FOUNDATION

Date: 2026-08-21
Status: COMPLETE (rollover methodology flagged as open item, low priority for RTH research)

## Datasets accepted as canonical

| Symbol | File | Rows | Range (UTC) |
|---|---|---|---|
| NQ.F | `data/raw/NQ1m-2020-26.parquet` | 2,333,787 | 2020-01-01 → 2026-08-20 |
| ES.F | `data/raw/futures_ES.F_1m.parquet` | 1,992,152 | 2021-01-03 → 2026-08-21 |
| GC.F | `data/raw/futures_GC.F_1m.parquet` | 2,244,564 | 2020-01-21 → 2026-08-20 |

## Data quality results (all three symbols)

- **Zero** duplicate timestamps; monotonic ordering.
- **Zero** OHLC violations (high≥low, open/close within range).
- **Zero** non-positive prices, zero zero-volume bars.
- Zero Saturday bars; Sunday bars = legitimate Globex Sunday-evening open.
- Session structure matches CME Globex exactly in ET terms:
  - maintenance break 17:00–18:00 ET (no bars),
  - Friday early close, ~310 trading days/year,
  - DST-aligned year-round (session boundaries fixed in ET).
- Missing minutes (~33% of calendar grid) fully explained by maintenance
  break + weekends + holidays. No unexplained structural holes.
- Short sessions (<300 bars): NQ 4 days, GC 27 days — holidays/half days.
- All large daily moves (>3%) map to real macro events (COVID 2020,
  2022 bear market, Aug 2024 vol shock, Apr 2025 tariff shock). No anomalies.

## Bugs found and fixed during this phase

1. **DST trade-date bug** (`sessions.py`): tz-aware timestamp + `Timedelta(days=1)`
   performs absolute-time arithmetic, shifting Globex trade dates across US DST
   transitions. Fixed with naive-local date math. Regression test added.
2. **Symbol glob bug** (`loaders.py`): Windows case-insensitive glob made
   `*ES*` match `futures_GC...` ("futur**es**"), silently loading GC data for ES.
   Fixed with token-boundary regex matching. Regression test added.

Both bugs are exactly the class of silent data errors this phase exists to catch.

## Holdout vault sealed

- **Period: all of 2026 onward** (>= 2026-01-01 UTC), per owner decision.
- Enforced in code: `src/data/holdout.py` — `filter_holdout()`,
  `assert_not_holdout()`; `load_symbol(research_only=True)` strips the vault.
- Research data now ends 2025-12-31. Vault may be opened exactly once per
  frozen strategy (Phase 4+).

## Open items / risks

1. `.F` continuous-contract roll methodology undocumented by source.
   No roll artifacts detected in price series, but must be verified before
   stat-arb spread research. Low risk for RTH directional strategies.
2. RTY data unavailable → NQ/RTY and ES/RTY stat-arb pairs dropped from V1;
   NQ/ES (+ micro equivalents) remains in scope.

## Update 2026-08-21 (later same day): 2016–2020 backfill integrated

Owner provided pre-2021 files for NQ/ES/GC. Audit results:

- All three clean: 0 duplicates, 0 OHLC violations, 0 Saturday bars.
- Overlap with canonical files (NQ/GC: all of 2020) is **byte-identical**
  across every OHLCV field → same upstream source, safe merge.
- Loader now auto-merges `*_pre2021` supplements with dedupe on timestamp.
- Seam check at 2021 boundary: price continuity confirmed, no adjustment
  jumps; levels match real markets (NQ ~12,850 / ES ~3,730 on 2020-12-31).

**Merged dataset:**

| Symbol | Rows | Range (UTC) |
|---|---|---|
| NQ.F | 3,564,244 | 2016-05-29 → 2026-08-20 |
| ES.F | 3,588,200 | 2016-05-29 → 2026-08-21 |
| GC.F | 3,487,001 | 2016-05-01 → 2026-08-20 |

### Known anomalies (documented, NOT repaired)

- NQ: one stray bar at 2016-11-02 17:00 ET (inside maintenance break,
  volume=1, flat OHLC). Regression test pins it to this exact timestamp;
  session filters exclude hour 17 from RTH logic. Impact: negligible.

Research window now spans ~9.2 years pre-holdout (2016-05 → 2025-12).

## Test status

9/9 passing (`src/tests/test_data_foundation.py`):
schema, integrity, no-Saturday-bars, maintenance break, session columns,
daily session aggregation, DST single-trade-date invariant, holdout vault,
loader precision.
