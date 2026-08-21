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

## NQ — tracking the OR30 breakout all session long (Aug 2026)

Question from the project owner: instead of checking only at a fixed time,
what if we watch the opening range all day and take the FIRST breakout,
whenever it happens?

### What actually happens (descriptive)

- **96.5% of days see an OR30 breakout before noon**, 99.2% before 15:45.
  Plain language: waiting for the opening range to break is almost never
  selective — nearly every day breaks one side or the other.
- Breakouts happen FAST: median breakout time is just **36 minutes after the
  open** (25th–75th percentile: 30–51 minutes). So "track all session" and
  "check at 10:00" end up looking at nearly the same moments.
- Up-first happens on ~53% of days, down-first ~45% (rest ambiguous).

### Trading the first breakout (net of costs, 2016–2025)

| Variant | Trades | Win rate | Expectancy | Verdict |
|---|---|---|---|---|
| Long breakouts, ATR stop, 1.5R target | 1,280 | 55.6% | **+0.021R** | tiny edge |
| Short breakouts, same rules | 1,092 | 45.5% | +0.004R | nothing |
| Structural (stop at OR mid, target other side) | 2,444 | 30.3% | −0.017R | loses |

- The long-side number looks positive every-year-ish but is small and flips
  negative in 2016/2018/2020; statistically it is roughly 1 standard error
  from zero — **not distinguishable from luck**.
- Plain language: the famous "opening range breakout" on NQ in 2016–2025 was
  essentially free of edge after realistic costs. The long side drifts
  slightly positive (consistent with NQ's general upward bias), the short
  side earns nothing, and the wide-stop structural version loses.

---

## NQ — OR30 breakout with fixed-point exits: TP 30 pts, stops 30 vs 50 (Aug 2026)

Owner request: same all-session OR30 breakout, but exit at a fixed
+30 points target, testing a 30-point stop vs a 50-point stop.

| Setup | Trades | Win rate | Expectancy | Verdict |
|---|---|---|---|---|
| Stop 30 / TP 30 (1:1) | 2,447 | 48.6% | **−0.037R** | loses |
| Stop 50 / TP 30 (needs 62.5% WR) | 2,447 | 58.3% | **−0.014R** | loses |

- The 50-pt stop does its job mechanically: win rate rises from 49% to 58%
  because fewer trades get stopped before the +30 target. But 58% < the
  62.5% break-even for a 30/50 payoff, so it still loses.
- Plain language: widening the stop "fixes" the win rate but not the math —
  you're risking 1.67 to make 1.0, and NQ's opening-range breakouts simply
  don't pay enough per attempt to cover it.
- Slippage makes both worse (e.g., 1:1 setup drops from −0.037R to −0.072R
  at half-a-point slippage per fill).
- Combined with earlier probes: three different exit logics on OR30
  breakouts (ATR-based, structural, fixed-point) all fail after costs on
  2016–2025 NQ. This family is now considered thoroughly tested and dead
  unless combined with genuinely new conditioning.

---

(Entries are appended as research proceeds — newest at the bottom.)
