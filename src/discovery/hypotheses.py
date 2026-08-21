"""Declarative hypothesis format + evaluation + candidate generation.

A hypothesis is a plain dict (YAML-serializable):

    hypothesis:
      name: or30_breakout_continuation
      family: opening_behavior
      market: NQ
      obs_minute: 30            # minutes after 09:30 ET
      direction: long           # long | short | both
      filters:                  # ALL must pass (AND)
        - [or30_broke_up, "==", 1]
        - [above_vwap, "==", 1]
        - [atr_pctile, "between", [0.2, 0.9]]
      stop:   {type: atr, mult: 1.0}     # stop_points = mult * atr_prev
      target: {type: rr, rr: 1.5}        # target_points = rr * stop_points
      time_stop_min: 240

Stop/target types:
  atr(mult) | points(x) | level(pdh/pdl/ib_high/ib_low/or30_high/or30_low,
                            buffer_atr=m)

Multiple-testing accounting: every generated candidate increments the global
hypothesis counter persisted with experiment results.
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

_OPERATORS = {
    "==": lambda s, v: s == v,
    "!=": lambda s, v: s != v,
    ">": lambda s, v: s > v,
    ">=": lambda s, v: s >= v,
    "<": lambda s, v: s < v,
    "<=": lambda s, v: s <= v,
    "between": lambda s, v: (s >= v[0]) & (s <= v[1]),
}


def apply_filters(events: pd.DataFrame, filters: list,
                  obs_minute: int | None = None) -> pd.DataFrame:
    mask = pd.Series(True, index=events.index)
    if obs_minute is not None:
        mask &= events["obs_minute"] == obs_minute
    for col, op, val in filters:
        if col not in events.columns:
            raise KeyError(f"Unknown filter column: {col}")
        mask &= _OPERATORS[op](events[col], val)
    return events[mask]


def build_specs(hyp: dict, selected: pd.DataFrame) -> pd.DataFrame:
    """Convert filtered events into backtest trade specs."""
    td = selected["trade_date"].reset_index(drop=True)
    stop_points = _resolve_size(hyp["stop"], selected).reset_index(drop=True)
    specs = pd.DataFrame({
        "trade_date": td,
        "obs_minute": int(hyp["obs_minute"]),
        "direction": hyp["direction"],
        "stop_points": stop_points,
        "target_points": np.nan,
        "time_stop_min": float(hyp.get("time_stop_min", 240)),
    })
    tgt = hyp.get("target")
    if tgt is None:
        specs["target_points"] = np.nan
    elif tgt["type"] == "rr":
        specs["target_points"] = specs["stop_points"] * tgt["rr"]
    elif tgt["type"] == "points":
        specs["target_points"] = float(tgt["x"])
    else:
        raise ValueError(f"Unsupported target type {tgt['type']}")
    return specs


def _resolve_size(cfg: dict, sel: pd.DataFrame) -> pd.Series:
    if cfg["type"] == "atr":
        return sel["atr_prev"] * cfg["mult"]
    if cfg["type"] == "points":
        return pd.Series(float(cfg["x"]), index=sel.index)
    raise ValueError(f"Unsupported stop type {cfg['type']}")


# ---------------- candidate generation ----------------

def generate_candidates(base_hyp: dict, grid: dict) -> list[dict]:
    """Expand a base hypothesis over a parameter grid.

    grid maps dotted paths inside the hypothesis to lists of values, e.g.
        {"filters.gap_atr.op_values": ...} is too clever; instead use explicit
        callables: {"filter:gap_atr": [0.25, 0.4]} replaces/creates the filter
        [gap_atr, ">", value].
    Supported grid keys:
      "obs_minute": [...]
      "direction": [...]
      "stop.mult": [...]
      "target.rr": [...]
      "filter:<col>": [...]  -> adds/replaces filter [col, ">", v]
    """
    keys = sorted(grid.keys())
    combos = list(itertools.product(*[grid[k] for k in keys]))
    out = []
    for combo in combos:
        h = _deep_copy(base_hyp)
        for k, v in zip(keys, combo):
            if k == "obs_minute":
                h["obs_minute"] = v
            elif k == "direction":
                h["direction"] = v
            elif k.startswith("stop."):
                h["stop"][k.split(".", 1)[1]] = v
            elif k.startswith("target."):
                h.setdefault("target", {})[k.split(".", 1)[1]] = v
            elif k.startswith("filter:"):
                col = k.split(":", 1)[1]
                h["filters"] = [f for f in h["filters"] if f[0] != col]
                h["filters"].append([col, ">", v])
        out.append(h)
    return out


def _deep_copy(h: dict) -> dict:
    import copy
    return copy.deepcopy(h)


def hypothesis_id(h: dict) -> str:
    """Stable id for multiple-testing accounting."""
    import hashlib
    import json
    blob = json.dumps(h, sort_keys=True, default=str)
    return hashlib.sha1(blob.encode()).hexdigest()[:12]
