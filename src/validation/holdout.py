"""One-shot holdout vault protocol.

A frozen strategy may be evaluated on the sealed holdout EXACTLY ONCE.
Freeze -> record definition hash + timestamp -> evaluate once -> result is
permanent. Any re-evaluation attempt raises.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

RESULTS = Path(__file__).resolve().parents[2] / "results"
LEDGER = RESULTS / "holdout_evaluations.json"


def _load() -> dict:
    if LEDGER.exists():
        return json.loads(LEDGER.read_text())
    return {"evaluations": {}}


def _save(state: dict):
    RESULTS.mkdir(exist_ok=True)
    LEDGER.write_text(json.dumps(state, indent=2, default=str))


def freeze(strategy_def: dict) -> str:
    """Record the frozen definition. Returns its hash."""
    blob = json.dumps(strategy_def, sort_keys=True, default=str)
    h = hashlib.sha256(blob.encode()).hexdigest()[:16]
    state = _load()
    state.setdefault("frozen", {})
    if h not in state["frozen"]:
        state["frozen"][h] = {
            "definition": strategy_def,
            "frozen_at": datetime.now(timezone.utc).isoformat(),
        }
        _save(state)
    return h


def evaluate_once(hash_id: str, eval_fn) -> dict:
    """Run eval_fn() on the holdout ONCE for this frozen hash.

    Raises if this hash was already evaluated (no reruns until something works).
    """
    state = _load()
    if hash_id not in state.get("frozen", {}):
        raise ValueError(f"Strategy {hash_id} was never frozen — freeze it first.")
    if hash_id in state.get("evaluations", {}):
        raise RuntimeError(
            f"HOLDOUT ALREADY EVALUATED for {hash_id} at "
            f"{state['evaluations'][hash_id]['evaluated_at']}. "
            "One-shot rule: no re-evaluation.")
    result = eval_fn()
    state.setdefault("evaluations", {})[hash_id] = {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "result": result,
    }
    _save(state)
    return result
