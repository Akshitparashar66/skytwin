from typing import Literal

from pydantic import BaseModel, Field, model_validator

from ..twin.perturbations import Perturbation
from ..whatif.engine import MAX_HORIZON_MIN

Kind = Literal[
    "load_increase",
    "solar_degradation",
    "battery_capacity_loss",
    "thermal_spike",
    "radiator_degradation",
    "comms_blackout",
    "payload_off",
]


class PerturbationIn(BaseModel):
    kind: Kind
    magnitude: float | None = None
    start_min: float = Field(0.0, ge=0, le=MAX_HORIZON_MIN)
    duration_min: float | None = Field(None, gt=0, le=MAX_HORIZON_MIN)

    @model_validator(mode="after")
    def _check(self) -> "PerturbationIn":
        self.to_domain()  # raises ValueError (→ 422) on out-of-range magnitude
        return self

    def to_domain(self) -> Perturbation:
        return Perturbation(self.kind, self.magnitude, self.start_min, self.duration_min)


class SimulateRequest(BaseModel):
    perturbations: list[PerturbationIn] = Field(..., min_length=1, max_length=8)
    horizon_min: int = Field(360, ge=10, le=MAX_HORIZON_MIN)
    label: str | None = Field(None, max_length=120)


class CompareRequest(BaseModel):
    a: SimulateRequest
    b: SimulateRequest
