"""Perturbations: changes applied to a spacecraft model.

The same perturbation types serve two purposes:
- What-If scenarios (applied to a sandboxed copy of the twin), and
- demo "environment events" injected into the live truth model to emulate a real-world fault.
"""

from dataclasses import dataclass

from .state import TwinState


@dataclass(frozen=True)
class MagnitudeSpec:
    label: str
    unit: str
    default: float
    minimum: float
    maximum: float


@dataclass(frozen=True)
class KindSpec:
    kind: str
    label: str
    description: str
    category: str
    magnitude: MagnitudeSpec | None = None
    impulse: bool = False
    default_duration_min: float | None = None
    requires_duration: bool = False

    def to_dict(self) -> dict:
        m = self.magnitude
        return {
            "kind": self.kind,
            "label": self.label,
            "description": self.description,
            "category": self.category,
            "impulse": self.impulse,
            "default_duration_min": self.default_duration_min,
            "requires_duration": self.requires_duration,
            "magnitude": None
            if m is None
            else {"label": m.label, "unit": m.unit, "default": m.default, "min": m.minimum, "max": m.maximum},
        }


KINDS: dict[str, KindSpec] = {
    spec.kind: spec
    for spec in (
        KindSpec(
            "load_increase",
            "Power consumption increase",
            "All spacecraft loads (bus, payload, comms) draw more power.",
            "operation",
            MagnitudeSpec("Increase", "%", 20.0, 1.0, 200.0),
        ),
        KindSpec(
            "solar_degradation",
            "Solar array degradation",
            "Solar array output drops, e.g. from panel damage or a string failure.",
            "fault",
            MagnitudeSpec("Output loss", "%", 30.0, 1.0, 100.0),
        ),
        KindSpec(
            "battery_capacity_loss",
            "Battery capacity loss",
            "Usable battery capacity drops, e.g. from a failed cell string.",
            "fault",
            MagnitudeSpec("Capacity loss", "%", 30.0, 1.0, 90.0),
        ),
        KindSpec(
            "thermal_spike",
            "Temperature spike",
            "Spacecraft temperature jumps instantly (bus and battery).",
            "fault",
            MagnitudeSpec("Temperature rise", "°C", 15.0, 1.0, 40.0),
            impulse=True,
        ),
        KindSpec(
            "radiator_degradation",
            "Radiator degradation",
            "Radiator emissivity drops (contamination, coating damage), so heat is shed more slowly.",
            "fault",
            MagnitudeSpec("Emissivity loss", "%", 30.0, 1.0, 90.0),
        ),
        KindSpec(
            "comms_blackout",
            "Communication loss",
            "The ground link is lost; the transmitter idles and payload data accumulates onboard.",
            "fault",
            default_duration_min=10.0,
            requires_duration=True,
        ),
        KindSpec(
            "payload_off",
            "Payload power-down",
            "Mitigation: switch the payload off to save power (no science data is generated).",
            "mitigation",
        ),
    )
}


@dataclass(frozen=True)
class Perturbation:
    kind: str
    magnitude: float | None = None
    start_min: float = 0.0
    duration_min: float | None = None

    def __post_init__(self) -> None:
        spec = KINDS.get(self.kind)
        if spec is None:
            raise ValueError(f"unknown perturbation kind: {self.kind!r}")
        if self.start_min < 0:
            raise ValueError("start_min must be >= 0")
        if self.duration_min is not None and self.duration_min <= 0:
            raise ValueError("duration_min must be > 0")
        if spec.requires_duration and self.duration_min is None:
            object.__setattr__(self, "duration_min", spec.default_duration_min)
        if spec.magnitude is None:
            object.__setattr__(self, "magnitude", None)
        else:
            m = spec.magnitude
            value = m.default if self.magnitude is None else float(self.magnitude)
            if not m.minimum <= value <= m.maximum:
                raise ValueError(f"{self.kind} magnitude must be between {m.minimum} and {m.maximum} {m.unit}")
            object.__setattr__(self, "magnitude", value)

    @property
    def spec(self) -> KindSpec:
        return KINDS[self.kind]

    @property
    def start_s(self) -> float:
        return self.start_min * 60.0

    @property
    def end_s(self) -> float | None:
        if self.spec.impulse or self.duration_min is None:
            return None
        return (self.start_min + self.duration_min) * 60.0

    @property
    def persistent(self) -> bool:
        return not self.spec.impulse and self.duration_min is None

    def is_active(self, elapsed_s: float) -> bool:
        if elapsed_s < self.start_s:
            return False
        end = self.end_s
        return end is None or elapsed_s < end

    def scaled(self, factor: float) -> "Perturbation":
        """Same perturbation with magnitude scaled and clamped to the allowed range (for ensembles)."""
        if self.magnitude is None:
            return self
        m = self.spec.magnitude
        value = min(max(self.magnitude * factor, m.minimum), m.maximum)
        return Perturbation(self.kind, value, self.start_min, self.duration_min)

    def label(self) -> str:
        spec = self.spec
        if spec.magnitude is not None:
            sign = "+" if spec.kind in ("load_increase", "thermal_spike") else ""
            unit = spec.magnitude.unit
            sep = " " if unit == "°C" else ""
            text = f"{spec.label} {sign}{self.magnitude:g}{sep}{unit}"
        else:
            text = spec.label
        if self.duration_min is not None and not spec.impulse:
            text += f" for {self.duration_min:g} min"
        if self.start_min > 0:
            text += f" at T+{self.start_min:g} min"
        return text

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "magnitude": self.magnitude,
            "start_min": self.start_min,
            "duration_min": self.duration_min,
            "label": self.label(),
        }


@dataclass
class Modifiers:
    load_scale: float = 1.0
    solar_scale: float = 1.0
    capacity_scale: float = 1.0
    emissivity_scale: float = 1.0
    link_up: bool = True
    payload_forced_off: bool = False


def apply_effect(p: Perturbation, mods: Modifiers) -> None:
    fraction = (p.magnitude or 0.0) / 100.0
    if p.kind == "load_increase":
        mods.load_scale *= 1.0 + fraction
    elif p.kind == "solar_degradation":
        mods.solar_scale *= 1.0 - fraction
    elif p.kind == "battery_capacity_loss":
        mods.capacity_scale *= 1.0 - fraction
    elif p.kind == "radiator_degradation":
        mods.emissivity_scale *= 1.0 - fraction
    elif p.kind == "comms_blackout":
        mods.link_up = False
    elif p.kind == "payload_off":
        mods.payload_forced_off = True


def apply_impulse(p: Perturbation, state: TwinState) -> None:
    if p.kind == "thermal_spike":
        state.bus_temp_c += p.magnitude
        state.battery_temp_c += p.magnitude
