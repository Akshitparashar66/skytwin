import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from skytwin.nasa.dataset import Channel
from skytwin.nasa.lstm import META_FILE, MODEL_FILE, LstmPredictor
from skytwin.nasa.validation import LSTM_THRESHOLD_GRID, tune_and_test

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def models_dir(tmp_path):
    shutil.copy(FIXTURES / "tiny_lstm.onnx", tmp_path / MODEL_FILE)
    shutil.copy(FIXTURES / "tiny_lstm.json", tmp_path / META_FILE)
    return tmp_path


def test_load_returns_none_without_model(tmp_path):
    assert LstmPredictor.load(tmp_path) is None


def test_predicts_every_point_after_the_window(models_dir):
    p = LstmPredictor.load(models_dir)
    assert p is not None and p.window == 8
    values = np.sin(np.linspace(0, 20, 500)).astype(np.float32)
    pred = p.predict(values)
    assert np.isnan(pred[:8]).all() and np.isfinite(pred[8:]).all()
    res = p.residuals(values)
    assert (res[:8] == 0).all() and np.isfinite(res).all()


def test_batching_does_not_change_predictions(models_dir):
    values = np.random.default_rng(0).normal(size=3000).astype(np.float32)
    small = LstmPredictor.load(models_dir)
    small.batch = 7
    big = LstmPredictor.load(models_dir)
    np.testing.assert_allclose(small.predict(values)[8:], big.predict(values)[8:], atol=1e-5)


def test_short_series_is_all_nan(models_dir):
    assert np.isnan(LstmPredictor.load(models_dir).predict(np.zeros(5))).all()


def test_lstm_method_runs_through_tuning(models_dir):
    p = LstmPredictor.load(models_dir)
    rng = np.random.default_rng(1)

    def channel(name):
        v = rng.normal(0, 0.01, 1500)
        v[1000:1050] += 1.0
        return Channel("T", name, v, ((1000, 1050),))

    grid = {"alpha": (0.3,), "z": (6.0,), "signed": (False,)}
    result = tune_and_test([channel("A")], [channel("B")], {"lstm": lambda ch: p.residuals(ch.values)}, grid, log=lambda _: None)
    assert result["variant"] == "lstm"
    assert result["msl_held_out"]["labelled_anomalies"] == 1
    assert set(LSTM_THRESHOLD_GRID) == {"alpha", "z", "signed"}


def test_horizon_shifts_prediction_lead(tmp_path):
    shutil.copy(FIXTURES / "tiny_lstm.onnx", tmp_path / MODEL_FILE)
    meta = json.loads((FIXTURES / "tiny_lstm.json").read_text())
    (tmp_path / META_FILE).write_text(json.dumps(meta | {"horizon": 5}))
    p = LstmPredictor.load(tmp_path)
    values = np.sin(np.linspace(0, 20, 300)).astype(np.float32)
    pred = p.predict(values)
    lead = p.window + p.horizon - 1
    assert np.isnan(pred[:lead]).all() and np.isfinite(pred[lead:]).all()
    # the prediction for t uses the window ending at t - horizon, i.e. one-step prediction shifted by horizon - 1
    one_step = LstmPredictor.load(tmp_path)
    one_step.horizon = 1
    np.testing.assert_allclose(pred[lead:], one_step.predict(values)[p.window : len(values) - p.horizon + 1], atol=1e-6)
