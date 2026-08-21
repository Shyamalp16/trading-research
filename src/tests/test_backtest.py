"""Backtest engine, cost model, metrics, and hypothesis DSL tests."""
import numpy as np
import pandas as pd
import pytest

from src.backtest.engine import PathBook, simulate_trade
from src.backtest.metrics import core_stats
from src.discovery.hypotheses import apply_filters, build_specs, generate_candidates, hypothesis_id


def bars_frame(rows):
    """rows: (day, ET_minute, o, h, l, c)"""
    recs = []
    for day, m, o, h, l, c in rows:
        ts = pd.Timestamp(f"{day} {m//60:02d}:{m%60:02d}:00",
                          tz="America/New_York").tz_convert("UTC")
        recs.append({"ts": ts, "symbol": "T", "open": o, "high": h,
                     "low": l, "close": c, "volume": 100.0})
    return pd.DataFrame(recs)


D = "2024-01-09"


def test_target_hit_long():
    # entry at open of 10:00 bar (=100). risk 2 pts, target +4 pts (=104).
    # Bar rises to 105 -> target hit => +4pts / 2pts risk = +2R.
    df = bars_frame([(D, 9 * 60 + 45, 100, 100, 100, 100),
                     (D, 10 * 60, 100, 105, 99, 104),
                     (D, 10 * 60 + 1, 104, 106, 103, 105)])
    pb = PathBook(df)
    res = simulate_trade(pb, pd.Timestamp(D, tz="America/New_York"), 30,
                         "long", stop_points=2.0, target_points=4.0,
                         time_stop_min=None)
    assert res["exit_reason"] == "target"
    assert res["r_multiple_gross"] == pytest.approx(2.0)


def test_stop_first_on_same_bar_conservative():
    # one bar touches both target (104) and stop (98): must count as STOP.
    df = bars_frame([(D, 9 * 60 + 45, 100, 100, 100, 100),
                     (D, 10 * 60, 100, 105, 97, 101)])
    pb = PathBook(df)
    res = simulate_trade(pb, pd.Timestamp(D, tz="America/New_York"), 30,
                         "long", stop_points=2.0, target_points=4.0,
                         time_stop_min=None)
    assert res["exit_reason"] == "stop"
    assert res["r_multiple_gross"] == pytest.approx(-1.0)


def test_gap_through_stop_fills_worse():
    # entry at 10:00 open=100, stop=98. NEXT bar OPENS at 95 (gapped through):
    # fill must be at the open (95): -5 pts / 2 pts risk = -2.5R.
    df = bars_frame([(D, 9 * 60 + 45, 100, 100, 100, 100),
                     (D, 10 * 60, 100, 100.5, 99.5, 100),
                     (D, 10 * 60 + 1, 95, 96, 94, 95)])
    pb = PathBook(df)
    res = simulate_trade(pb, pd.Timestamp(D, tz="America/New_York"), 30,
                         "long", stop_points=2.0, target_points=4.0,
                         time_stop_min=None)
    assert res["exit_reason"] == "stop"
    assert res["r_multiple_gross"] == pytest.approx(-2.5)


def test_session_end_flatten_1600():
    """No stop/target hit: trade MUST be flat by 16:00 ET."""
    rows = [(D, 9 * 60 + 45, 100, 100, 100, 100)]
    for m in range(10 * 60, 16 * 60):
        rows.append((D, m, 100, 100.5, 99.5, 100))
    df = bars_frame(rows)
    pb = PathBook(df)
    res = simulate_trade(pb, pd.Timestamp(D, tz="America/New_York"), 30,
                         "long", stop_points=5.0, target_points=50.0,
                         time_stop_min=None)
    assert res["exit_reason"] == "session_end"
    assert res["hold_min"] <= 360


def test_time_stop():
    df = bars_frame([(D, 9 * 60 + 45, 100, 100, 100, 100)] +
                    [(D, m, 100, 100.4, 99.6, 100) for m in range(600, 700)])
    pb = PathBook(df)
    res = simulate_trade(pb, pd.Timestamp(D, tz="America/New_York"), 30,
                         "long", stop_points=5.0, target_points=50.0,
                         time_stop_min=30)
    assert res["exit_reason"] == "time"
    assert res["hold_min"] == 30


def test_short_direction_mirror():
    df = bars_frame([(D, 9 * 60 + 45, 100, 100, 100, 100),
                     (D, 10 * 60, 100, 101, 95, 96)])
    pb = PathBook(df)
    res = simulate_trade(pb, pd.Timestamp(D, tz="America/New_York"), 30,
                         "short", stop_points=2.0, target_points=4.0,
                         time_stop_min=None)
    assert res["exit_reason"] == "target"
    assert res["r_multiple_gross"] == pytest.approx(2.0)


def test_metrics_math():
    r = np.array([1.0, -1.0, 1.0, 1.0, -2.0])
    s = core_stats(r)
    assert s["n"] == 5
    assert s["win_rate"] == pytest.approx(0.6)
    assert s["expectancy_r"] == pytest.approx(0.0)
    assert s["profit_factor"] == pytest.approx(3.0 / 3.0)
    assert s["max_dd_r"] == pytest.approx(2.0)
    assert s["max_losing_streak"] == 1


def test_filter_dsl_and_specs():
    ev = pd.DataFrame({
        "or30_broke_up": [1, 0, 1],
        "above_vwap": [1, 1, 0],
        "atr_pctile": [0.5, 0.1, 0.8],
        "atr_prev": [10.0, 10.0, 20.0],
        "trade_date": pd.to_datetime(["2024-01-09"]).repeat(3),
    })
    sel = apply_filters(ev, [["or30_broke_up", "==", 1], ["above_vwap", "==", 1],
                             ["atr_pctile", "between", [0.2, 0.9]]])
    assert len(sel) == 1
    hyp = {"obs_minute": 30, "direction": "long",
           "stop": {"type": "atr", "mult": 1.0},
           "target": {"type": "rr", "rr": 1.5}, "time_stop_min": 240}
    specs = build_specs(hyp, sel)
    assert specs.stop_points.iloc[0] == pytest.approx(10.0)
    assert specs.target_points.iloc[0] == pytest.approx(15.0)


def test_candidate_grid_expansion():
    base = {"name": "x", "obs_minute": 30, "direction": "long",
            "filters": [["gap_atr", ">", 0.25]],
            "stop": {"type": "atr", "mult": 1.0},
            "target": {"type": "rr", "rr": 1.5}}
    cands = generate_candidates(base, {
        "obs_minute": [15, 30],
        "filter:gap_atr": [0.25, 0.5],
        "target.rr": [1.0, 2.0],
    })
    assert len(cands) == 8
    ids = {hypothesis_id(h) for h in cands}
    assert len(ids) == 8  # all distinct
