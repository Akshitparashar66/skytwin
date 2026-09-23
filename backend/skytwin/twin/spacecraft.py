"""Spacecraft physics: orbit, power, battery, thermal, data storage and onboard FDIR.

This is the single physics core shared by Live Mode and the What-If engine.
"""

import copy
import math
from dataclasses import dataclass

from ..config import DEFAULT_PARAMS, SAFE_MODE_BATTERY_TEMP_C, SAFE_MODE_SOC_PCT, SpacecraftParams
from .perturbations import Modifiers, Perturbation, apply_effect, apply_impulse
from .state import NOMINAL, SAFE, Frame, TwinState

STEFAN_BOLTZMANN = 5.670374419e-8
KELVIN = 273.15
DEFAULT_DT_S = 10.0


def sun_factor(t_s: float, params: SpacecraftParams) -> float:
    """1.0 in full sunlight, 0.0 in umbra, linear ramp through penumbra. Eclipse is at the end of each orbit."""
    period = params.orbit_period_s
    phase_s = t_s % period
    eclipse_start = period * (1.0 - params.eclipse_fraction)
    half = params.penumbra_s / 2.0
    if abs(phase_s - eclipse_start) < half:
        return (eclipse_start + half - phase_s) / params.penumbra_s
    if phase_s > period - half:
        return (phase_s - (period - half)) / params.penumbra_s
    if phase_s < half:
        return (phase_s + half) / params.penumbra_s
    return 1.0 if phase_s < eclipse_start else 0.0


def open_circuit_voltage(soc: float, params: SpacecraftParams) -> float:
    span = params.battery_v_full - params.battery_v_empty
    shape = 0.85 * soc + 0.15 * (1.0 - (1.0 - soc) ** 4)
    return params.battery_v_empty + span * shape


@dataclass
class _Scheduled:
    perturbation: Perturbation
    t0_s: float
    fired: bool = False


@dataclass(frozen=True)
class _Derived:
    sun: float
    solar_w: float
    equipment_w: float
    heater_w: float
    load_w: float
    payload_on: bool
    link_up: bool
    capacity_wh: float


