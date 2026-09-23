"""Live Mode: the twin tracking the spacecraft.

`truth` stands in for the real spacecraft (in a real deployment, frames would arrive from the ground
segment). Each tick the nominal twin predicts the next frame from the last known state; residuals between
measured and predicted telemetry feed the anomaly detectors, and measured values are limit-checked.
"""

import itertools
import random
from collections import deque

from ..config import DEFAULT_PARAMS, LIMITS, SpacecraftParams
from ..twin.perturbations import Perturbation
from ..twin.spacecraft import Spacecraft
from ..twin.state import TwinState
from .detector import DynamicThresholdDetector

# channel: (sensor noise sigma, label, unit)
RESIDUAL_CHANNELS = {
    "solar_power_w": (0.8, "Solar array power", "W"),
    "load_power_w": (0.5, "Load power", "W"),
    "battery_current_a": (0.02, "Battery current", "A"),
    "bus_temp_c": (0.1, "Bus temperature", "°C"),
    "battery_temp_c": (0.1, "Battery temperature", "°C"),
}
SENSOR_NOISE = {
    **{ch: sigma for ch, (sigma, _, _) in RESIDUAL_CHANNELS.items()},
    "battery_voltage_v": 0.02,
    "soc_pct": 0.1,
}


class LiveTwin:
    def __init__(
        self,
        params: SpacecraftParams = DEFAULT_PARAMS,
        tick_sim_s: float = 30.0,
        seed: int = 7,
        history_len: int = 720,
        prime_ticks: int = 60,
    ):
        self.params = params
        self.tick_sim_s = tick_sim_s
        self.truth = Spacecraft.settled(params)
        self._rng = random.Random(seed)
        self.detectors = {
            ch: DynamicThresholdDetector(alpha=0.3, window=200, z=6.0, min_std=sigma * 0.3, warmup=30, min_consecutive=2)
            for ch, (sigma, _, _) in RESIDUAL_CHANNELS.items()
        }
        self.history: deque[dict] = deque(maxlen=history_len)
        self.alerts: deque[dict] = deque(maxlen=100)
        self._alert_ids = itertools.count(1)
        self._active: set[tuple[str, str]] = set()
        self.latest: dict | None = None
        for _ in range(prime_ticks):
            self.tick()
        self.alerts.clear()

    def snapshot(self) -> TwinState:
        return self.truth.snapshot()

    @property
    def faults(self) -> list[dict]:
        return [{**p.to_dict(), "injected_at_min": round(t0 / 60.0, 2)} for p, t0 in self.truth.perturbations]

    def inject_fault(self, perturbation: Perturbation) -> None:
        self.truth.schedule(perturbation)

    def clear_faults(self) -> None:
        self.truth.clear_perturbations()
        self.truth.reset_mode()

    def tick(self) -> dict:
        predicted = Spacecraft.from_snapshot(self.truth.snapshot(), self.params).advance(self.tick_sim_s)
        true_frame = self.truth.advance(self.tick_sim_s)

        frame = true_frame.to_dict()
        for ch, sigma in SENSOR_NOISE.items():
            frame[ch] = frame[ch] + self._rng.gauss(0.0, sigma)
        frame["soc_pct"] = min(max(frame["soc_pct"], 0.0), 100.0)
        frame["solar_power_w"] = max(frame["solar_power_w"], 0.0)
        frame["power_margin_w"] = frame["solar_power_w"] - frame["load_power_w"]

        anomalies = []
        for ch, (_, label, unit) in RESIDUAL_CHANNELS.items():
            expected = getattr(predicted, ch)
            det = self.detectors[ch].update(frame[ch] - expected)
            if det.is_anomaly:
                anomalies.append(
                    {
                        "channel": ch,
                        "label": label,
                        "unit": unit,
                        "measured": frame[ch],
                        "expected": expected,
                        "residual": det.smoothed,
                        "score": det.score,
                        "threshold": det.threshold,
                    }
                )

        violations = []
        for limit in LIMITS:
            hit = limit.severity(frame[limit.channel])
            if hit:
                severity, bound, value = hit
                violations.append(
                    {
                        "channel": limit.channel,
                        "label": limit.label,
                        "unit": limit.unit,
                        "severity": severity,
                        "bound": bound,
                        "limit": value,
                        "value": frame[limit.channel],
                    }
                )

        new_alerts = self._update_alerts(frame, anomalies, violations)
        if frame["mode"] == "SAFE" or any(v["severity"] == "critical" for v in violations):
            status = "CRITICAL"
        elif violations or anomalies:
            status = "WARNING"
        else:
            status = "NOMINAL"

        payload = {
            "type": "telemetry",
            "frame": {k: round(v, 4) if isinstance(v, float) else v for k, v in frame.items()},
            "expected": {ch: round(getattr(predicted, ch), 4) for ch in RESIDUAL_CHANNELS},
            "anomalies": anomalies,
            "limit_violations": violations,
            "status": status,
            "faults": self.faults,
            "new_alerts": new_alerts,
        }
        self.history.append(payload["frame"] | {"status": status, "anomaly_count": len(anomalies)})
        self.latest = payload
        return payload

    def _update_alerts(self, frame: dict, anomalies: list[dict], violations: list[dict]) -> list[dict]:
        current: dict[tuple[str, str], tuple[str, str]] = {}
        for a in anomalies:
            current[("anomaly", a["channel"])] = (
                "warning",
                f"{a['label']} deviates from twin prediction by {a['residual']:+.2f} {a['unit']}",
            )
        for v in violations:
            current[("limit", v["channel"])] = (
                v["severity"],
                f"{v['label']} {v['value']:.1f} {v['unit']} beyond {v['severity']} limit {v['limit']:g} {v['unit']}",
            )
        if frame["mode"] == "SAFE":
            current[("mode", "mode")] = ("critical", f"Spacecraft entered SAFE mode: {frame['safe_mode_reason']}")

        new = []
        for key, (severity, message) in current.items():
            if key not in self._active:
                alert = {
                    "id": next(self._alert_ids),
                    "t_min": round(frame["t_min"], 2),
                    "kind": key[0],
                    "channel": key[1],
                    "severity": severity,
                    "message": message,
                }
                self.alerts.appendleft(alert)
                new.append(alert)
        self._active = set(current)
        return new
