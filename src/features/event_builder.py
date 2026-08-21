"""Market Event Engine.

Builds one row per (trade_date, observation_time) with:
  - FEATURES: strictly causal, computed from completed bars only
    (bars with start time < observation time).
  - OUTCOMES: what happened AFTER the observation time (separate columns,
    separate table, never mixed into features).

Observation times are ET minutes after the 09:30 RTH open.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.loaders import load_symbol
from src.data.sessions import add_session_cols, daily_sessions, ET
from src.features.daily_context import build_daily_context

OBS_MINUTES = [5, 15, 30, 45, 60, 90, 150, 210, 270]  # minutes after 09:30
OBS_LABELS = [f"{9 + (30 + m) // 60:02d}:{(30 + m) % 60:02d}" for m in OBS_MINUTES]

# Session-relative minute key: minutes since the 18:00 ET Globex open.
# Monotonic within a Globex trading day (wall-clock minute-of-day is NOT:
# the 18:00-23:59 evening bars precede the 00:00-09:29 overnight bars).
RTH_OPEN_K = (9 * 60 + 30 + 360) % 1440    # 930
NOON_K = (12 * 60 + 360) % 1440            # 1080
CUT_1545_K = (15 * 60 + 45 + 360) % 1440   # 1305
RTH_END_K = (16 * 60 + 360) % 1440         # 1320


def _smod(ts_et: pd.Series) -> pd.Series:
    mod = ts_et.dt.hour * 60 + ts_et.dt.minute
    return (mod + 360) % 1440


RTH_OPEN = 9 * 60 + 30
RTH_CLOSE = 16 * 60


def _td_ns(s: pd.Series) -> pd.Series:
    """tz-aware datetime series -> int64 nanoseconds since epoch (stable key)."""
    return s.astype("datetime64[ns, America/New_York]").astype("int64")


def _rth_bars(df: pd.DataFrame) -> pd.DataFrame:
    r = df[df["is_rth"]].copy()
    r["smod"] = _smod(r["ts_et"])
    return r.sort_values(["trade_date", "ts"]).reset_index(drop=True)


def build_events(symbol: str, research_only: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (features_df, outcomes_df), both keyed by (trade_date, obs_minute)."""
    df = load_symbol(symbol, research_only=research_only)
    return compute_events(df)


