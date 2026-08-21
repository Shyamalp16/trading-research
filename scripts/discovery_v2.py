"""Discovery V2: wide-net conditional return screening.

Philosophy shift from V1: RR targets rarely get hit, so strategies are
effectively directional bets over fixed horizons. Screen THOUSANDS of
feature-conditioned cells for expected move-to-close (in ATR units),
train-only thresholds, one-shot test validation, full trial accounting.

Scope: NQ + ES + GC, obs times {10:00, 11:00, 11:30, 12:30, 13:30, 14:30},
outcome = return from observation to 15:45 ET normalized by prior-day ATR.
All positions flat by 16:00 ET per owner requirement.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.discovery.runner import load_events
from src.validation.parameter_stability import deflated_sharpe

TRAIN_END = pd.Timestamp("2023-01-01")
OBS_MINUTES = [30, 60, 90, 150, 210, 270]
QUANTILES = [0.10, 0.25, 0.75, 0.90]

FEATURES = [
    "d_pdh", "d_pdl", "d_pc", "d_on_high", "d_on_low", "d_on_mid", "d_vwap",
    "on_position", "gap_atr", "atr_pctile", "ret_5m", "ret_15m", "ret_30m",
    "ret_60m", "rel_volume", "upbars10", "ib_ratio", "or30_range",
    "pd_return", "on_range_atr",
]


def load_symbol_events(symbol: str) -> pd.DataFrame:
    from src.discovery.families import add_derived_columns
    f, o = load_events(symbol, research_only=True)
    m = add_derived_columns(f).merge(
        o[["trade_date", "obs_minute", "ret_to_1545"]],
        on=["trade_date", "obs_minute"], how="left")
    m["ret_atr"] = m["ret_to_1545"] * m["price"] / m["atr_prev"]
    m["year"] = pd.to_datetime(m["trade_date"]).dt.tz_localize(None).dt.year
    return m


def screen_symbol(symbol: str, trials_counter: list) -> pd.DataFrame:
    ev = load_symbol_events(symbol)
    ev = ev[ev.obs_minute.isin(OBS_MINUTES)]
    train = ev[pd.to_datetime(ev.trade_date).dt.tz_localize(None) < TRAIN_END]

    rows = []
    for obs in OBS_MINUTES:
        t = train[train.obs_minute == obs].dropna(
            subset=["ret_atr"] + FEATURES, how="any")
        # baseline: all days
        rows.append(_cell(symbol, obs, "ALL", None, None, t))
        trials_counter.append(1)
        for feat in FEATURES:
            qs = t[feat].quantile(QUANTILES)
            for q in QUANTILES:
                thr = qs[q]
                for side, mask in [(">", t[feat] > thr), ("<", t[feat] < thr)]:
                    sub = t[mask]
                    rows.append(_cell(symbol, obs, feat, side, float(thr), sub))
                    trials_counter.append(1)
    return pd.DataFrame(rows)


def _cell(symbol, obs, feat, side, thr, sub) -> dict:
    r = sub["ret_atr"]
    if len(r) == 0:
        return {"symbol": symbol, "obs": obs, "feature": feat, "side": side,
                "thr": thr, "n_train": 0, "er_train": np.nan,
                "wr_train": np.nan, "sr_train": np.nan}
    return {
        "symbol": symbol, "obs": obs, "feature": feat, "side": side, "thr": thr,
        "n_train": len(r),
        "er_train": float(r.mean()),
        "wr_train": float((r > 0).mean()),
        "sr_train": float(r.mean() / r.std()) if r.std() > 0 else np.nan,
    }


def validate_test(df_cells: pd.DataFrame, ev: pd.DataFrame) -> pd.DataFrame:
    test = ev[pd.to_datetime(ev.trade_date).dt.tz_localize(None) >= TRAIN_END]
    out = []
    for rec in df_cells.itertuples(index=False):
        sub = test[test.obs_minute == rec.obs]
        if rec.feature != "ALL":
            if rec.side == ">":
                sub = sub[sub[rec.feature] > rec.thr]
            elif rec.side == "<":
                sub = sub[sub[rec.feature] < rec.thr]
        sub = sub.dropna(subset=["ret_atr"])
        r = sub["ret_atr"]
        out.append({
            "n_test": len(r),
            "er_test": float(r.mean()) if len(r) else np.nan,
            "wr_test": float((r > 0).mean()) if len(r) else np.nan,
        })
    return pd.concat([df_cells.reset_index(drop=True),
                      pd.DataFrame(out)], axis=1)


def main():
    trials = []
    all_cells = []
    for sym in ["NQ", "ES", "GC"]:
        print(f"screening {sym} ...", flush=True)
        cells = screen_symbol(sym, trials)
        ev = load_symbol_events(sym)
        cells = validate_test(cells, ev)
        all_cells.append(cells)
        print(f"  {len(cells)} cells")

    df = pd.concat(all_cells, ignore_index=True)
    n_trials = len(trials)

    # pre-registered survivor gate
    df["survivor"] = (
        (df.n_train >= 250) & (df.n_test >= 80)
        & (df.er_train >= 0.05) & (df.er_test >= 0.02)
    )
    surv = df[df.survivor].sort_values("er_test", ascending=False)

    RESULTS = Path(__file__).resolve().parents[1] / "results"
    df.to_csv(RESULTS / "discovery_v2_cells.csv", index=False)

    print(f"\ntotal conditionings tested: {n_trials}")
    print(f"survivors (pre-registered gate): {len(surv)}")
    cols = ["symbol", "obs", "feature", "side", "thr", "n_train", "er_train",
            "n_test", "er_test", "wr_test"]
    print(surv[cols].head(40).to_string(index=False))

    # DSR for top survivors (per-trade SR approximated on test)
    if len(surv):
        dsrs = []
        for rec in surv.itertuples(index=False):
            sr = rec.er_test / max(rec.er_train, 1e-9) * rec.sr_train if rec.sr_train == rec.sr_train else np.nan
            dsrs.append(deflated_sharpe(rec.sr_train if rec.sr_train == rec.sr_train else 0.0,
                                        int(rec.n_test), n_trials))
        surv = surv.assign(dsr=dsrs)
        print("\ntop survivor DSRs:", np.round(surv.dsr.head(10), 3).tolist())

    meta = {"n_trials": n_trials, "n_survivors": int(len(surv)),
            "symbols": ["NQ", "ES", "GC"], "split": str(TRAIN_END)}
    (RESULTS / "discovery_v2_meta.json").write_text(json.dumps(meta, indent=2))
    print("saved -> results/discovery_v2_cells.csv")


if __name__ == "__main__":
    main()
