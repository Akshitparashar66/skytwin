from ..twin.perturbations import KINDS, Perturbation

PRESETS: tuple[dict, ...] = (
    {
        "id": "power_plus_20",
        "label": "Power consumption +20%",
        "description": "All loads draw 20% more power, e.g. a new high-power payload mode.",
        "perturbations": [{"kind": "load_increase", "magnitude": 20}],
    },
    {
        "id": "comms_loss_10",
        "label": "Comms blackout 10 min",
        "description": "Ground link lost for 10 minutes.",
        "perturbations": [{"kind": "comms_blackout", "duration_min": 10}],
    },
    {
        "id": "temp_plus_15",
        "label": "Temperature +15 °C",
        "description": "Spacecraft temperature jumps by 15 °C.",
        "perturbations": [{"kind": "thermal_spike", "magnitude": 15}],
    },
    {
        "id": "solar_damage_30",
        "label": "Solar array damage 30%",
        "description": "Solar array output drops 30%.",
        "perturbations": [{"kind": "solar_degradation", "magnitude": 30}],
    },
    {
        "id": "radiator_30",
        "label": "Radiator degradation 30%",
        "description": "Radiator emissivity drops 30%; the spacecraft heats up.",
        "perturbations": [{"kind": "radiator_degradation", "magnitude": 30}],
    },
    {
        "id": "power_plus_20_shed",
        "label": "Power +20% with payload shed",
        "description": "Mitigation for the +20% case: power the payload down.",
        "perturbations": [{"kind": "load_increase", "magnitude": 20}, {"kind": "payload_off"}],
    },
)


def catalog() -> dict:
    return {
        "kinds": [spec.to_dict() for spec in KINDS.values()],
        "presets": [
            {**preset, "perturbations": [Perturbation(**p).to_dict() for p in preset["perturbations"]]} for preset in PRESETS
        ],
    }
