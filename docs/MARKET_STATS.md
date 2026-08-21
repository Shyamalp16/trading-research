# MARKET STATS NOTEBOOK — Probabilities & Recurring Behaviors

Living document. Every probability/statistic observed in the data gets logged
here in plain language as research proceeds. These are OBSERVATIONS, not
tradable edges, until they survive Phase 4 validation.

Legend: "PDH" = previous day's high, "PDL" = previous day's low,
"ONH/ONL" = overnight high/low, "VWAP" = session volume-weighted average price,
"IB" = initial balance (first hour's range), "ATR" = average daily range.

---

## NQ — baseline probabilities (2016-05 → 2025-12, ~2,466 days)

### Which level gets touched first?

- Measured at 10:00 ET each day: **45.3%** of days touch PDH before PDL by
  noon, **31.5%** touch PDL first, 23.2% touch neither.
  In plain language: on a random day, the market is slightly more likely to
  visit yesterday's high than yesterday's low before lunch.
- Conditioning on the opening gap skews this exactly as market logic predicts:
  days that open above yesterday's close favor PDH-first; days that open below
  favor PDL-first. Direction of the overnight gap carries real information
  about which level gets visited first.

### VWAP as a reference

- At 10:00 ET, days trading above VWAP have a mildly better average next-hour
  return than days below it — but the difference is small and NOT yet evidence
  of tradability (no transaction costs applied yet, no out-of-sample testing).

---

## NQ — what a "long every day" baseline looks like (Aug 2026)

To judge any strategy we first measured doing NOTHING clever: buy NQ at
10:00 ET every day, exit by 16:00, stop = 1× daily ATR, target = 1.5×ATR.

- **2,457 trades, win rate 53.9%, expectancy ≈ 0.00R after costs.**
- The short mirror loses slightly (E[R] ≈ -0.01R, WR 44.9%).
- Plain language: over 2016–2025, simply being long NQ during the day earned
  essentially nothing after costs on average — the bull market happened
  overnight/over years, not reliably within the 10:00→14:00 window.
- Consequence: any intraday strategy must beat this flat baseline, and
  long-only strategies must prove they are not just riding multi-year beta.

---

## NQ — OR30 breakout continuation probe (Phase 3 acceptance run)

Rule tested: at 10:00 ET, if the latest bar pokes above the morning's
30-minute range high AND price is above VWAP AND volatility regime is normal
→ long, stop 1×ATR, target 1.5×ATR, flat by 16:00.

- Only **74 qualifying trades in ~9.5 years** (~8/year) — the strict
  "new breakout at exactly 10:00" condition is rare.
- Win rate 57%, expectancy **+0.03R**, profit factor 1.23.
- Under +3 ticks slippage per fill, expectancy falls to +0.016R — most of
  the (weak) edge evaporates.
- Verdict: **interesting but unproven**. Far too few trades, edge too small
  versus costs in this exact form. A looser "price above opening range"
  family (rather than fresh breakout) will be probed in Discovery V1.

---

(Entries are appended as research proceeds — newest at the bottom.)
