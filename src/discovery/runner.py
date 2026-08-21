"""End-to-end research runner: hypothesis -> filtered events -> backtest -> report.

This is the Phase 3 acceptance path: one known strategy, reproducible.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from src.backtest.costs import CostModel
from src.backtest.engine import PathBook, run_backtest
from src.backtest.metrics import core_stats, full_report
from src.data.instruments import INSTRUMENTS
from src.data.loaders import dataset_version, load_symbol
from src.discovery.hypotheses import apply_filters, build_specs, hypothesis_id

PROCESSED = Path(__file__).resolve().parents[2] / "data" / "processed"


@dataclass
class ExperimentLog:
    experiment_id: str
    dataset_versions: dict = field(default_factory=dict)
    hypotheses_tested: int = 0
    ids: list = field(default_factory=list)

    def register(self, hyp: dict):
        self.hypotheses_tested += 1
        self.ids.append(hypothesis_id(hyp))


def load_events(symbol: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    f = pd.read_parquet(PROCESSED / f"{symbol}_events_features.parquet")
    o = pd.read_parquet(PROCESSED / f"{symbol}_events_outcomes.parquet")
    return f, o


def evaluate_hypothesis(hyp: dict, events: pd.DataFrame, pb: PathBook,
                        cost: CostModel, log: ExperimentLog | None = None,
                        slippage_override_ticks: float | None = None,
                        ) -> dict:
    if log is not None:
        log.register(hyp)
    selected = apply_filters(events, hyp["filters"],
                             obs_minute=hyp.get("obs_minute"))
    specs = build_specs(hyp, selected)
    slip = cost.slippage_points if slippage_override_ticks is None \
        else slippage_override_ticks * cost.spec.tick_size
    trades = run_backtest(pb, specs, cost_points=cost.cost_in_points(),
                          slippage_points=slip)
    # attach context columns for regime splits
    if len(trades):
        ctx_cols = [c for c in ["atr_pctile", "pd_return", "weekday"] if c in selected.columns]
        meta = selected[["trade_date"] + ctx_cols].drop_duplicates("trade_date")
        trades = trades.merge(meta, on="trade_date", how="left")
    return {
        "hypothesis": hyp,
        "hyp_id": hypothesis_id(hyp),
        "n_selected": len(selected),
        "trades": trades,
        "report": full_report(trades) if len(trades) else {"overall": {"n": 0}},
    }


def default_experiment_log(symbol: str) -> ExperimentLog:
    from src.data.loaders import RAW_DIR
    dv = {}
    for p in sorted(RAW_DIR.glob(f"*{symbol}*")):
        if not p.name.startswith("duplicate_"):
            dv[p.name] = dataset_version(p)["sha256"][:16]
    import datetime
    eid = f"{symbol}-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    return ExperimentLog(experiment_id=eid, dataset_versions=dv)
