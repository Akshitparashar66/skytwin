import pytest

from skytwin.config import DEFAULT_PARAMS
from skytwin.twin import SAFE, Perturbation, Spacecraft
from skytwin.twin.spacecraft import sun_factor

ORBIT_S = DEFAULT_PARAMS.orbit_period_s


@pytest.fixture(scope="module")
def settled():
    return Spacecraft.settled().snapshot()


def run(snapshot, *perturbations, hours=6):
    craft = Spacecraft.from_snapshot(snapshot)
    for p in perturbations:
        craft.schedule(p)
    return craft.run(hours * 3600)


def test_sun_factor_has_sunlight_eclipse_and_penumbra():
    assert sun_factor(ORBIT_S * 0.3, DEFAULT_PARAMS) == 1.0
    assert sun_factor(ORBIT_S * 0.8, DEFAULT_PARAMS) == 0.0
    assert 0.0 < sun_factor(ORBIT_S * 0.65, DEFAULT_PARAMS) < 1.0


def test_settled_spacecraft_is_periodic_and_power_positive(settled):
    frames = run(settled, hours=ORBIT_S / 3600 * 2)
    per_orbit = round(ORBIT_S / 60)
    first, second = frames[per_orbit], frames[2 * per_orbit]
    assert abs(first.soc_pct - second.soc_pct) < 0.5
    assert abs(first.bus_temp_c - second.bus_temp_c) < 0.5
    assert min(f.soc_pct for f in frames) > 60
    assert all(f.mode == "NOMINAL" for f in frames)


def test_battery_discharges_in_eclipse_and_charges_in_sunlight(settled):
    frames = run(settled, hours=ORBIT_S / 3600)
    eclipse = [f for f in frames if f.in_eclipse]
    sunlit = [f for f in frames if f.solar_power_w == DEFAULT_PARAMS.solar_array_peak_w and f.soc_pct < 99.9]
    assert eclipse and all(f.battery_current_a > 0 for f in eclipse)
    assert sunlit and all(f.battery_current_a < 0 for f in sunlit)
    soc = [f.soc_pct for f in eclipse]
    assert all(b <= a for a, b in zip(soc, soc[1:]))


def test_load_increase_drains_battery_and_warms_spacecraft(settled):
    base, more = run(settled), run(settled, Perturbation("load_increase", 20))
    assert min(f.soc_pct for f in more) < min(f.soc_pct for f in base) - 10
    assert max(f.battery_temp_c for f in more) > max(f.battery_temp_c for f in base)
    assert max(f.battery_current_a for f in more) > max(f.battery_current_a for f in base)


def test_solar_degradation_triggers_safe_mode_and_sheds_payload(settled):
    frames = run(settled, Perturbation("solar_degradation", 30))
    safe = [f for f in frames if f.mode == SAFE]
    assert safe, "expected onboard FDIR to enter SAFE mode"
    assert safe[0].safe_mode_reason.startswith("Battery SOC")
    assert not any(f.payload_on for f in safe)


def test_comms_blackout_builds_backlog_that_drains(settled):
    frames = run(settled, Perturbation("comms_blackout", duration_min=10), hours=1)
    peak = max(f.data_buffer_mb for f in frames)
    assert peak == pytest.approx(15.0, abs=0.5)
    assert frames[-1].data_buffer_mb == 0.0
    assert not frames[5].link_up and frames[30].link_up


def test_thermal_spike_is_applied_once(settled):
    frames = run(settled, Perturbation("thermal_spike", 15), hours=1)
    assert frames[1].bus_temp_c > settled.bus_temp_c + 14


def test_payload_off_saves_its_power(settled):
    frames = run(settled, Perturbation("payload_off"), hours=0.2)
    assert not frames[-1].payload_on
    assert frames[-1].load_power_w == pytest.approx(DEFAULT_PARAMS.bus_load_w + DEFAULT_PARAMS.comms_tx_load_w)


def test_delayed_and_bounded_perturbations(settled):
    frames = run(settled, Perturbation("load_increase", 50, start_min=10, duration_min=10), hours=0.5)
    nominal = DEFAULT_PARAMS.bus_load_w + DEFAULT_PARAMS.payload_load_w + DEFAULT_PARAMS.comms_tx_load_w
    assert frames[5].load_power_w == pytest.approx(nominal)
    assert frames[15].load_power_w == pytest.approx(nominal * 1.5)
    assert frames[25].load_power_w == pytest.approx(nominal)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"kind": "nope"},
        {"kind": "load_increase", "magnitude": 500},
        {"kind": "load_increase", "magnitude": 10, "start_min": -1},
        {"kind": "comms_blackout", "duration_min": 0},
    ],
)
def test_invalid_perturbations_are_rejected(kwargs):
    with pytest.raises(ValueError):
        Perturbation(**kwargs)


def test_perturbation_defaults():
    assert Perturbation("load_increase").magnitude == 20.0
    assert Perturbation("comms_blackout").duration_min == 10.0
    assert Perturbation("payload_off", magnitude=5).magnitude is None
