"""Data quality report generator.

Produces results/data_quality_report.md plus a machine-readable JSON.
Never repairs data silently: every anomaly is reported.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.data.loaders import load_symbol, RAW_DIR
from src.data.sessions import ET, add_session_cols

RESULTS = Path(__file__).resolve().parents[2] / "results"


def analyze(df: pd.DataFrame, name: str) -> dict:
    ts = df["ts"]
    full = pd.date_range(ts.min(), ts.max(), freq="1min", tz="UTC")
    missing = full.difference(ts)

    et = ts.dt.tz_convert(ET)
    d = ts.diff().dt.total_seconds() / 60.0
    daily = df.groupby(et.dt.date).agg(
        n_bars=("close", "size"),
        volume=("volume", "sum"),
    )

    ohlc_bad = int((
        (df.high < df.low)
        | (df.open > df.high) | (df.open < df.low)
        | (df.close > df.high) | (df.close < df.low)
    ).sum())

    # Zero-volume bars are normal in quiet ETH but tracked.
    zero_vol = int((df.volume == 0).sum())
    # Stale bars: close == previous close AND volume == 0
    stale = int(((df.close == df.close.shift(1)) & (df.volume == 0)).sum())

    # Short sessions (< 300 bars) => holidays / half days
    short_days = daily[daily.n_bars < 300]

    return {
        "name": name,
        "rows": len(df),
        "start_utc": str(ts.min()),
        "end_utc": str(ts.max()),
        "duplicate_timestamps": int(ts.duplicated().sum()),
        "monotonic": bool(ts.is_monotonic_increasing),
        "ohlc_violations": ohlc_bad,
        "zero_volume_bars": zero_vol,
        "stale_zero_vol_bars": stale,
        "nonpositive_prices": int((df[["open", "high", "low", "close"]] <= 0).any(axis=1).sum()),
        "expected_minutes": len(full),
        "missing_minutes": len(missing),
        "missing_pct": round(len(missing) / len(full) * 100, 2),
        "gaps_over_60min": int((d > 60).sum()),
        "weekend_bars_sat": int((et.dt.dayofweek == 5).sum()),
        "weekend_bars_sun": int((et.dt.dayofweek == 6).sum()),
        "trading_days": len(daily),
        "short_sessions_lt300bars": {str(k): int(v) for k, v in short_days.n_bars.items()},
        "missing_by_year": {int(k): int(v) for k, v in
                            pd.Series(1, index=missing).groupby(missing.year).sum().items()},
    }


def main():
    RESULTS.mkdir(exist_ok=True)
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "symbols": {}}
    lines = [
        "# DATA QUALITY REPORT",
        "",
        f"Generated: {report['generated_at']}",
        "",
        "Scope: raw 1-minute continuous-contract bars. No repairs applied.",
        "",
    ]
    for sym in ["NQ", "ES", "GC"]:
        df = load_symbol(sym)
        res = analyze(df, sym)
        report["symbols"][sym] = res
        lines += [
            f"## {sym}",
            "",
            f"- Rows: {res['rows']:,}",
            f"- Range (UTC): {res['start_utc']} -> {res['end_utc']}",
            f"- Duplicate timestamps: {res['duplicate_timestamps']}",
            f"- Monotonic timestamps: {res['monotonic']}",
            f"- OHLC violations: {res['ohlc_violations']}",
            f"- Non-positive prices: {res['nonpositive_prices']}",
            f"- Zero-volume bars: {res['zero_volume_bars']:,} "
            f"(stale close+zero-vol: {res['stale_zero_vol_bars']:,})",
            f"- Missing minutes vs calendar grid: {res['missing_minutes']:,} "
            f"({res['missing_pct']}%) — expected due to maintenance break/weekends/holidays",
            f"- Gaps > 60 min: {res['gaps_over_60min']}",
            f"- Saturday bars: {res['weekend_bars_sat']} (0 expected)",
            f"- Sunday bars: {res['weekend_bars_sun']} (Sunday evening Globex open is legitimate)",
            f"- Trading days: {res['trading_days']}",
            f"- Short sessions (<300 bars): {len(res['short_sessions_lt300bars'])} days "
            "(holidays / half days — see JSON)",
            f"- Missing minutes by year: {res['missing_by_year']}",
            "",
        ]

    md = "\n".join(lines)
    (RESULTS / "data_quality_report.md").write_text(md, encoding="utf-8")
    (RESULTS / "data_quality_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
