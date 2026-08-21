# PHASE 0 — REPOSITORY AUDIT

Date: 2026-08-21

## What existed before this project

The repository contained **only four raw data files** — no code, no git history,
no prior infrastructure.

| File | Symbol | Resolution | Range (UTC) | Rows | Status |
|---|---|---|---|---|---|
| `NQ1m-2020-26.parquet` | NQ.F (continuous) | 1-min OHLCV | 2020-01-01 → 2026-08-20 | 2,333,787 | **canonical NQ source** |
| `futures_GC.F_1m.parquet` | GC.F (continuous) | 1-min OHLCV | 2020-01-21 → 2026-08-20 | 2,244,564 | **canonical GC source** |
| `duplicate_NQ1m-2026.parquet` | NQ.F | 1-min | 2026 slice | 225,125 | verified byte-identical subset of canonical |
| `duplicate_NQ1m-2026.csv` | NQ.F | 1-min | 2026 slice | 225,125 | duplicate of above |

The duplicates were verified identical to the 2026 portion of the canonical file
and moved to `data/raw/duplicate_*` so they are never double-counted.

## Data quality findings (see results/data_quality_report.md)

- Schema: `ts (UTC)`, `symbol`, `open`, `high`, `low`, `close`, `volume` — clean.
- **0** duplicate timestamps, monotonic ordering, **0** OHLC violations,
  **0** non-positive prices, **0** zero-volume bars.
- Session structure matches CME Globex exactly in US/Eastern terms:
  no bars in hour 17 ET (maintenance break), Sunday open 18:00 ET,
  Friday early close, ~310 trading days/year, DST-aligned year-round
  (session boundaries stay fixed in ET across DST transitions).
- Short sessions (<300 bars): 4 days for NQ, 27 for GC → holidays/half-days.
- Missing minutes vs calendar grid (~33%) are explained by maintenance break,
  weekends and holidays. No unexplained structural holes detected so far.

## Continuous contract methodology — OPEN QUESTION

Symbols are `.F` continuous contracts. Roll/adjustment methodology is not
documented by the source. Evidence gathered:

- Large daily moves all map to real macro events (COVID Mar 2020, 2022 bear,
  Aug 2024 vol shock, Apr 2025 tariffs). No suspicious jumps at quarterly roll
  dates (2nd Thursday of Mar/Jun/Sep/Dec).
- Jan 2020 prices (~8776) match actual traded NQ levels → consistent with a
  back-adjusted series anchored to the current contract (no adjustment yet at
  the end of the series).

**Action required before research:** verify roll dates explicitly by checking
volume/price behavior around each quarterly roll. Until then, treat roll
handling as UNVERIFIED. For intraday RTH strategies this is low-risk; for
stat-arb spreads it must be confirmed.

## Gaps / missing capabilities

| Capability | Status |
|---|---|
| ES / RTY data | **MISSING** — stat-arb family (NQ/ES etc.) blocked until acquired |
| Tick / bid-ask data | MISSING — execution modeling will use conservative bar-based assumptions |
| Volume profile / bid volume | MISSING (total volume only) |
| Broker infrastructure (NinjaTrader) | Not present in repo — needed by Phase 9 |
| Prior code/backtests | None existed |

## Reusable components

None pre-existing. Everything is built fresh on Python 3.11 + pandas 3.0 +
pyarrow 24.

## Environment

- Windows, PowerShell, Python 3.11.9
- pandas 3.0.2, pyarrow 24.0.0 present; polars NOT installed (can add if perf requires)
