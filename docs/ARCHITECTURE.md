# ARCHITECTURE PLAN

## Current state (post Phase 0/1 start)

Built:
- `src/data/instruments.py` — contract specs (tick size/value, multiplier, sessions)
- `src/data/loaders.py` — canonical schema loader + dataset fingerprinting (sha256)
- `src/data/sessions.py` — Globex trading-day model, RTH/overnight flags,
  daily session aggregation (DST-safe; regression-tested)
- `src/data/quality.py` — reproducible data-quality report generator
- `src/tests/test_data_foundation.py` — 7 data-integrity/DST/session tests (passing)
- `results/data_quality_report.{md,json}`

## System separation

SYSTEM A (research) and SYSTEM B (live) share only: data layer, feature
definitions, and the frozen strategy registry format.

```
data/raw  ──► loaders ──► sessions ──► features/events ──► discovery
                                        │                      │
                                        ▼                      ▼
                                   outcomes              validation pipeline
                                                               │
                                                               ▼
                                                    strategy registry (frozen YAML+hash)
                                                               │
                                              ┌────────────────┴───────────────┐
                                              ▼ SYSTEM B                       │
                                     live monitor → setup engine → risk engine │
                                     → charts → telegram → approval → execution│
```

## Storage choices

- Market bars: Parquet (as-is), processed derived sets in `data/processed/`
- Events/features/outcomes: Parquet, partitioned by year
- Registry/signals/orders/decisions/experiments: DuckDB single file (`data/trading.duckdb`)
- Configs: YAML in `configs/`

## Phase plan & status

| Phase | Deliverable | Status |
|---|---|---|
| 0 | Repository audit | DONE (docs/PHASE0_AUDIT.md) |
| 1 | Data foundation + quality report | IN PROGRESS — core done; rollover verification pending |
| 2 | Market event engine (features/outcomes, point-in-time) | NEXT |
| 3 | Research framework (hypothesis→backtest→metrics→costs) | |
| 4 | Anti-overfitting (walk-forward, holdout vault, MC, stability) | |
| 5 | Discovery V1 (~100-300 hypotheses, US open focus) | |
| 6 | Strategy registry | |
| 7 | Paper live monitor | blocked by live data feed decision |
| 8 | Telegram interface | |
| 9 | Execution adapter (NinjaTrader) | needs user infrastructure details |
| 10-12 | Forward test / prop sim / limited deployment | |

## Known blockers / decisions needed from user

1. **ES/RTY historical data** — required for the stat-arb family (NQ/ES etc.).
   Only NQ + GC currently available.
2. **Live market data source** for Phases 7+: what feed/subscription exists?
3. **NinjaTrader connection details** (ATP? external script bridge?) for Phase 9.
4. **Roll methodology of `.F` continuous contracts** — verify before stat-arb research;
   low priority for RTH directional research.
5. Final holdout boundary proposal: last 6 months of NQ data (2026-02-20 → 2026-08-20)
   sealed as VAULT. Confirm or adjust.

## Point-in-time policy (enforced in code)

- All feature functions take an explicit `asof` boundary; vectorized implementations
  must be causal-only (rolling/expanding with closed='left' semantics).
- Leakage tests: every feature module ships a shuffle/shift test proving output at T
  is unchanged by modifications to data > T.
- Outcomes computed in a separate table keyed by (trade_date, observation_time),
  never joined into feature frames during model fitting.
