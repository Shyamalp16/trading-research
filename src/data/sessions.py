"""CME Globex session logic in US/Eastern time.

Session model used throughout the platform:
  - ETH (electronic): opens 18:00 ET on the previous calendar day,
    runs to 17:00 ET with a daily maintenance break 17:00-18:00 ET.
  - RTH (regular trading hours / US cash session): 09:30-16:00 ET for
    equity index futures.
  - A "trading day" is defined by Globex convention: it starts at the
    18:00 ET open of the previous calendar day and ends at 17:00 ET.
"""
import pandas as pd

ET = "America/New_York"


def add_session_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Add ts_et, trade_date (Globex trading date), and session flags."""
    out = df.copy()
    ts_et = out["ts"].dt.tz_convert(ET)
    out["ts_et"] = ts_et

    # Globex trading day: bars from 18:00 belong to the NEXT calendar day.
    d = ts_et.dt.normalize()
    is_evening = ts_et.dt.hour >= 18
    out["trade_date"] = d + pd.to_timedelta(is_evening.astype(int), unit="D")

    hour = ts_et.dt.hour + ts_et.dt.minute / 60.0
    minutes = ts_et.dt.hour * 60 + ts_et.dt.minute
    out["is_rth"] = (minutes >= 9 * 60 + 30) & (minutes < 16 * 60)
    # Overnight = ETH portion of the trading day before RTH opens
    out["is_overnight"] = ~out["is_rth"]
    out["minutes_from_rth_open"] = minutes - (9 * 60 + 30)
    return out


def rth_mask(df: pd.DataFrame) -> pd.Series:
    return df["is_rth"]


def daily_sessions(df: pd.DataFrame) -> pd.DataFrame:
    """One row per Globex trading day with OHLCV aggregates and session stats."""
    g = df.groupby("trade_date")
    sessions = g.agg(
        session_open=("open", "first"),
        session_high=("high", "max"),
        session_low=("low", "min"),
        session_close=("close", "last"),
        volume=("volume", "sum"),
        n_bars=("close", "size"),
    )

    rth = df[df["is_rth"]]
    gr = rth.groupby("trade_date")
    rth_agg = gr.agg(
        rth_open=("open", "first"),
        rth_high=("high", "max"),
        rth_low=("low", "min"),
        rth_close=("close", "last"),
        rth_volume=("volume", "sum"),
        rth_n_bars=("close", "size"),
    )
    on = df[~df["is_rth"]]
    go = on.groupby("trade_date")
    on_agg = go.agg(
        on_high=("high", "max"),
        on_low=("low", "min"),
        on_volume=("volume", "sum"),
        on_n_bars=("close", "size"),
    )
    out = sessions.join(rth_agg).join(on_agg)

    # Overnight open/close: first/last bar before RTH open on that trade date
    pre_rth = on[on["minutes_from_rth_open"] < 0]
    gp = pre_rth.groupby("trade_date")
    pre_agg = gp.agg(
        on_open=("open", "first"),
        on_close=("close", "last"),
    )
    out = out.join(pre_agg)
    return out
