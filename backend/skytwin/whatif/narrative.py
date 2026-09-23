"""Plain-English explanation of a simulation result, generated from the propagation trace."""

from ..config import DEFAULT_PARAMS, SpacecraftParams
from ..twin.perturbations import Perturbation


def fmt_duration(minutes: float) -> str:
    minutes = round(minutes)
    if minutes < 60:
        return f"{minutes} min"
    h, m = divmod(minutes, 60)
    return f"{h} h" if m == 0 else f"{h} h {m} min"


def _fmt(value: float, unit: str) -> str:
    sep = "" if unit in ("%",) else " "
    return f"{value:.1f}{sep}{unit}" if abs(value) < 100 else f"{value:.0f}{sep}{unit}"


def describe_perturbation(p: Perturbation, params: SpacecraftParams = DEFAULT_PARAMS) -> str:
    when = f"from T+{fmt_duration(p.start_min)}" if p.start_min > 0 else "immediately"
    m = p.magnitude or 0.0
    if p.kind == "load_increase":
        base = params.bus_load_w + params.payload_load_w + params.comms_tx_load_w
        return f"Power consumption rises {m:g}% ({base:.0f} W → {base * (1 + m / 100):.0f} W) {when}."
    if p.kind == "solar_degradation":
        peak = params.solar_array_peak_w
        return f"Solar array output drops {m:g}% (peak {peak:.0f} W → {peak * (1 - m / 100):.0f} W) {when}."
    if p.kind == "battery_capacity_loss":
        cap = params.battery_capacity_wh
        return f"Usable battery capacity falls {m:g}% ({cap:.0f} Wh → {cap * (1 - m / 100):.0f} Wh) {when}."
    if p.kind == "thermal_spike":
        return f"Spacecraft temperature jumps +{m:g} °C {when}."
    if p.kind == "radiator_degradation":
        return f"Radiator emissivity falls {m:g}% {when}, so the spacecraft sheds heat more slowly."
    if p.kind == "comms_blackout":
        return (
            f"The ground link is lost for {fmt_duration(p.duration_min)} {when}; "
            "the transmitter idles and science data accumulates onboard."
        )
    if p.kind == "payload_off":
        return f"The payload is powered down {when}, removing {params.payload_load_w:.0f} W of load and pausing science data."
    return p.label()


_IMPACT_PHRASES = {
    "peak_discharge_a": "Peak battery discharge current",
    "max_battery_temp_c": "Peak battery temperature",
    "min_soc_pct": "Minimum battery state of charge",
    "avg_power_margin_w": "Average power margin",
    "max_bus_temp_c": "Peak bus temperature",
    "max_data_buffer_mb": "Peak onboard data backlog",
    "payload_uptime_pct": "Payload uptime",
}


def build_narrative(
    perturbations: list[Perturbation],
    impacts: list[dict],
    findings: list[dict],
    summary: dict,
    horizon_min: float,
    params: SpacecraftParams = DEFAULT_PARAMS,
) -> list[str]:
    lines = [describe_perturbation(p, params) for p in perturbations]

    for impact in impacts:
        phrase = _IMPACT_PHRASES.get(impact["key"])
        if phrase is None or impact["direction"] == "flat":
            continue
        verb = "rises" if impact["direction"] == "up" else "falls"
        lines.append(
            f"{phrase} {verb} from {_fmt(impact['baseline'], impact['unit'])} to {_fmt(impact['predicted'], impact['unit'])}."
        )

    by_key = {i["key"]: i for i in impacts}
    margin = by_key.get("avg_power_margin_w")
    if margin and margin["predicted"] < 0 <= margin["baseline"]:
        lines.append("The spacecraft becomes power-negative: the battery no longer fully recharges each orbit.")

    endurance = summary.get("endurance_h")
    if endurance is not None:
        how = "is reached" if summary.get("endurance_basis") == "simulated" else "would be reached at the current trend"
        lines.append(f"The 25% SOC critical limit {how} in about {fmt_duration(endurance * 60)}.")

    for f in findings:
        if f["confidence"] != "likely" or f["channel"] == "mode":
            continue
        pre = " (already expected without this scenario)" if f["pre_existing"] else ""
        lines.append(
            f"{f['label']} crosses the {f['severity']} limit ({_fmt(f['limit'], f['unit'])}) "
            f"at T+{fmt_duration(f['first_crossing_min'])}{pre}."
        )

    if summary.get("safe_mode_at_min") is not None:
        lines.append(
            f"Onboard FDIR switches the spacecraft to SAFE mode at T+{fmt_duration(summary['safe_mode_at_min'])} "
            f"({summary.get('safe_mode_reason')}); the payload is shut off and science stops."
        )

    if summary.get("recovery_applicable"):
        if summary.get("recovery_min") is not None:
            lines.append(
                f"The spacecraft returns to its normal trajectory {fmt_duration(summary['recovery_min'])} after the event ends."
            )
        else:
            lines.append(
                f"The spacecraft has not returned to its normal trajectory within the {fmt_duration(horizon_min)} horizon."
            )

    if not findings:
        lines.append(f"All monitored parameters stay within limits over the next {fmt_duration(horizon_min)}.")
    return lines


def build_recommendations(
    perturbations: list[Perturbation], impacts: list[dict], findings: list[dict], summary: dict
) -> list[str]:
    kinds = {p.kind for p in perturbations}
    by_key = {i["key"]: i for i in impacts}
    channels = {f["channel"] for f in findings}
    soc_safe_mode = any(f["channel"] == "mode" and "SOC" in (f.get("reason") or "") for f in findings)
    recs = []

    margin = by_key.get("avg_power_margin_w")
    power_negative = margin is not None and margin["predicted"] < 0
    if power_negative or "soc_pct" in channels or soc_safe_mode:
        if "payload_off" in kinds:
            recs.append("Even with the payload shed, power is at risk — reduce bus loads or plan a power-positive attitude.")
        else:
            recs.append("Compare against the 'payload power-down' mitigation to recover power margin.")
    if summary.get("endurance_h") is not None:
        recs.append(f"Act before T+{fmt_duration(summary['endurance_h'] * 60)}: at 25% SOC onboard FDIR enters SAFE mode.")
    if "battery_temp_c" in channels:
        recs.append(
            "Battery temperature is near its limit — pause high-power operations and avoid high charge rates until it cools."
        )
    if "bus_temp_c" in channels:
        recs.append("Bus temperature is high — consider a cold-biased attitude or powering down non-essential units.")
    backlog = by_key.get("max_data_buffer_mb")
    if backlog and backlog["predicted"] > 1.0:
        recs.append(
            f"Science data backlog peaks at {backlog['predicted']:.0f} MB — confirm the next ground-station pass can drain it."
        )
    if not recs:
        recs.append("No action needed — the spacecraft absorbs this scenario within limits.")
    return recs
