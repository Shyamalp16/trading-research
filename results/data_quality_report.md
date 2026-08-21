# DATA QUALITY REPORT

Generated: 2026-08-21T05:51:08.205120+00:00

Scope: raw 1-minute continuous-contract bars. No repairs applied.

## NQ

- Rows: 3,564,244
- Range (UTC): 2016-05-29 22:01:00+00:00 -> 2026-08-20 16:58:00+00:00
- Duplicate timestamps: 0
- Monotonic timestamps: True
- OHLC violations: 0
- Non-positive prices: 0
- Zero-volume bars: 0 (stale close+zero-vol: 0)
- Missing minutes vs calendar grid: 1,813,854 (33.73%) — expected due to maintenance break/weekends/holidays
- Gaps > 60 min: 2694
- Saturday bars: 0 (0 expected)
- Sunday bars: 186053 (Sunday evening Globex open is legitimate)
- Trading days: 3182
- Short sessions (<300 bars): 17 days (holidays / half days — see JSON)
- Missing minutes by year: {2016: 121231, 2017: 183981, 2018: 176503, 2019: 175787, 2020: 181693, 2021: 173356, 2022: 173987, 2023: 172205, 2024: 172026, 2025: 174551, 2026: 108534}

## ES

- Rows: 3,588,200
- Range (UTC): 2016-05-29 22:01:00+00:00 -> 2026-08-21 04:58:00+00:00
- Duplicate timestamps: 0
- Monotonic timestamps: True
- OHLC violations: 0
- Non-positive prices: 0
- Zero-volume bars: 0 (stale close+zero-vol: 0)
- Missing minutes vs calendar grid: 1,790,618 (33.29%) — expected due to maintenance break/weekends/holidays
- Gaps > 60 min: 2638
- Saturday bars: 0 (0 expected)
- Sunday bars: 188059 (Sunday evening Globex open is legitimate)
- Trading days: 3186
- Short sessions (<300 bars): 7 days (holidays / half days — see JSON)
- Missing minutes by year: {2016: 108654, 2017: 180901, 2018: 176680, 2019: 176085, 2020: 176631, 2021: 172382, 2022: 171547, 2023: 172410, 2024: 172222, 2025: 174575, 2026: 108531}

## GC

- Rows: 3,487,001
- Range (UTC): 2016-05-01 22:01:00+00:00 -> 2026-08-20 16:58:00+00:00
- Duplicate timestamps: 0
- Monotonic timestamps: True
- OHLC violations: 0
- Non-positive prices: 0
- Zero-volume bars: 0 (stale close+zero-vol: 0)
- Missing minutes vs calendar grid: 1,931,417 (35.65%) — expected due to maintenance break/weekends/holidays
- Gaps > 60 min: 2684
- Saturday bars: 0 (0 expected)
- Sunday bars: 179903 (Sunday evening Globex open is legitimate)
- Trading days: 3205
- Short sessions (<300 bars): 48 days (holidays / half days — see JSON)
- Missing minutes by year: {2016: 142786, 2017: 188508, 2018: 188853, 2019: 183386, 2020: 181924, 2021: 189603, 2022: 187837, 2023: 190519, 2024: 184822, 2025: 183437, 2026: 109742}