class Spacecraft:
    def __init__(self, state: TwinState | None = None, params: SpacecraftParams = DEFAULT_PARAMS):
        self.params = params
        self.state = state if state is not None else TwinState()
        self._scheduled: list[_Scheduled] = []

    @classmethod
    def from_snapshot(cls, snapshot: TwinState, params: SpacecraftParams = DEFAULT_PARAMS) -> "Spacecraft":
        return cls(copy.deepcopy(snapshot), params)

    @classmethod
    def settled(cls, params: SpacecraftParams = DEFAULT_PARAMS, orbits: int = 6) -> "Spacecraft":
        """A spacecraft in periodic steady state, positioned at the start of an orbit with the clock at T+0."""
        craft = cls(TwinState(), params)
        craft.advance(orbits * params.orbit_period_s)
        craft.state.t_s = 0.0
        return craft

    def snapshot(self) -> TwinState:
        return copy.deepcopy(self.state)

    def schedule(self, perturbation: Perturbation, t0_s: float | None = None) -> None:
        self._scheduled.append(_Scheduled(perturbation, self.state.t_s if t0_s is None else t0_s))

    def clear_perturbations(self) -> None:
        self._scheduled.clear()

    @property
    def perturbations(self) -> list[tuple[Perturbation, float]]:
        return [(s.perturbation, s.t0_s) for s in self._scheduled]

    def reset_mode(self) -> None:
        self.state.mode = NOMINAL
        self.state.safe_mode_reason = None

    def _modifiers(self, fire_impulses: bool) -> Modifiers:
        mods = Modifiers()
        for item in self._scheduled:
            p = item.perturbation
            elapsed = self.state.t_s - item.t0_s
            if p.spec.impulse:
                if fire_impulses and not item.fired and elapsed >= p.start_s:
                    apply_impulse(p, self.state)
                    item.fired = True
            elif p.is_active(elapsed):
                apply_effect(p, mods)
        return mods

    def _derive(self, mods: Modifiers) -> _Derived:
        p, s = self.params, self.state
        sun = sun_factor(s.t_s, p)
        payload_on = s.mode == NOMINAL and not mods.payload_forced_off
        comms = p.comms_tx_load_w if mods.link_up else p.comms_rx_load_w
        equipment = (p.bus_load_w + (p.payload_load_w if payload_on else 0.0) + comms) * mods.load_scale
        heater = p.heater_power_w if s.heater_on else 0.0
        return _Derived(
            sun=sun,
            solar_w=p.solar_array_peak_w * sun * mods.solar_scale,
            equipment_w=equipment,
            heater_w=heater,
            load_w=equipment + heater,
            payload_on=payload_on,
            link_up=mods.link_up,
            capacity_wh=p.battery_capacity_wh * mods.capacity_scale,
        )

    def _battery_power(self, d: _Derived, dt_s: float) -> float:
        """Power delivered by the battery (+ discharge, − charge), limited by what it can accept or supply."""
        p, s = self.params, self.state
        net = d.solar_w - d.load_w
        energy_wh = s.soc * d.capacity_wh
        if net >= 0:
            headroom_w = (d.capacity_wh - energy_wh) * 3600.0 / dt_s
            return -min(net * p.battery_charge_efficiency, headroom_w)
        available_w = energy_wh * 3600.0 / dt_s
        return min(-net, available_w)

    def step(self, dt_s: float = DEFAULT_DT_S) -> None:
        p, s = self.params, self.state
        mods = self._modifiers(fire_impulses=True)
        d = self._derive(mods)

        battery_w = self._battery_power(d, dt_s)
        ocv = open_circuit_voltage(s.soc, p)
        current_a = battery_w / ocv
        i2r_w = current_a**2 * p.battery_internal_resistance_ohm
        if d.capacity_wh > 0:
            s.soc = min(max(s.soc - battery_w * dt_s / 3600.0 / d.capacity_wh, 0.0), 1.0)
        else:
            s.soc = 0.0

        bus_k = s.bus_temp_c + KELVIN
        emissivity = p.radiator_emissivity * mods.emissivity_scale
        q_radiated = STEFAN_BOLTZMANN * emissivity * p.radiator_area_m2 * bus_k**4
        q_bus_in = p.absorbed_solar_w * d.sun + p.load_heat_fraction * d.equipment_w
        q_conducted = p.bus_battery_conductance_w_per_k * (s.bus_temp_c - s.battery_temp_c)
        s.bus_temp_c += (q_bus_in - q_radiated - q_conducted) * dt_s / p.bus_heat_capacity_j_per_k
        s.battery_temp_c += (q_conducted + i2r_w + d.heater_w) * dt_s / p.battery_heat_capacity_j_per_k

        if s.battery_temp_c < p.heater_on_below_c:
            s.heater_on = True
        elif s.battery_temp_c > p.heater_off_above_c:
            s.heater_on = False

        generated = p.data_generation_mb_per_min if d.payload_on else 0.0
        downlinked = p.downlink_mb_per_min if d.link_up else 0.0
        s.data_buffer_mb = min(max(s.data_buffer_mb + (generated - downlinked) * dt_s / 60.0, 0.0), p.storage_capacity_mb)

        if s.mode == NOMINAL:
            if s.soc * 100.0 < SAFE_MODE_SOC_PCT:
                s.mode, s.safe_mode_reason = SAFE, f"Battery SOC below {SAFE_MODE_SOC_PCT:g}%"
            elif s.battery_temp_c > SAFE_MODE_BATTERY_TEMP_C:
                s.mode, s.safe_mode_reason = SAFE, f"Battery above {SAFE_MODE_BATTERY_TEMP_C:g} °C"

        s.t_s += dt_s

    def advance(self, duration_s: float, dt_s: float = DEFAULT_DT_S) -> Frame:
        for _ in range(max(1, round(duration_s / dt_s))):
            self.step(dt_s)
        return self.frame()

    def run(self, duration_s: float, dt_s: float = DEFAULT_DT_S, sample_every_s: float = 60.0) -> list[Frame]:
        """Frames at T+0 and every `sample_every_s` until `duration_s`."""
        steps_per_sample = max(1, round(sample_every_s / dt_s))
        frames = [self.frame()]
        for i in range(1, round(duration_s / dt_s) + 1):
            self.step(dt_s)
            if i % steps_per_sample == 0:
                frames.append(self.frame())
        return frames

    def frame(self) -> Frame:
        p, s = self.params, self.state
        d = self._derive(self._modifiers(fire_impulses=False))
        ocv = open_circuit_voltage(s.soc, p)
        battery_w = self._battery_power(d, DEFAULT_DT_S)
        current_a = battery_w / ocv
        return Frame(
            t_s=s.t_s,
            orbit_number=int(s.t_s // p.orbit_period_s) + 1,
            orbit_phase=(s.t_s % p.orbit_period_s) / p.orbit_period_s,
            in_eclipse=d.sun < 0.5,
            solar_power_w=d.solar_w,
            load_power_w=d.load_w,
            power_margin_w=d.solar_w - d.load_w,
            battery_current_a=current_a,
            battery_voltage_v=ocv - current_a * p.battery_internal_resistance_ohm,
            soc_pct=s.soc * 100.0,
            battery_temp_c=s.battery_temp_c,
            bus_temp_c=s.bus_temp_c,
            heater_on=s.heater_on,
            data_buffer_mb=s.data_buffer_mb,
            data_buffer_pct=100.0 * s.data_buffer_mb / p.storage_capacity_mb,
            link_up=d.link_up,
            payload_on=d.payload_on,
            mode=s.mode,
            safe_mode_reason=s.safe_mode_reason,
        )


def orbit_average(values: list[float], samples_per_orbit: int) -> list[float]:
    """Mean over each complete orbit window."""
    n = len(values) // samples_per_orbit
    return [math.fsum(values[i * samples_per_orbit : (i + 1) * samples_per_orbit]) / samples_per_orbit for i in range(n)]
