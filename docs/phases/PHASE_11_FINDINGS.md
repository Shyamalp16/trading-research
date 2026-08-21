# PHASE 11 FINDINGS — PROP SIMULATION OF NQ-004 / NQ-005

Date: 2026-08-21
Status: COMPLETE

## Setup

- Trade source: full research history of NQ-004 + NQ-005 (687 combined
  signals over 9.6y ≈ 6 trades/month across both).
- Dollar sizing: R multiples × risk-per-trade tier.
- Firm model (configurable, typical retail-prop): $50k account,
  $3,000 eval target, $2,500 trailing drawdown (trails until $2,500 profit
  buffer, then static), 5 min trading days, $150 reset + $150 activation,
  monthly payouts of everything above buffer at 90% split, consistency rule
  (best day ≤45% of period profit).
- Monte Carlo: 5,000 bootstrap journeys per configuration, seeded.

## Results (12 calendar months funded phase)

| Risk/trade | Eval pass | Net p5 | Net median | Net p75 | P(net<0) | Funded blowup |
|---|---|---|---|---|---|---|
| $200 | 100% | $367 | **$1,669** | $2,164 | 2% | 0% |
| $400 | 100% | $3,693 | **$6,076** | $7,004 | 0% | 0% |
| $600 | 100% | $6,921 | **$10,346** | $11,797 | 0% | 0% |
| $800 | 100% | $10,109 | **$14,595** | $16,575 | 0% | 0% |

Expected net per $1 of evaluation fees: $5.5 → $48.9 as sizing rises.

## Interpretation

- The edge's high win rate (83–95%) plus wide ATR stops means the trailing
  drawdown is almost never the binding constraint at these sizes — the
  strategies pass evaluation on attempt #1 in effectively every path.
- Blowup risk only appears when risk-per-trade exceeds ~30–40% of the
  trailing DD ($800+ tiers in earlier runs with forever-trailing DD showed
  this clearly; with the static-DD-after-buffer rule it stays low).
- Contract-granularity reality check: the strategies' stop is 1×ATR
  (~300–450 NQ pts). One MNQ contract ≈ $600–900 risk → the natural first
  live size is ~$700/trade, i.e., between the $600 and $800 tiers:
  **~$10–15k expected net per account-year**, near-zero simulated blowup.
- Multi-account note: copied accounts trade IDENTICAL streams — outcomes are
  perfectly correlated, so N accounts scale fees and payouts linearly; there
  is NO diversification from running multiple copies. True diversification
  requires uncorrelated edges (future research families).

## Caveats

- Sim assumes historical win rates persist exactly. Holdout evidence
  supports direction but n was small (20–23 trades).
- Drawdown tracked at trade-close granularity (mild approximation; both
  strategies hold one intraday position max).
- Fees/rules vary by firm; all parameters are configurable in
  `src/prop/simulator.py::FirmRules`.
