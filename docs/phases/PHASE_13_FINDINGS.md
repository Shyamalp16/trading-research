# PHASE 13 FINDINGS — PORTFOLIO LAYER (#21)

Date: 2026-08-21
Status: COMPLETE

## The combined reversion book (NQ+ES, 4 time slots, both directions)

| Metric | Value |
|---|---|
| Trades | 3,338 over 9.6y (~348/yr) |
| Total | **+776R** |
| Expectancy | +0.232 R/trade |
| Win rate | 71.2% |
| Max drawdown (trade-close granularity) | **2.0R over 9.6 years** |
| Yearly totals | +47.9R to +108.6R — positive all 10 years |

## Bootstrap Monte Carlo (one year = 348 trades, 5,000 paths)

- Annual expectancy: **+80.9R**
- Annual maxDD: median 1.0R, p95 1.6R
- Annual total: p5 +68.5R / median +80.7R / p95 +93.8R
- P(negative year): **0.0%**

## Correlation structure

- Average pairwise sleeve correlation on co-active days: **+0.91** (4 pairs
  with ≥100 shared days — the NQ-vs-ES pairs).
- 72.5% of signal days have BOTH symbols firing simultaneously.
- Plain language: ES is nearly a clone of NQ for this effect. Running both
  symbols doubles fees and doubles exposure without meaningful
  diversification. It is still rational (more capital deployed into the
  same verified edge), but do not mistake it for two independent edges.

## Sleeve notes

- The 10:00 slots dominate volume (485–493 trades each) with the best
  expectancy (+0.30…+0.35).
- All 16 sleeves positive; later slots (12:30, 13:30) thinner but positive.

## Recommended concurrent-risk limits (enforced in future live layer)

- Max concurrent positions: 2 (one per symbol; already enforced by dedup)
- Both-symbols-same-day: allowed, but count as ~1.6× single-trade risk in
  exposure accounting (empirical corr ~0.9)
- Book daily stop: 2R; book weekly stop: 5R
- Never scale size after wins; ATR-based sizing only

## Caveats

- Drawdown measured at trade-close granularity; intraday heat not included
  (earlier MAE analysis suggests it is modest for this effect).
- Bootstrap assumes iid trades; regime clustering would make real DD worse.
- The +0.91 correlation means portfolio-level "diversification" claims
  should be limited to the slot dimension, not the symbol dimension.
