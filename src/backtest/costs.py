"""Transaction cost model.

All costs expressed per contract per side unless noted.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.data.instruments import InstrumentSpec


@dataclass(frozen=True)
class CostModel:
    spec: InstrumentSpec
    commission_per_side: float = 2.50   # USD/contract/side (broker+exchange, configurable)
    slippage_ticks: float = 1.0         # adverse ticks per execution (fill vs decision price)

    @property
    def slippage_points(self) -> float:
        return self.slippage_ticks * self.spec.tick_size

    def round_trip_cost(self) -> float:
        """Total USD cost for one contract round trip (entry+exit)."""
        return 2 * self.commission_per_side + 2 * self.slippage_points * self.spec.multiplier / self.spec.multiplier

    def cost_in_points(self) -> float:
        """Round-trip cost expressed in price points of the instrument."""
        usd = 2 * self.commission_per_side
        pts = 2 * self.slippage_points
        return pts + usd / self.spec.multiplier


def stress_costs(spec: InstrumentSpec) -> dict[str, CostModel]:
    """Standard slippage stress tiers."""
    out = {}
    for t in [0.0, 1.0, 2.0, 3.0]:
        out[f"slip_{int(t)}t"] = CostModel(spec, slippage_ticks=t)
    return out
