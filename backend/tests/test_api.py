import pytest
from fastapi.testclient import TestClient

from skytwin.api.main import create_app


@pytest.fixture()
def client():
    with TestClient(create_app(start_loop=False)) as c:
        yield c


def test_health_and_config(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    cfg = client.get("/api/config").json()
    assert cfg["orbit_period_min"] == pytest.approx(95)
    assert any(limit["channel"] == "soc_pct" for limit in cfg["limits"])


def test_twin_state_and_history(client):
    state = client.get("/api/twin/state").json()
    assert state["type"] == "telemetry"
    assert 0 <= state["frame"]["soc_pct"] <= 100.5
    assert len(client.get("/api/twin/history").json()) > 0


def test_scenarios_catalog(client):
    body = client.get("/api/scenarios").json()
    assert body["kinds"] and body["presets"]


def test_simulate_end_to_end(client):
    res = client.post("/api/simulate", json={"perturbations": [{"kind": "load_increase", "magnitude": 20}], "horizon_min": 180})
    assert res.status_code == 200
    body = res.json()
    assert len(body["scenario"]) == 181
    assert body["impacts"] and body["narrative"]


def test_simulate_does_not_touch_live_state(client):
    before = client.get("/api/twin/state").json()["frame"]
    client.post("/api/simulate", json={"perturbations": [{"kind": "solar_degradation", "magnitude": 90}]})
    after = client.get("/api/twin/state").json()["frame"]
    assert before == after
    assert client.get("/api/live/faults").json() == []


@pytest.mark.parametrize(
    "payload",
    [
        {"perturbations": []},
        {"perturbations": [{"kind": "warp_drive"}]},
        {"perturbations": [{"kind": "load_increase", "magnitude": 1000}]},
        {"perturbations": [{"kind": "load_increase"}], "horizon_min": 5000},
        {"perturbations": [{"kind": "comms_blackout", "duration_min": -3}]},
    ],
)
def test_simulate_rejects_bad_input(client, payload):
    assert client.post("/api/simulate", json=payload).status_code == 422


def test_compare_uses_one_snapshot(client):
    res = client.post(
        "/api/compare",
        json={
            "a": {"perturbations": [{"kind": "load_increase", "magnitude": 20}]},
            "b": {"perturbations": [{"kind": "load_increase", "magnitude": 20}, {"kind": "payload_off"}]},
        },
    )
    assert res.status_code == 200
    a, b = res.json()["a"], res.json()["b"]
    assert a["baseline"] == b["baseline"]
    assert a["start_t_min"] == b["start_t_min"]


def test_fault_injection_lifecycle(client):
    assert client.post("/api/live/faults", json={"kind": "solar_degradation", "magnitude": 30}).status_code == 201
    faults = client.get("/api/live/faults").json()
    assert len(faults) == 1 and faults[0]["kind"] == "solar_degradation"
    assert client.delete("/api/live/faults").json() == []


def test_validation_endpoint(client):
    body = client.get("/api/validation").json()
    assert "available" in body
    if body["available"]:
        assert body["methods"] and all("msl_held_out" in m and "sweep" not in m for m in body["methods"])


def test_websocket_sends_history_then_frames():
    app = create_app(start_loop=True, tick_interval_s=0.01)
    with TestClient(app) as c, c.websocket_connect("/ws/telemetry") as ws:
        assert ws.receive_json()["type"] == "history"
        assert ws.receive_json()["type"] == "telemetry"
