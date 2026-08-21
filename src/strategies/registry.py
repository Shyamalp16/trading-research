"""Strategy registry: formal versioned definitions with immutable history.

Definitions live in configs/strategies/<id>.yaml. Any modification creates
a NEW version (vX.Y.Z) — previous versions are never overwritten.
Status transitions are appended to the definition's history list.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

REGISTRY_DIR = Path(__file__).resolve().parents[2] / "configs" / "strategies"

STATUSES = [
    "IDEA", "CANDIDATE", "RESEARCHED", "VALIDATED", "HOLDOUT_PASSED",
    "PAPER_FORWARD", "LIVE_LIMITED", "LIVE_APPROVED", "RETIRED",
]


def _hash_def(defn: dict) -> str:
    blob = json.dumps(defn, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def save_definition(strategy_id: str, defn: dict) -> tuple[str, Path]:
    """Save a new version. Returns (version_hash, path)."""
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    h = _hash_def(defn)
    defn = {**defn,
            "strategy_id": strategy_id,
            "version_hash": h,
            "frozen_at": datetime.now(timezone.utc).isoformat()}
    path = REGISTRY_DIR / f"{strategy_id}_{defn['version']}_{h}.yaml"
    path.write_text(yaml.safe_dump(defn, sort_keys=False), encoding="utf-8")
    return h, path


def set_status(strategy_id: str, version: str, version_hash: str, status: str):
    assert status in STATUSES
    # append transition record alongside the file
    transitions_path = REGISTRY_DIR / "_transitions.json"
    log = json.loads(transitions_path.read_text()) if transitions_path.exists() else []
    log.append({
        "strategy_id": strategy_id, "version": version,
        "version_hash": version_hash, "status": status,
        "at": datetime.now(timezone.utc).isoformat(),
    })
    transitions_path.write_text(json.dumps(log, indent=2))


def load_all() -> list[dict]:
    return [yaml.safe_load(p.read_text(encoding="utf-8"))
            for p in sorted(REGISTRY_DIR.glob("*.yaml"))]
