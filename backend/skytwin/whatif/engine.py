"""What-If engine: propagate scenarios on sandboxed copies of the twin.

The engine only ever receives a *snapshot* (a deep copy) of the live state and builds fresh Spacecraft
instances from it, so a simulation can never modify the live twin or command the spacecraft.
"""

import dataclasses

from ..config import DEFAULT_PARAMS, SAFE_MODE_SOC_PCT, SpacecraftParams
from ..twin.perturbations import Perturbation
from ..twin.spacecraft import DEFAULT_DT_S, Spacecraft
from ..twin.state import TwinState
from .narrative import build_narrative, build_recommendations
from .risk import analyze, risk_level

SAMPLE_EVERY_S = 60.0
MAX_HORIZON_MIN = 1440
ENSEMBLE = ((0.9, 0.95), (0.9, 1.05), (1.1, 0.95), (1.1, 1.05))
BAND_CHANNELS = ("soc_pct", "battery_temp_c", "bus_temp_c", "power_margin_w", "data_buffer_mb", "battery_current_a")
POINT_FIELDS = (
    "soc_pct", "battery_voltage_v", "battery_current_a", "battery_temp_c", "bus_temp_c", "solar_power_w",
    "load_power_w", "power_margin_w", "data_buffer_mb", "data_buffer_pct",
)  # fmt: skip
RECOVERY_TOLERANCE = {"soc_pct": 1.0, "battery_temp_c": 2.0, "bus_temp_c": 2.0, "data_buffer_mb": 1.0}

# (key, label, unit, reducer over points, flat tolerance, True if "up" is bad)
IMPACT_METRICS = (
    ("peak_discharge_a", "Battery discharge", "A", lambda ps: max(p["battery_current_a"] for p in ps), 0.05, True),
    ("max_battery_temp_c", "Battery temperature", "°C", lambda ps: max(p["battery_temp_c"] for p in ps), 0.5, True),
    ("min_soc_pct", "Battery SOC (min)", "%", lambda ps: min(p["soc_pct"] for p in ps), 0.5, False),
    ("avg_power_margin_w", "Power margin (avg)", "W", lambda ps: sum(p["power_margin_w"] for p in ps) / len(ps), 0.5, False),
    ("max_bus_temp_c", "Bus temperature", "°C", lambda ps: max(p["bus_temp_c"] for p in ps), 0.5, True),
    ("max_data_buffer_mb", "Data backlog", "MB", lambda ps: max(p["data_buffer_mb"] for p in ps), 0.5, True),
    ("payload_uptime_pct", "Payload uptime", "%", lambda ps: 100.0 * sum(p["payload_on"] for p in ps) / len(ps), 0.5, False),
)


def _run(snapshot: TwinState, perturbations: list[Perturbation], horizon_min: float, params: SpacecraftParams) -> list[dict]:
    craft = Spacecraft.from_snapshot(snapshot, params)
    for p in perturbations:
        craft.schedule(p)
    t0 = snapshot.t_s
    points = []
    for f in craft.run(horizon_min * 60.0, DEFAULT_DT_S, SAMPLE_EVERY_S):
        point = {"t_min": round((f.t_s - t0) / 60.0, 3)}
        point.update({k: round(getattr(f, k), 3) for k in POINT_FIELDS})
        point.update(
            in_eclipse=f.in_eclipse, payload_on=f.payload_on, link_up=f.link_up, heater_on=f.heater_on,
            mode=f.mode, safe_mode_reason=f.safe_mode_reason,
        )  # fmt: skip
        points.append(point)
    return points


def _band(runs: list[list[dict]]) -> list[dict]:
    band = []
    for i, point in enumerate(runs[0]):
        row = {"t_min": point["t_min"]}
        for ch in BAND_CHANNELS:
            values = [run[i][ch] for run in runs]
            row[f"{ch}_lo"] = min(values)
            row[f"{ch}_hi"] = max(values)
        band.append(row)
    return band


def _impacts(baseline: list[dict], scenario: list[dict], endurance: dict) -> list[dict]:
    impacts = []
    for key, label, unit, reduce, tolerance, up_is_bad in IMPACT_METRICS:
        b, s = reduce(baseline), reduce(scenario)
        impacts.append(_impact(key, label, unit, b, s, tolerance, up_is_bad))
    b_end, s_end = endurance["baseline_h"], endurance["scenario_h"]
    if b_end is not None or s_end is not None:
        impact = _impact("endurance_h", "Time to SOC critical", "h", b_end, s_end, 0.1, False)
        impacts.insert(3, impact)
    return impacts


def _impact(key, label, unit, b, s, tolerance, up_is_bad) -> dict:
    if b is None or s is None:
        # None means "sustainable" (never reaches critical): going from None to a value is a loss.
        direction = "flat" if b == s else ("down" if s is not None else "up")
        delta = None
    else:
        delta = s - b
        direction = "flat" if abs(delta) < tolerance else ("up" if delta > 0 else "down")
    effect = "neutral" if direction == "flat" else ("worse" if (direction == "up") == up_is_bad else "better")
    return {
        "key": key,
        "label": label,
        "unit": unit,
        "baseline": None if b is None else round(b, 3),
        "predicted": None if s is None else round(s, 3),
        "delta": None if delta is None else round(delta, 3),
        "direction": direction,
        "effect": effect,
    }


