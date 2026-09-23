from dataclasses import dataclass


@dataclass(frozen=True)
class SpacecraftParams:
    orbit_period_s: float = 5700.0
    eclipse_fraction: float = 0.35
    penumbra_s: float = 60.0

    solar_array_peak_w: float = 140.0
    bus_load_w: float = 40.0
    payload_load_w: float = 30.0
    comms_tx_load_w: float = 12.0
    comms_rx_load_w: float = 3.0
    heater_power_w: float = 15.0

    battery_capacity_wh: float = 150.0
    battery_charge_efficiency: float = 0.95
    battery_internal_resistance_ohm: float = 0.12
    battery_v_empty: float = 24.0
    battery_v_full: float = 33.6

    bus_heat_capacity_j_per_k: float = 15000.0
    battery_heat_capacity_j_per_k: float = 3000.0
    radiator_area_m2: float = 0.5
    radiator_emissivity: float = 0.85
    absorbed_solar_w: float = 150.0
    load_heat_fraction: float = 0.85
    bus_battery_conductance_w_per_k: float = 1.5
    heater_on_below_c: float = 5.0
    heater_off_above_c: float = 10.0

    storage_capacity_mb: float = 2048.0
    data_generation_mb_per_min: float = 1.5
    downlink_mb_per_min: float = 4.0


DEFAULT_PARAMS = SpacecraftParams()


@dataclass(frozen=True)
class Limit:
    channel: str
    label: str
    unit: str
    warn_low: float | None = None
    crit_low: float | None = None
    warn_high: float | None = None
    crit_high: float | None = None

    def severity(self, value: float) -> tuple[str, str, float] | None:
        """Return (severity, bound, limit) for the worst limit violated, or None."""
        if self.crit_low is not None and value < self.crit_low:
            return "critical", "low", self.crit_low
        if self.crit_high is not None and value > self.crit_high:
            return "critical", "high", self.crit_high
        if self.warn_low is not None and value < self.warn_low:
            return "warning", "low", self.warn_low
        if self.warn_high is not None and value > self.warn_high:
            return "warning", "high", self.warn_high
        return None


LIMITS: tuple[Limit, ...] = (
    Limit("soc_pct", "Battery SOC", "%", warn_low=40.0, crit_low=25.0),
    Limit("battery_temp_c", "Battery temperature", "°C", warn_low=2.0, crit_low=0.0, warn_high=35.0, crit_high=45.0),
    Limit("bus_temp_c", "Bus temperature", "°C", warn_low=-5.0, crit_low=-10.0, warn_high=45.0, crit_high=60.0),
    Limit("battery_voltage_v", "Battery voltage", "V", warn_low=26.5, crit_low=25.5),
    Limit("data_buffer_pct", "Data storage", "%", warn_high=75.0, crit_high=90.0),
)

LIMITS_BY_CHANNEL = {limit.channel: limit for limit in LIMITS}

SAFE_MODE_SOC_PCT = 25.0
SAFE_MODE_BATTERY_TEMP_C = 45.0
