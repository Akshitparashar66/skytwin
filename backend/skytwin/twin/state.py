from dataclasses import asdict, dataclass

NOMINAL = "NOMINAL"
SAFE = "SAFE"


@dataclass
class TwinState:
    """Integrated (memoryful) state of the spacecraft. Everything else is derived per step."""

    t_s: float = 0.0
    soc: float = 1.0
    battery_temp_c: float = 18.0
    bus_temp_c: float = 18.0
    heater_on: bool = False
    data_buffer_mb: float = 0.0
    mode: str = NOMINAL
    safe_mode_reason: str | None = None


@dataclass(frozen=True)
class Frame:
    """One telemetry frame: the state after a step plus the quantities derived during it."""

    t_s: float
    orbit_number: int
    orbit_phase: float
    in_eclipse: bool
    solar_power_w: float
    load_power_w: float
    power_margin_w: float
    battery_current_a: float
    battery_voltage_v: float
    soc_pct: float
    battery_temp_c: float
    bus_temp_c: float
    heater_on: bool
    data_buffer_mb: float
    data_buffer_pct: float
    link_up: bool
    payload_on: bool
    mode: str
    safe_mode_reason: str | None

    @property
    def t_min(self) -> float:
        return self.t_s / 60.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["t_min"] = self.t_min
        return d