def endurance_h(points: list[dict], params: SpacecraftParams) -> tuple[float | None, str]:
    """Hours until SOC reaches the critical limit: simulated if it happens in the horizon, else extrapolated
    from the orbit-to-orbit trend of SOC minima (never earlier than the horizon end, which the simulation shows
    SOC survives). None if the trend is flat or rising (sustainable)."""
    for p in points:
        if p["soc_pct"] < SAFE_MODE_SOC_PCT:
            return p["t_min"] / 60.0, "simulated"
    per_orbit = max(1, round(params.orbit_period_s / SAMPLE_EVERY_S))
    windows = [points[i * per_orbit + 1 : (i + 1) * per_orbit + 1] for i in range((len(points) - 1) // per_orbit)]
    if len(windows) < 2:
        return None, "insufficient_horizon"
    minima = [min(w, key=lambda p: p["soc_pct"]) for w in windows]
    xs = [p["t_min"] for p in minima]
    ys = [p["soc_pct"] for p in minima]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)  # % per minute
    if slope > -0.1 / 60.0:
        return None, "sustainable"
    # Orbit windows start at the snapshot, not at eclipse boundaries, so the line through their minima can
    # cross the limit inside the horizon even though the simulated SOC never does.
    t_cross = max(xs[-1] + (ys[-1] - SAFE_MODE_SOC_PCT) / -slope, points[-1]["t_min"])
    return t_cross / 60.0, "extrapolated"


def _recovery(baseline: list[dict], scenario: list[dict], perturbations: list[Perturbation]) -> tuple[bool, float | None]:
    if not perturbations or any(p.persistent for p in perturbations):
        return False, None
    end_min = max((p.end_s if p.end_s is not None else p.start_s) / 60.0 for p in perturbations)
    recovered_at = None
    for b, s in zip(baseline, scenario):
        within = b["mode"] == s["mode"] and all(abs(b[k] - s[k]) <= tol for k, tol in RECOVERY_TOLERANCE.items())
        if not within:
            recovered_at = None
        elif recovered_at is None and s["t_min"] >= end_min:
            recovered_at = s["t_min"]
    return True, None if recovered_at is None else round(recovered_at - end_min, 1)


def simulate(
    snapshot: TwinState,
    perturbations: list[Perturbation],
    horizon_min: float = 360,
    params: SpacecraftParams = DEFAULT_PARAMS,
    label: str | None = None,
) -> dict:
    if not 10 <= horizon_min <= MAX_HORIZON_MIN:
        raise ValueError(f"horizon_min must be between 10 and {MAX_HORIZON_MIN}")

    baseline = _run(snapshot, [], horizon_min, params)
    scenario = _run(snapshot, perturbations, horizon_min, params)
    members = []
    for magnitude_factor, env_factor in ENSEMBLE:
        env = dataclasses.replace(
            params,
            solar_array_peak_w=params.solar_array_peak_w * env_factor,
            absorbed_solar_w=params.absorbed_solar_w * env_factor,
        )
        members.append(_run(snapshot, [p.scaled(magnitude_factor) for p in perturbations], horizon_min, env))

    base_end, _ = endurance_h(baseline, params)
    scen_end, basis = endurance_h(scenario, params)
    findings = analyze(baseline, scenario, members)
    recovery_applicable, recovery_min = _recovery(baseline, scenario, perturbations)
    safe = next((p for p in scenario if p["mode"] == "SAFE"), None)
    summary = {
        "endurance_h": None if scen_end is None else round(scen_end, 2),
        "endurance_basis": basis,
        "baseline_endurance_h": None if base_end is None else round(base_end, 2),
        "recovery_applicable": recovery_applicable,
        "recovery_min": recovery_min,
        "safe_mode_at_min": None if safe is None else safe["t_min"],
        "safe_mode_reason": None if safe is None else safe["safe_mode_reason"],
    }
    impacts = _impacts(baseline, scenario, {"baseline_h": base_end, "scenario_h": scen_end})

    return {
        "label": label or " + ".join(p.label() for p in perturbations) or "No change",
        "perturbations": [p.to_dict() for p in perturbations],
        "horizon_min": horizon_min,
        "start_t_min": round(snapshot.t_s / 60.0, 2),
        "baseline": baseline,
        "scenario": scenario,
        "band": _band([scenario, *members]),
        "impacts": impacts,
        "findings": findings,
        "risk_level": risk_level(findings),
        "summary": summary,
        "narrative": build_narrative(perturbations, impacts, findings, summary, horizon_min, params),
        "recommendations": build_recommendations(perturbations, impacts, findings, summary),
    }
