"""Performance metric suite for R-multiple trade series."""
from __future__ import annotations

import numpy as np
import pandas as pd


def core_stats(r: np.ndarray) -> dict:
    r = r[~np.isnan(r)]
    if len(r) == 0:
        return {"n": 0}
    wins, losses = r[r > 0], r[r < 0]
    gross_win = wins.sum()
    gross_loss = -losses.sum()
    eq = np.cumsum(r)
    dd = eq - np.maximum.accumulate(eq)
    streaks = _losing_streaks(r)
    return {
        "n": int(len(r)),
        "win_rate": float((r > 0).mean()),
        "avg_win_r": float(wins.mean()) if len(wins) else 0.0,
        "avg_loss_r": float(losses.mean()) if len(losses) else 0.0,
        "payoff_ratio": float(abs(wins.mean() / losses.mean())) if len(wins) and len(losses) else np.nan,
        "expectancy_r": float(r.mean()),
        "profit_factor": float(gross_win / gross_loss) if gross_loss > 0 else np.inf if gross_win > 0 else np.nan,
        "total_r": float(r.sum()),
        "max_dd_r": float(-dd.min()) if len(dd) else 0.0,
        "avg_dd_r": float(-dd[dd < 0].mean()) if (dd < 0).any() else 0.0,
        "max_losing_streak": streaks,
        "sharpe_trade": float(r.mean() / r.std()) if r.std() > 0 else np.nan,
        "sortino_trade": float(r.mean() / r[r < 0].std()) if (r < 0).any() and r[r < 0].std() > 0 else np.nan,
        "pct_negative_months_placeholder": np.nan,
    }


def _losing_streaks(r: np.ndarray) -> int:
    mx = cur = 0
    for x in r:
        if x < 0:
            cur += 1
            mx = max(mx, cur)
        else:
            cur = 0
    return mx


def grouped_stats(trades: pd.DataFrame, by: str | list[str]) -> pd.DataFrame:
    """core_stats per group of the r_net column."""
    rows = []
    for key, g in trades.groupby(by):
        s = core_stats(g["r_net"].values)
        s["group"] = key if not isinstance(key, tuple) else str(key)
        rows.append(s)
    return pd.DataFrame(rows)


def full_report(trades: pd.DataFrame) -> dict:
    """Aggregate + stability splits. trades needs r_net, trade_date, weekday-ish cols."""
    rep = {"overall": core_stats(trades["r_net"].values)}
    td = pd.to_datetime(trades["trade_date"]).dt.tz_localize(None)
    trades = trades.assign(year=td.dt.year, month=td.dt.to_period("M").astype(str))
    if "weekday" in trades.columns:
        rep["by_weekday"] = grouped_stats(trades, "weekday").to_dict("records")
    rep["by_year"] = grouped_stats(trades, "year").to_dict("records")
    if "atr_pctile" in trades.columns:
        tercile = pd.qcut(trades["atr_pctile"], q=3, labels=["low_vol", "mid_vol", "high_vol"],
                          duplicates="drop")
        rep["by_vol_regime"] = grouped_stats(trades.assign(vol_regime=tercile), "vol_regime").to_dict("records")
    if "pd_return" in trades.columns:
        regime = np.where(trades["pd_return"] > 0.003, "up_day",
                          np.where(trades["pd_return"] < -0.003, "down_day", "flat"))
        rep["by_trend_regime"] = grouped_stats(trades.assign(trend=regime), "trend").to_dict("records")
    if "exit_reason" in trades.columns:
        rep["exit_reason_counts"] = trades["exit_reason"].value_counts().to_dict()
    if "hold_min" in trades.columns:
        rep["avg_hold_min"] = float(trades["hold_min"].mean())
    years = td.dt.year.nunique()
    rep["trades_per_year"] = float(len(trades) / years) if years else np.nan
    return rep
