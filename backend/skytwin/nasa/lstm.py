"""Trained LSTM next-value predictor (exported to ONNX by training/train_lstm.py).

Residual = actual − predicted next value; it feeds the same DynamicThresholdDetector as the statistical
predictor, so the benchmark compares predictors on equal terms.
"""

import json
from pathlib import Path

import numpy as np

MODELS_DIR = Path(__file__).resolve().parents[2] / "models"
MODEL_FILE = "lstm_detector.onnx"
META_FILE = "lstm_detector.json"


class LstmPredictor:
    def __init__(self, onnx_path: Path, meta_path: Path, batch: int = 4096):
        import onnxruntime as ort

        self.meta = json.loads(meta_path.read_text(encoding="utf-8"))
        self.window = int(self.meta["window"])
        self.horizon = int(self.meta.get("horizon", 1))
        self.batch = batch
        self.session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name

    @classmethod
    def load(cls, models_dir: Path = MODELS_DIR) -> "LstmPredictor | None":
        onnx_path, meta_path = models_dir / MODEL_FILE, models_dir / META_FILE
        if not (onnx_path.exists() and meta_path.exists()):
            return None
        return cls(onnx_path, meta_path)

    @property
    def fingerprint(self) -> str:
        return str(self.meta.get("sha256", "unknown"))[:12]

    def predict(self, values: np.ndarray) -> np.ndarray:
        """Prediction of values[t] from the window ending `horizon` steps earlier; NaN where no full window exists."""
        values = np.asarray(values, dtype=np.float32)
        out = np.full(len(values), np.nan, dtype=np.float32)
        lead = self.window + self.horizon - 1
        if len(values) <= lead:
            return out
        windows = np.lib.stride_tricks.sliding_window_view(values[: -self.horizon], self.window)
        preds = []
        for i in range(0, len(windows), self.batch):
            chunk = np.ascontiguousarray(windows[i : i + self.batch])[:, :, None]
            preds.append(self.session.run(None, {self.input_name: chunk})[0][:, 0])
        out[lead:] = np.concatenate(preds)
        return out

    def residuals(self, values: np.ndarray) -> np.ndarray:
        pred = self.predict(values)
        res = np.asarray(values, dtype=np.float64) - pred
        res[np.isnan(pred)] = 0.0
        return res
