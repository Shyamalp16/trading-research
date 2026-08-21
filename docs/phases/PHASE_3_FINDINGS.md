# PHASE 3 FINDINGS — RESEARCH FRAMEWORK

Date: 2026-08-21
Status: COMPLETE

## What was built

### Backtester (`src/backtest/engine.py`)
- Market entry at the open of the first bar at/after the observation time
  (realistic for a signal evaluated on completed bars).
- Stop / target / time-stop / **hard session-end flatten at 16:00 ET**
  (owner requirement: no trade carries past 16:00 ET; enforced as default).
- Conservative same-bar rule: stop checked before target.
- Gap-through stops fill at the worse of stop price / bar open.
- Slippage applied to entries and all exits.

### Cost model (`src/backtest/costs.py`)
- Commission per side + adverse slippage ticks, converted to price points.
- Standard stress tiers: 0 / +1 / +2 / +3 ticks per fill.

### Metrics (`src/backtest/metrics.py`)
- Full suite: n, win rate, avg win/loss R, payoff, expectancy R, profit
  factor, total R, max/avg drawdown (R), longest losing streak, per-trade
  Sharpe/Sortino, trades/year, exits breakdown, avg hold time.
- Stability splits: by year, weekday, volatility tercile, prior-day trend.

### Hypothesis DSL + candidate generator (`src/discovery/hypotheses.py`)
- Declarative dict/YAML hypotheses: filters (==, !=, >, >=, <, <=, between),
  obs_minute, direction, ATR/points stops, RR/points targets, time stop.
- Grid expansion with stable hypothesis IDs for multiple-testing accounting.
- Experiment log records dataset sha256 fingerprints + every hypothesis ID.

## Bugs caught during acceptance (why this phase exists)

1. **Duplicate-trade bug**: `obs_minute` was not applied during filtering —
   all observation times were simulated as 10:00 entries, producing 12,348
   "trades" from 2,466 days and absurd fake statistics (90% WR, PF 18).
   Caught by sanity-checking trade counts against day counts.
2. **Impossible breakout flag**: `price > window_high` compared against a
   range that included the current bar's own high → flag could never fire.
   Fixed by comparing against the range excluding the most recent bar.

## Acceptance run (`scripts/phase3_acceptance.py`, results/phase3_acceptance.json)

OR30 breakout continuation on NQ @ 10:00 ET, stop 1×ATR, targets {1.0, 1.5,
2.0}×R, flat by 16:00:

- n=74 over ~9.5 years (~8/yr), WR 57%, E[R] = +0.03R, PF 1.23
- Slippage stress: E[R] +0.042R (0 ticks) → +0.016R (+3 ticks)
- Positive but weak and thin — classified INTERESTING BUT UNPROVEN.
- Baseline check: unfiltered long-every-day same rules → E[R] ≈ 0.00R
  (n=2,457). Any claimed edge must beat this.
- Reproducibility: two identical runs produce byte-identical trade tables ✓

## Test status

24/24 passing (data foundation 9, event engine 8, backtest/DSL 7).

## Next: Phase 4

Chronological validation machinery: expanding-window walk-forward, sealed
holdout evaluation protocol (one-shot), parameter stability neighborhoods,
Monte Carlo trade reshuffling, deflated Sharpe / multiple-testing tracking.
