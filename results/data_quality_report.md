# DATA QUALITY REPORT

Generated: 2026-08-21T05:34:51.163531+00:00

Scope: raw 1-minute continuous-contract bars. No repairs applied.

## NQ

- Rows: 2,333,787
- Range (UTC): 2020-01-01 23:00:00+00:00 -> 2026-08-20 16:58:00+00:00
- Duplicate timestamps: 0
- Monotonic timestamps: True
- OHLC violations: 0
- Non-positive prices: 0
- Zero-volume bars: 0 (stale close+zero-vol: 0)
- Missing minutes vs calendar grid: 1,154,972 (33.11%) — expected due to maintenance break/weekends/holidays
- Gaps > 60 min: 1745
- Saturday bars: 0 (0 expected)
- Sunday bars: 122179 (Sunday evening Globex open is legitimate)
- Trading days: 2064
- Short sessions (<300 bars): 4 days (holidays / half days — see JSON)
- Missing minutes by year: {2020: 180313, 2021: 173356, 2022: 173987, 2023: 172205, 2024: 172026, 2025: 174551, 2026: 108534}

## GC

- Rows: 2,244,564
- Range (UTC): 2020-01-21 00:00:00+00:00 -> 2026-08-20 16:58:00+00:00
- Duplicate timestamps: 0
- Monotonic timestamps: True
- OHLC violations: 0
- Non-positive prices: 0
- Zero-volume bars: 0 (stale close+zero-vol: 0)
- Missing minutes vs calendar grid: 1,216,775 (35.15%) — expected due to maintenance break/weekends/holidays
- Gaps > 60 min: 1724
- Saturday bars: 0 (0 expected)
- Sunday bars: 115995 (Sunday evening Globex open is legitimate)
- Trading days: 2047
- Short sessions (<300 bars): 27 days (holidays / half days — see JSON)
- Missing minutes by year: {2020: 170815, 2021: 189603, 2022: 187837, 2023: 190519, 2024: 184822, 2025: 183437, 2026: 109742}
