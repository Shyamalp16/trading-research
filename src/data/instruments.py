from dataclasses import dataclass


@dataclass(frozen=True)
class InstrumentSpec:
    symbol: str
    name: str
    exchange: str
    tick_size: float
    tick_value: float          # USD per tick per contract
    multiplier: float          # USD per full point per contract
    rth_open: str              # ET
    rth_close: str             # ET
    eth_open: str              # ET (Globex open, previous calendar day)
    maintenance_break: tuple   # (start_et, end_et)
    micro: str | None = None

    @property
    def micro_multiplier(self) -> float | None:
        return None


INSTRUMENTS = {
    "NQ": InstrumentSpec(
        symbol="NQ", name="E-mini Nasdaq-100", exchange="CME",
        tick_size=0.25, tick_value=5.0, multiplier=20.0,
        rth_open="09:30", rth_close="16:00",
        eth_open="18:00", maintenance_break=("17:00", "18:00"),
        micro="MNQ",
    ),
    "ES": InstrumentSpec(
        symbol="ES", name="E-mini S&P 500", exchange="CME",
        tick_size=0.25, tick_value=12.5, multiplier=50.0,
        rth_open="09:30", rth_close="16:00",
        eth_open="18:00", maintenance_break=("17:00", "18:00"),
        micro="MES",
    ),
    "GC": InstrumentSpec(
        symbol="GC", name="Gold", exchange="COMEX",
        tick_size=0.10, tick_value=10.0, multiplier=100.0,
        rth_open="08:20", rth_close="13:30",
        eth_open="18:00", maintenance_break=("17:00", "18:00"),
        micro="MGC",
    ),
}

# Micro contracts (used for hedge precision in statarb research)
MICRO_INSTRUMENTS = {
    "MNQ": InstrumentSpec(
        symbol="MNQ", name="Micro E-mini Nasdaq-100", exchange="CME",
        tick_size=0.25, tick_value=0.50, multiplier=2.0,
        rth_open="09:30", rth_close="16:00",
        eth_open="18:00", maintenance_break=("17:00", "18:00"),
    ),
}
