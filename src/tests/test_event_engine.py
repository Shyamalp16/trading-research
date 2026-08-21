"""Point-in-time correctness and correctness tests for the event engine.

The leakage test is the critical one: features at time T must be unchanged
when all data AFTER T is perturbed. Outcomes MUST change.
"""
import numpy as np
import pandas as pd
import pytest

from src.features.event_builder import compute_events, OBS_MINUTES


def make_bars(days, minutes, price_fn, symbol="TEST", volume=100.0):
    """Build a canonical 1m bar frame. price_fn(day, minute) -> (o,h,l,c)."""
    rows = []
    for day in days:
        for m in minutes:
            o, h, l, c = price_fn(day, m)
            ts = pd.Timestamp(f"{day} {m//60:02d}:{m%60:02d}:00",
                              tz="America/New_York").tz_convert("UTC")
            rows.append({
                "ts": ts,
                "symbol": symbol,
                "open": o, "high": h, "low": l, "close": c, "volume": volume,
            })
    return pd.DataFrame(rows)


def rth_minutes():
    return list(range(9 * 60 + 30, 16 * 60))


def eth_minutes():
    # previous evening 18:00-23:59 + morning 00:00-09:29
    return list(range(18 * 60, 24 * 60)) + list(range(0, 9 * 60 + 30))


def flat_price(p):
    def fn(day, m):
        return (p, p, p, p)
    return fn


D1, D2, D3 = "2024-01-08", "2024-01-09", "2024-01-10"  # Mon, Tue, Wed


def two_day_frame():
    """Two full sessions with deterministic prices.

    Day 1: RTH trades flat at 100 rising to 110 close.
    Day 2: overnight at 105; RTH opens 106, rises linearly to 116.
    """
    def fn(day, m):
        if day == D1:
            if m >= 18 * 60:  # Monday evening ETH: ranged overnight
                px = 104.5 + (m % 60) / 60.0
                return (px, px, px, px)
            return (100, 100, 100, 100)
        if day == D2:
            if m >= 18 * 60:  # Tuesday evening -> belongs to D3 session
                return (110, 110, 110, 110)
            if m < 9 * 60 + 30:
                px = 104.5 + (m % 60) / 60.0
                return (px, px, px, px)
            px = 106 + (m - 570) / 10.0  # 106.0 -> ~115.8
            return (px, px, px, px)
        if m < 9 * 60 + 30:
            return (110, 110, 110, 110)
        return (110, 110, 110, 110)
    days = [D1, D2, D3]
    minutes = sorted(set(eth_minutes() + rth_minutes()))
    return make_bars(days, minutes, fn)


def test_synthetic_levels_and_gap():
    df = two_day_frame()
    feats, outs = compute_events(df)

    d2 = feats[feats.obs_minute == 30].set_index("trade_date")
    assert len(d2) >= 2

    # Day2 context: PDH/PDL from day1 RTH (flat 100), PC=100
    day2 = d2.iloc[1]
    assert day2.pdh == 100 and day2.pdl == 100 and day2.pc == 100
    # gap = open(106) - pc(100) = 6
    assert day2.gap == pytest.approx(6.0)


def test_overnight_position_bounds_and_value():
    df = two_day_frame()
    feats, _ = compute_events(df)
    f = feats[(feats.obs_minute == 15)].reset_index(drop=True)
    f = f.dropna(subset=["on_position"])
    assert ((f.on_position >= 0) & (f.on_position <= 1)).all()
    # D2: overnight flat at 105 then price rises => position pinned at 1.0
    d2 = feats[(feats.obs_minute == 15)].iloc[1]
    assert d2.on_position == pytest.approx(1.0)


def test_vwap_is_causal_on_synthetic():
    """VWAP at obs T must equal mean of typical prices of bars < T."""
    df = two_day_frame()
    feats, _ = compute_events(df)
    row = feats[feats.obs_minute == 60].iloc[1]
    # bars 09:30..10:29 (60 bars), prices 106.0..115.9 step .1
    pxs = np.arange(106.0, 106.0 + 60 * 0.1, 0.1)
    expected = pxs.mean()
    assert row.vwap == pytest.approx(expected, abs=1e-6)


def test_no_leakage_features_invariant_to_future_perturbation():
    """CRITICAL: perturbing all bars AFTER an observation must not change
    any feature value for that observation."""
    rng = np.random.default_rng(42)
    base = two_day_frame()
    feats_a, outs_a = compute_events(base)

    pert = base.copy()
    # perturb everything on D2/D3 strictly after the 09:45 ET bar completes
    mask = pert.ts > pd.Timestamp(f"{D2} 09:46:00", tz="America/New_York")
    shift = rng.uniform(-20, 20, size=int(mask.sum()))
    pert.loc[mask, "close"] = pert.loc[mask, "close"] + shift
    pert.loc[mask, "high"] = pert.loc[mask, "high"] + shift + 1
    pert.loc[mask, "low"] = pert.loc[mask, "low"] + shift - 1

    feats_b, outs_b = compute_events(pert)

    a = feats_a.copy(); b = feats_b.copy()
    d2_ts = pd.Timestamp(D2, tz="America/New_York")
    early = (a.trade_date == d2_ts) & (a.obs_minute <= 15)
    late = (a.trade_date == d2_ts) & (a.obs_minute > 15)

    # FEATURES at (D2, obs <= 15) must be IDENTICAL despite future perturbation
    cols = list(a.columns)
    pd.testing.assert_frame_equal(
        a[early].sort_values("obs_minute")[cols].reset_index(drop=True),
        b[early].sort_values("obs_minute")[cols].reset_index(drop=True),
        check_dtype=False)

    # FEATURES at (D2, obs > 15) MUST change (they see the perturbed bars)
    assert not np.allclose(a.loc[late, "price"].values, b.loc[late, "price"].values)

    # OUTCOMES at (D2, obs <= 15) MUST change (forward window is perturbed)
    oe = (outs_a.trade_date == d2_ts) & (outs_a.obs_minute <= 15)
    assert not np.allclose(outs_a.loc[oe, "fwd_ret_15"].values,
                           outs_b.loc[oe, "fwd_ret_15"].values, equal_nan=True)


def test_race_outcomes_directionality():
    """If price never moves, upper level cannot be hit first when below it... 
    Construct explicit race: day opens below PDH and rallies to it before
    falling to PDL."""
    # Day1: high 110 low 90 close 95 -> PDH=110 PDL=90
    # Day2 RTH: monotonic rally 96 -> 120: PDH hit first => race +1
    def fn(day, m):
        if day == D1:
            if m >= 18 * 60:
                return (96, 96, 96, 96)
            return (100, 110, 90, 95)
        if day == D2:
            if m < 9 * 60 + 30:
                return (96, 96, 96, 96)
            px = 96 + (m - 570) * 0.05
            return (px, px, px, px)
        return (110, 110, 110, 110)
    days = [D1, D2, D3]
    minutes = sorted(set(eth_minutes() + rth_minutes()))
    df = make_bars(days, minutes, fn)
    _, outs = compute_events(df)
    d2 = outs[
        (outs.trade_date == pd.Timestamp(D2, tz="America/New_York"))
        & (outs.obs_minute == 15)
    ]
    assert d2.race_pdh_pdl_eod.iloc[0] == 1.0
