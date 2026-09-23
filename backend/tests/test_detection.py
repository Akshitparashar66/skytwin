import random

import numpy as np

from skytwin.nasa.dataset import Channel
from skytwin.nasa.validation import DetectorConfig, evaluate, rolling_mean_residuals, runs, score
from skytwin.telemetry import DynamicThresholdDetector, LiveTwin
from skytwin.twin import Perturbation


def test_detector_quiet_on_noise_and_flags_a_step():
    rng = random.Random(0)
    det = DynamicThresholdDetector(alpha=0.3, z=6.0, warmup=30, min_consecutive=2)
    assert not any(det.update(rng.gauss(0, 1)).is_anomaly for _ in range(2000))
    assert any(det.update(8.0 + rng.gauss(0, 1)).is_anomaly for _ in range(10))


def test_persistent_fault_stays_flagged():
    rng = random.Random(1)
    det = DynamicThresholdDetector(alpha=0.3, z=6.0, warmup=30)
    for _ in range(500):
        det.update(rng.gauss(0, 1))
    flags = [det.update(10 + rng.gauss(0, 1)).is_anomaly for _ in range(300)]
    assert all(flags[5:])


def test_live_twin_has_no_false_alarms_when_nominal():
    live = LiveTwin()
    for _ in range(1000):
        assert not live.tick()["anomalies"]


def test_live_twin_detects_injected_load_fault():
    live = LiveTwin()
    live.inject_fault(Perturbation("load_increase", 20))
    payloads = [live.tick() for _ in range(5)]
    assert any(a["channel"] == "load_power_w" for p in payloads for a in p["anomalies"])
    assert any(alert["kind"] == "anomaly" for alert in live.alerts)


def test_clearing_faults_resets_safe_mode():
    live = LiveTwin()
    live.inject_fault(Perturbation("solar_degradation", 100))
    for _ in range(400):
        if live.tick()["frame"]["mode"] == "SAFE":
            break
    assert live.truth.state.mode == "SAFE"
    live.clear_faults()
    assert live.truth.state.mode == "NOMINAL" and live.faults == []


def test_runs_and_scoring():
    flags = np.array([0, 1, 1, 0, 0, 1, 0, 1, 1, 1], dtype=bool)
    assert runs(flags) == [(1, 2), (5, 5), (7, 9)]
    tp, fp, fn = score([(1, 2), (5, 5), (7, 9)], ((0, 1), (20, 30)))
    assert (tp, fp, fn) == (1, 2, 1)


def test_residuals_use_preceding_values_only():
    r = rolling_mean_residuals(np.array([1.0, 1.0, 1.0, 4.0]), window=2)
    assert r.tolist() == [0.0, 0.0, 0.0, 3.0]


def test_evaluate_finds_synthetic_anomaly():
    rng = np.random.default_rng(0)
    values = rng.normal(0, 0.01, 3000)
    values[2000:2100] += 0.8
    channel = Channel("TEST", "T-1", values, ((2000, 2100),))
    metrics = evaluate([channel], [rolling_mean_residuals(values, 30)], DetectorConfig(alpha=0.1, z=12.0))
    assert metrics["true_positives"] == 1 and metrics["false_negatives"] == 0
