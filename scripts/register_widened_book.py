"""Lock in the widened reversion book: NQ+ES at <=20%/>=80% thresholds.

New versions per registry rules (never modify frozen definitions):
  NQ-004 v1.1.0, NQ-005 v1.1.0 (threshold loosened from 10% to 20%)
  ES-001 v1.0.0, ES-002 v1.0.0 (new symbols, same rules)

Status: VALIDATED only. The 2026 holdout was consumed by the strict
v1.0.0 definitions; the loosened variants are highly correlated with them
but did NOT get their own holdout shot (no second bites at the vault).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.strategies import registry


def make(symbol_prefix, sid, name, direction, op, thr):
    return {
        "name": name,
        "version": "1.1.0" if sid.startswith("NQ-00") else "1.0.0",
        "source_hypothesis": "discovery_v2 on_position extremes (widened)",
        "family": "overnight_range_reversion",
        "markets": [symbol_prefix],
        "session_window": "signal 11:00 ET, flat by 16:00 ET",
        "conditions": [
            f"on_position {op} {thr} at 11:00 ET "
            f"(price in {'bottom' if direction=='long' else 'top'} 20% of overnight range)"
        ],
        "dsl": {
            "obs_minute": 90,
            "direction": direction,
            "filters": [["on_position", op, thr]],
            "stop": {"type": "atr", "mult": 1.0},
            "target": None,
            "time_stop_min": None,
            "session_exit": "15:45-16:00 ET",
        },
        "risk": {"max_risk_per_trade_usd": 200, "max_contracts": 2},
        "flatten_by_et": "16:00",
        "holdout_note": (
            "Strict <=10%/>=90% variants passed the one-shot 2026 holdout "
            "(NQ only). Widened thresholds registered WITHOUT a holdout "
            "claim to avoid multiple vault openings."
        ),
    }


def main():
    defs = [
        ("NQ", "NQ-004", "Morning Weakness Reversal Long (widened)", "long", "<=", 0.20),
        ("NQ", "NQ-005", "Morning Strength Reversal Short (widened)", "short", ">=", 0.80),
        ("ES", "ES-001", "ES Morning Weakness Reversal Long", "long", "<=", 0.20),
        ("ES", "ES-002", "ES Morning Strength Reversal Short", "short", ">=", 0.80),
    ]
    for sym, sid, name, d, op, thr in defs:
        defn = make(sym, sid, name, d, op, thr)
        h, path = registry.save_definition(sid, defn)
        registry.set_status(sid, defn["version"], h, "VALIDATED")
        print(f"registered {sid} v{defn['version']} -> {h} ({path.name})")


if __name__ == "__main__":
    main()
