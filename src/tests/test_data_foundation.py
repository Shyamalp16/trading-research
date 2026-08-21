import pandas as pd
import pytest

from src.data.loaders import load_symbol
from src.data.sessions import add_session_cols, daily_sessions


@pytest.fixture(scope="module")
def nq():
    return load_symbol("NQ")


def test_schema(nq):
    assert list(nq.columns) == ["ts", "symbol", "open", "high", "low", "close", "volume"]
    assert "UTC" in str(nq.ts.dtype)

def test_no_duplicates_or_violations(nq):
    assert nq.ts.duplicated().sum() == 0
    assert nq.ts.is_monotonic_increasing
    bad = ((nq.high < nq.low) | (nq.open > nq.high) | (nq.open < nq.low)
           | (nq.close > nq.high) | (nq.close < nq.low))
    assert bad.sum() == 0


def test_no_saturday_bars(nq):
    et = nq.ts.dt.tz_convert("America/New_York")
    assert (et.dt.dayofweek == 5).sum() == 0


def test_maintenance_break_empty(nq):
    """No NQ bars between 17:00 and 18:00 ET."""
    et = nq.ts.dt.tz_convert("America/New_York")
    minutes = et.dt.hour * 60 + et.dt.minute
    assert ((minutes >= 17 * 60) & (minutes < 18 * 60)).sum() == 0


def test_session_columns(nq):
    df = add_session_cols(nq.head(100_000))
    # evening bars (>=18:00 ET) belong to next trade date
    ev = df[df.ts_et.dt.hour >= 18]
    assert (ev.trade_date == ev.ts_et.dt.normalize() + pd.Timedelta(days=1)).all()
    day = df[(df.ts_et.dt.hour >= 0) & (df.ts_et.dt.hour < 17)]
    assert (day.trade_date == day.ts_et.dt.normalize()).all()


def test_daily_sessions_shape(nq):
    sample = add_session_cols(nq[nq.ts >= "2024-01-01"])
    s = daily_sessions(sample)
    # one row per trade date (DST must not create duplicate dates)
    assert s.index.nunique() == len(s)
    rth_days = s[s.rth_n_bars.notna()]
    assert len(rth_days) > 300
    # RTH high/low within session high/low
    assert (rth_days.rth_high <= rth_days.session_high).all()
    assert (rth_days.rth_low >= rth_days.session_low).all()
    # overnight high/low within session extremes
    on_days = s[s.on_n_bars > 0]
    assert (on_days.on_high <= on_days.session_high).all()
    assert (on_days.on_low >= on_days.session_low).all()


def test_dst_transition_days_have_single_trade_date(nq):
    """US DST 2024: Mar 10 (spring fwd), Nov 3 (fall back)."""
    sample = add_session_cols(nq[(nq.ts >= "2024-03-09") & (nq.ts <= "2024-03-12")])
    dates = sample.trade_date.dt.tz_localize(None).dt.date
    counts = dates.value_counts()
    assert (counts == 1).all()
