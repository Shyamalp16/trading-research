"""Build and persist market event tables for all symbols.

Usage: python -m scripts.build_events
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.features.event_builder import build_events
from src.data.loaders import dataset_version

PROCESSED = Path(__file__).resolve().parents[1] / "data" / "processed"


def main(symbols=("NQ", "ES", "GC")):
    PROCESSED.mkdir(parents=True, exist_ok=True)
    for sym in symbols:
        print(f"building {sym} ...", flush=True)
        feats, outs = build_events(sym)
        fp = PROCESSED / f"{sym}_events_features.parquet"
        op = PROCESSED / f"{sym}_events_outcomes.parquet"
        feats.to_parquet(fp)
        outs.to_parquet(op)
        print(f"  {len(feats)} events -> {fp.name}")
    print("done")


if __name__ == "__main__":
    main()
