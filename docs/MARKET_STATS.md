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

## NQ — Discovery V1 first screen: what survived a train/test split (Aug 2026)

114 hypotheses across 9 market-structure families were screened: each had to
be profitable on 2016–2022 AND separately on 2023–2025 (test touched once).

### What looks interesting (candidate edges, NOT validated strategies)

1. **VWAP pullback continuation** (best family): buy when the morning trend
   is up, price is above VWAP but close to it (pullback), by 11:00 ET.
   Best variant: ~700 trades over 10 years (~70/yr), +0.05R expectancy in
   2023–2025, profit factor 1.4. Walk-forward across the whole family:
   n=449, E[R] +0.043R, maxDD 4.8R. 8 of 12 variants positive OOS —
   a plateau, not a spike.
2. **VWAP reclaim**: price pushes back above VWAP with momentum → long.
   Strong in 2023–2025 (+0.08R) but only ~24 trades/year; the whole-family
   walk-forward was flat, so this may be regime-dependent.
3. **Gap-down reversal**: gap down >0.3 ATR but price reclaims VWAP → long.
   Positive both periods, moderate sample.

### What died

- **Overnight-position extremes with tight stops**: catastrophic
  (E[R] −0.20R, 61R max drawdown). Extreme overnight positioning does NOT
  mean "go with the crowd" at the open on NQ.
- Failed-breakout entries: nothing after costs.
- Volatility-conditioned breakouts: flat.

### Honest caveats

- With 114 hypotheses tested, the deflated Sharpe of every single candidate
  is still below 0.33 — none is statistically significant on its own yet.
- The top ideas overlap little with each other (good for a portfolio later).
- Next steps for survivors: parameter-stability neighborhoods, Monte Carlo,
  then freeze → one-shot holdout evaluation.

---

## NQ — Survivor diagnostics: which edges survive robustness testing? (Aug 2026)

The five Discovery V1 leaders were stress-tested: parameter neighborhoods
(27 variants each: time ±30min, stop ±25%, target 1.0–2.0R), Monte Carlo,
year-by-year breakdowns, and drift comparisons.

### Scorecard

| Candidate | Neighbors profitable | E[R] range across variants | Bootstrap P(E≤0) | Verdict |
|---|---|---|---|---|
| **pdh_accept_90** | **100%** (all 27) | [+0.019, +0.036] — tight & positive | 6% | **most robust** |
| **gap_rev_dn_g0.3_30** | 83% | [−0.003, +0.043] | 16% | **passes** (lumpy years) |
| **pullback_up_90** | 67%* | [−0.006, +0.036] | **2%** — only CI excluding zero | **passes w/ notes** |
| vwap_reclaim_90 | 33% | [−0.053, +0.053] — sign flips | 6% | fails stability |
| mom_dn_m0.003_60 | 33% | [−0.026, +0.054] | 8% | fails stability |

*pullback's losing neighbors lose only trivially (worst −0.006R); it is
flat-everywhere-with-a-good-center, not a fragile spike.

### Plain language

- **Buying NQ when it accepts a break above yesterday's high with short-term
  momentum (pdh_accept_90)** is the most dependable pattern found so far:
  every reasonable variation of it makes money, just modestly
  (~+0.03R per trade, ~38 trades/year).
- **Fading gap-downs that reclaim VWAP** also survives robustness testing
  but with lumpier year-to-year results.
- **VWAP-reclaim and down-momentum entries look great at their exact
  settings but break when settings change** — classic overfitting shape.
  They are shelved, not frozen.
- Down-momentum shorting has one intriguing property: on the days it trades,
  simply being LONG loses money (−0.05R) while the short makes +0.04R —
  meaning the signal carries real directional information. Worth a targeted
  follow-up study, not live deployment.

---

## HOLDOUT VERDICT (Aug 2026) — the 2026 vault, opened once

The three surviving strategies were frozen into versioned definitions and
then evaluated ONCE on 2026 data they had never touched:

- **NQ-001 PDH Acceptance**: 38 trades, 65.8% win rate, +0.014R ✓
- **NQ-002 Gap-Down Reclaim**: 23 trades, 56.5% win rate, +0.009R ✓
- **NQ-003 VWAP Pullback**: 54 trades, 57.4% win rate, +0.011R ✓

Plain language: three independently-discovered patterns all made money on
data the research process never saw. The edges shrank from ~+0.03R
in-sample to ~+0.01R out-of-sample — normal decay, and a reminder these
are small, grind-it-out edges, not gold mines. Individually each sample is
too small for statistical certainty; the fact that all three agree in sign
is the strongest evidence we have.

---

## THE BIG ONE — Overnight-range morning reversion (Aug 2026)

Discovery V2's wide-net screen found it; raw-data verification confirmed it;
the sealed 2026 holdout validated it.

### The phenomenon

At 11:00 ET, look at where price sits inside the overnight range (ON low to
ON high). The relationship with the rest of the day is strongly MONOTONIC:

- Price at/below the overnight low (bottom decile) → NQ rallies into the
  close: **+0.37% average by 15:45, ~75% win rate**
- Price at/above the overnight high (top decile) → NQ fades into the close:
  **−0.28% average, short wins ~67%**

Plain language: when the morning selloff has pushed NQ below everything it
traded overnight, buyers step in for the rest of the day — and vice versa.
Morning extremes mean-revert into the close. This pattern is related to
documented "intraday momentum/reversal" research effects.

### Why we believe it

1. **Independent verification**: recomputed from raw bars with zero pipeline
   code — same result (+0.365%, 75.5% WR). (An initial "refutation" was our
   own checker comparing 10:00 instead of 11:00 — caught and fixed.)
2. **Positive in all 10 years** (2016–2025), including the 2022 bear market.
3. **Threshold plateau**: works from ≤5% all the way to ≤50% of range —
   no magic parameter. Edge degrades gracefully, never flips.
4. **Hold-time monotonic**: longer holds capture more (12:00 +0.09% →
   15:45 +0.37%). Not dependent on one exit trick.
5. **Replicates on ES** almost identically.
6. **Benign adverse excursion**: median MAE −0.19%; a 1×ATR stop almost
   never binds (1 in 250 historical trades).
7. **SEALED HOLDOUT 2026**: LONG side 20 trades, 95% WR, +0.24R net;
   SHORT side 23 trades, 83% WR, +0.17R net. Both passed.

### Frozen as

- **NQ-004 Morning Weakness Reversal (Long)** v1.0.0
- **NQ-005 Morning Strength Reversal (Short)** v1.0.0

Rules: signal at 11:00 ET, enter next bar open, stop 1×ATR(14d), no target,
flat by 16:00 ET. ~25 signals/side/year.

### Honest caveats

- Holdout samples are small (20–23 trades). Expect regression toward
  smaller (but likely still positive) edges forward.
- PF 446 is an artifact of a tiny losing count — do not extrapolate.
- If this anomaly is widely known/exploited, live fills and drift may be
  worse than history. Paper-forward tracking remains advisable before any
  capital (owner has elected not to forward-validate for now).

---

(Entries are appended as research proceeds — newest at the bottom.)