def compute_events(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Core event computation on a canonical bar frame (with session cols added)."""
    df = add_session_cols(df)
    ctx = build_daily_context(df)

    r = _rth_bars(df)
    day_keys = _td_ns(r["trade_date"]).values  # sortable ints
    mod = r["smod"].values
    o = r["open"].values
    h = r["high"].values
    l = r["low"].values
    c = r["close"].values
    v = r["volume"].values
    tpv = ((h + l + c) / 3.0) * v

    # day boundaries in the sorted array
    day_starts = np.searchsorted(day_keys, np.unique(day_keys), side="left")
    day_ends = np.searchsorted(day_keys, np.unique(day_keys), side="right")
    unique_days = np.unique(day_keys)

    # cumvol-at-obs matrix for relative volume (days x obs)
    cumvol_matrix = np.full((len(unique_days), len(OBS_MINUTES)), np.nan)

    feat_rows = []
    out_rows = []

    for i in range(len(unique_days)):
        s, e = day_starts[i], day_ends[i]
        d_mod = mod[s:e]
        # RTH bars of this day only (sorted by minute already)
        open_idx = int(np.searchsorted(d_mod, RTH_OPEN_K, side="left"))
        if e - s - open_idx < 30:
            continue  # no meaningful RTH session
        d_o, d_h, d_l, d_c, d_v = o[s:e], h[s:e], l[s:e], c[s:e], v[s:e]
        d_tpv = tpv[s:e]
        n = len(d_mod)

        cum_vol = np.cumsum(d_v)
        cum_tpv = np.cumsum(d_tpv)

        td = pd.Timestamp(unique_days[i])  # tz-aware trade_date

        for j, m in enumerate(OBS_MINUTES):
            t = RTH_OPEN_K + m
            cut = int(np.searchsorted(d_mod, t, side="left"))  # first bar >= T
            if cut <= open_idx:
                continue
            px = d_c[cut - 1]
            cumvol_matrix[i, j] = cum_vol[cut - 1]

            # ---- opening ranges (fixed windows from open, truncated to
            #      data available at the observation — no look-ahead) ----
            def or_stats(w):
                wcut = int(np.searchsorted(d_mod, RTH_OPEN_K + w, side="left"))
                wcut = min(max(wcut, open_idx + 1), cut)
                seg_h = d_h[open_idx:wcut]
                seg_l = d_l[open_idx:wcut]
                hi, lo = float(seg_h.max()), float(seg_l.min())
                rng = hi - lo
                direction = float(np.sign(d_c[wcut - 1] - d_o[open_idx]))
                broke_up = int(px > hi)
                broke_dn = int(px < lo)
                return hi, lo, rng, direction, broke_up, broke_dn

            or5 = or_stats(5)
            or15 = or_stats(15)
            or30 = or_stats(30)
            ib = or_stats(60)  # Initial Balance = first 60 min

            vwap = cum_tpv[cut - 1] / max(cum_vol[cut - 1], 1e-9)

            def ret(bars):
                k = cut - 1 - bars
                return float(px / d_c[k] - 1.0) if k >= 0 else np.nan

            last10 = d_c[max(cut - 11, 0):cut]
            upbars = int(np.sum(np.diff(last10) > 0))

            feat_rows.append({
                "trade_date": td,
                "obs_minute": m,
                "price": px,
                "vwap": vwap,
                "or5_high": or5[0], "or5_low": or5[1], "or5_range": or5[2],
                "or5_dir": or5[3], "or5_broke_up": or5[4], "or5_broke_dn": or5[5],
                "or15_high": or15[0], "or15_low": or15[1], "or15_range": or15[2],
                "or15_dir": or15[3],
                "or30_high": or30[0], "or30_low": or30[1], "or30_range": or30[2],
                "or30_dir": or30[3], "or30_broke_up": or30[4], "or30_broke_dn": or30[5],
                "ib_high": ib[0], "ib_low": ib[1], "ib_range": ib[2], "ib_dir": ib[3],
                "ret_5m": ret(5), "ret_15m": ret(15), "ret_30m": ret(30),
                "ret_60m": ret(60),
                "upbars10": upbars,
                "cum_volume": cum_vol[cut - 1],
            })

            # ---------------- OUTCOMES (future data) ----------------
            def seg_until(t_end):
                ecut = int(np.searchsorted(d_mod, t_end, side="left"))
                return cut, min(ecut, n)

            rows_out = {"trade_date": td, "obs_minute": m, "entry": px}

            for horizon, tag in [(15, "15"), (30, "30"), (60, "60")]:
                k = cut + horizon - 1
                if k < n:
                    rows_out[f"fwd_ret_{tag}"] = float(d_c[k] / px - 1.0)
                else:
                    rows_out[f"fwd_ret_{tag}"] = np.nan

            for t_end, tag in [(NOON_K, "1200"), (CUT_1545_K, "1545")]:
                a, b = seg_until(t_end)
                if t >= t_end or b <= a:
                    rows_out[f"ret_to_{tag}"] = np.nan
                else:
                    rows_out[f"ret_to_{tag}"] = float(d_c[b - 1] / px - 1.0)

            for span, tag in [(60, "60"), (RTH_END_K, "eod")]:
                a, b = seg_until(RTH_OPEN_K + span) if tag == "60" else seg_until(RTH_END_K)
                if b > a:
                    mfe = float(d_h[a:b].max() / px - 1.0)
                    mae = float(d_l[a:b].min() / px - 1.0)
                else:
                    mfe = mae = np.nan
                rows_out[f"mfe_{tag}"] = mfe
                rows_out[f"mae_{tag}"] = mae

            out_rows.append(rows_out)

    feats = pd.DataFrame(feat_rows)
    outs = pd.DataFrame(out_rows)

    # int64->Timestamp round-trip lost the tz; restore ET-wall midnight
    def _restore_td(col_frame):
        s = col_frame["trade_date"]
        s = s.dt.tz_localize("UTC").dt.tz_convert(ET).dt.normalize()
        col_frame["trade_date"] = s.astype("datetime64[us, America/New_York]")
        return col_frame

    feats = _restore_td(feats)
    outs = _restore_td(outs)

    # ---- broadcast daily context onto events ----
    # unify datetime units for the merge (parquet gives us; groupby gives ns)
    ctx_small = ctx.copy()
    ctx_small.index = ctx_small.index.astype("datetime64[us, America/New_York]")
    ctx_small = ctx_small.drop(columns=[
        "session_open", "session_high", "session_low", "session_close",
        "volume", "n_bars", "rth_open", "rth_high", "rth_low", "rth_close",
        "rth_volume", "rth_n_bars", "on_volume", "on_n_bars",
    ])
    feats = feats.merge(ctx_small, left_on="trade_date", right_index=True, how="left")

    # ---- derived causal features needing context ----
    atr = feats["atr_prev"]
    for lvl in ["pdh", "pdl", "pc", "on_high", "on_low"]:
        feats[f"d_{lvl}"] = (feats[lvl] - feats["price"]) / atr
    feats["d_on_mid"] = ((feats["on_high"] + feats["on_low"]) / 2 - feats["price"]) / atr
    feats["d_vwap"] = (feats["vwap"] - feats["price"]) / atr
    feats["above_vwap"] = (feats["price"] > feats["vwap"]).astype(int)
    on_rng = (feats["on_high"] - feats["on_low"]).replace(0, np.nan)
    feats["on_position"] = ((feats["price"] - feats["on_low"]) / on_rng).clip(0, 1)
    feats["px_vs_pdh"] = (feats["price"] > feats["pdh"]).astype(int)
    feats["px_vs_pdl"] = (feats["price"] < feats["pdl"]).astype(int)
    feats["weekday"] = feats["trade_date"].dt.weekday
    feats["rel_volume"] = feats["cum_volume"] / _rel_vol_baseline(cumvol_matrix, unique_days, feats)

    outs = _add_level_races(r, unique_days, day_starts, day_ends, feats, outs)

    return feats, outs


def _rel_vol_baseline(cumvol_matrix, unique_days, feats) -> pd.Series:
    """Mean cumulative volume at same obs time over prior 20 sessions."""
    days_int = pd.Index(unique_days)
    cm = pd.DataFrame(cumvol_matrix, index=days_int)
    base = cm.rolling(20, min_periods=10).mean().shift(1)
    key = _td_ns(feats["trade_date"])
    vals = base.reindex(key).values
    j = pd.Categorical(feats["obs_minute"], categories=OBS_MINUTES).codes
    return pd.Series(vals[np.arange(len(vals)), j], index=feats.index)


def _add_level_races(r, unique_days, day_starts, day_ends, feats, outs) -> pd.DataFrame:
    """Which level of a pair is touched first after the observation time.

    +1 = upper level first, -1 = lower level first, 0 = neither/ambiguous.
    Cutoffs: 12:00 ET and RTH close. Level values come from `feats`
    (same row order as outs by construction).
    """
    day_keys = r["trade_date"].astype("int64").values
    mod = r["smod"].values
    h = r["high"].values
    l = r["low"].values

    races = np.full((len(outs), 6), np.nan)  # 3 pairs x 2 cutoffs
    out_days = _td_ns(outs["trade_date"]).values

    pairs = [("pdh", "pdl"), ("on_high", "on_low"), ("ib_high", "ib_low")]
    lvl_arrays = {name: feats[name].values for pair in pairs for name in pair}

    for i in range(len(unique_days)):
        d = unique_days[i]
        s, e = day_starts[i], day_ends[i]
        rows = np.where(out_days == d)[0]
        if not len(rows):
            continue
        d_mod = mod[s:e]
        d_h, d_l = h[s:e], l[s:e]
        n = len(d_mod)
        for ri in rows:
            m = int(outs.at[ri, "obs_minute"])
            t = RTH_OPEN_K + m
            cut = int(np.searchsorted(d_mod, t, side="left"))
            if cut == 0:
                continue
            for k, t_end in enumerate([NOON_K, RTH_END_K]):
                ecut = min(int(np.searchsorted(d_mod, t_end, side="left")), n)
                if ecut <= cut:
                    continue
                seg_h, seg_l = d_h[cut:ecut], d_l[cut:ecut]
                for p, (up, dn) in enumerate(pairs):
                    lu = lvl_arrays[up][ri]
                    ll = lvl_arrays[dn][ri]
                    if np.isnan(lu) or np.isnan(ll):
                        continue
                    hit_up = np.where(seg_h >= lu)[0]
                    hit_dn = np.where(seg_l <= ll)[0]
                    fu = int(hit_up[0]) if len(hit_up) else 10**9
                    fd = int(hit_dn[0]) if len(hit_dn) else 10**9
                    if fu == fd == 10**9:
                        val = 0.0
                    elif fu < fd:
                        val = 1.0
                    elif fd < fu:
                        val = -1.0
                    else:
                        val = 0.0  # same bar touched both -> ambiguous
                    races[ri, p * 2 + k] = val
    for p, name in enumerate(["pdh_pdl", "onh_onl", "ibh_ibl"]):
        outs[f"race_{name}_1200"] = races[:, p * 2]
        outs[f"race_{name}_eod"] = races[:, p * 2 + 1]
    return outs
