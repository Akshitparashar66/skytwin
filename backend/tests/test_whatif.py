import copy

import pytest

from skytwin.telemetry import LiveTwin
from skytwin.twin import Perturbation, Spacecraft
from skytwin.whatif import PRESETS, catalog, simulate
from skytwin.whatif.narrative import fmt_duration


@pytest.fixture(scope="module")
def snapshot():
    return Spacecraft.settled().snapshot()


def impact(result, key):
    return next(i for i in result["impacts"] if i["key"] == key)


def test_simulation_never_modifies_the_live_twin():
    live = LiveTwin(prime_ticks=5)
    before = copy.deepcopy(live.truth.state)
    faults_before = live.faults
    simulate(live.snapshot(), [Perturbation("solar_degradation", 60), Perturbation("thermal_spike", 30)])
    assert live.truth.state == before
    assert live.faults == faults_before


def test_simulation_is_deterministic(snapshot):
    a = simulate(snapshot, [Perturbation("load_increase", 20)])
    b = simulate(snapshot, [Perturbation("load_increase", 20)])
    assert a == b


def test_result_shape(snapshot):
    r = simulate(snapshot, [Perturbation("load_increase", 20)], horizon_min=120)
    assert len(r["baseline"]) == len(r["scenario"]) == len(r["band"]) == 121
    assert r["scenario"][0]["t_min"] == 0 and r["scenario"][-1]["t_min"] == 120
    band = r["band"][60]
    assert band["soc_pct_lo"] <= r["scenario"][60]["soc_pct"] <= band["soc_pct_hi"]
    assert r["risk_level"] in {"NOMINAL", "CAUTION", "WARNING", "CRITICAL"}
    assert r["narrative"] and r["recommendations"]


def test_power_increase_impact_chain(snapshot):
    r = simulate(snapshot, [Perturbation("load_increase", 20)])
    assert impact(r, "peak_discharge_a")["direction"] == "up"
    assert impact(r, "max_battery_temp_c")["direction"] == "up"
    assert impact(r, "min_soc_pct")["direction"] == "down"
    assert impact(r, "avg_power_margin_w")["effect"] == "worse"
    assert r["summary"]["endurance_h"] is not None
    assert r["summary"]["baseline_endurance_h"] is None
    assert any("power-negative" in line for line in r["narrative"])


def test_solar_damage_is_critical_with_safe_mode(snapshot):
    r = simulate(snapshot, [Perturbation("solar_degradation", 30)])
    assert r["risk_level"] == "CRITICAL"
    assert r["summary"]["safe_mode_at_min"] is not None
    assert r["summary"]["endurance_basis"] == "simulated"
    assert any(f["channel"] == "mode" and f["confidence"] == "likely" for f in r["findings"])


def test_comms_blackout_recovers(snapshot):
    r = simulate(snapshot, [Perturbation("comms_blackout", duration_min=10)])
    assert r["risk_level"] == "NOMINAL"
    assert impact(r, "max_data_buffer_mb")["predicted"] == pytest.approx(15, abs=0.5)
    assert r["summary"]["recovery_applicable"]
    assert 0 < r["summary"]["recovery_min"] < 10


def test_thermal_spike_recovers_within_horizon(snapshot):
    r = simulate(snapshot, [Perturbation("thermal_spike", 15)])
    assert r["summary"]["recovery_min"] is not None


def test_radiator_degradation_warns_on_temperature(snapshot):
    r = simulate(snapshot, [Perturbation("radiator_degradation", 30)])
    assert r["risk_level"] == "WARNING"
    assert {"battery_temp_c", "bus_temp_c"} <= {f["channel"] for f in r["findings"] if f["confidence"] == "likely"}
    assert not any("payload power-down" in rec for rec in r["recommendations"])


def test_mitigation_improves_power(snapshot):
    raw = simulate(snapshot, [Perturbation("load_increase", 20)])
    shed = simulate(snapshot, [Perturbation("load_increase", 20), Perturbation("payload_off")])
    assert impact(shed, "avg_power_margin_w")["predicted"] > impact(raw, "avg_power_margin_w")["predicted"]
    assert shed["summary"]["endurance_h"] is None


def test_every_preset_runs(snapshot):
    for preset in PRESETS:
        r = simulate(snapshot, [Perturbation(**p) for p in preset["perturbations"]], horizon_min=60)
        assert r["scenario"]


def test_horizon_is_bounded(snapshot):
    with pytest.raises(ValueError):
        simulate(snapshot, [Perturbation("load_increase")], horizon_min=5)


def test_catalog_lists_kinds_and_presets():
    c = catalog()
    assert {k["kind"] for k in c["kinds"]} >= {"load_increase", "comms_blackout", "thermal_spike"}
    assert len(c["presets"]) == len(PRESETS)


@pytest.mark.parametrize(("minutes", "text"), [(5, "5 min"), (60, "1 h"), (272, "4 h 32 min")])
def test_fmt_duration(minutes, text):
    assert fmt_duration(minutes) == text
