"""Benchmark anomaly detectors on labelled NASA spacecraft anomalies.

Each method is a *predictor* (statistical rolling mean, or the trained LSTM) whose residuals feed the same
dynamic-threshold detector used in Live Mode. Scoring follows Hundman et al.: a labelled anomaly is a true
positive if any flagged run overlaps it; flagged runs overlapping no label are false positives.
Thresholds are tuned on SMAP; the chosen configuration is reported on held-out MSL.
"""

import itertools
import json
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from ..telemetry.detector import DynamicThresholdDetector
from .dataset import Channel, load
from .lstm import LstmPredictor


@dataclass(frozen=True)
class DetectorConfig:
    alpha: float = 0.1
    z: float = 12.0
    signed: bool = False
    min_std: float = 0.01


def rolling_mean_residuals(values: np.ndarray, window: int) -> np.ndarray:
    """values[t] minus the mean of the preceding `window` values."""
    csum = np.concatenate(([0.0], np.cumsum(values)))
    out = np.zeros_like(values, dtype=np.float64)
    t = np.arange(1, len(values))
    lo = np.maximum(0, t - window)
    out[1:] = values[1:] - (csum[t] - csum[lo]) / (t - lo)
    return out


def detect(residuals: np.ndarray, cfg: DetectorConfig) -> np.ndarray:
    det = DynamicThresholdDetector(alpha=cfg.alpha, window=250, z=cfg.z, min_std=cfg.min_std, warmup=50, signed=cfg.signed)
    return np.array([det.update(r).is_anomaly for r in residuals.tolist()], dtype=bool)


def runs(flags: np.ndarray) -> list[tuple[int, int]]:
    """Inclusive (start, end) index ranges of consecutive True values."""
    padded = np.concatenate(([False], flags, [False])).astype(np.int8)
    edges = np.flatnonzero(np.diff(padded))
    return [(int(a), int(b) - 1) for a, b in zip(edges[::2], edges[1::2])]


def score(predicted: list[tuple[int, int]], labelled: tuple[tuple[int, int], ...]) -> tuple[int, int, int]:
    def overlaps(p, q):
        return p[0] <= q[1] and q[0] <= p[1]

    tp = sum(any(overlaps(p, lab) for p in predicted) for lab in labelled)
    fp = sum(not any(overlaps(p, lab) for lab in labelled) for p in predicted)
    return tp, fp, len(labelled) - tp


def evaluate(channels: list[Channel], residuals: list[np.ndarray], cfg: DetectorConfig) -> dict:
    tp = fp = fn = 0
    for ch, res in zip(channels, residuals, strict=True):
        a, b, c = score(runs(detect(res, cfg)), ch.anomalies)
        tp, fp, fn = tp + a, fp + b, fn + c
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "channels": len(channels),
        "labelled_anomalies": tp + fn,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
    }


THRESHOLD_GRID = {"alpha": (0.1, 0.3), "z": (6.0, 9.0, 12.0, 16.0), "signed": (False, True)}
LSTM_THRESHOLD_GRID = {"alpha": (0.1, 0.3, 0.5), "z": (4.0, 6.0, 9.0, 12.0, 16.0), "signed": (False, True)}
ROLLING_WINDOWS = (5, 30)

ResidualFn = Callable[[Channel], np.ndarray]


def tune_and_test(
    smap: list[Channel],
    msl: list[Channel],
    variants: dict[str, ResidualFn],
    grid: dict,
    log: Callable[[str], None],
) -> dict:
    """Sweep predictor variants × threshold grid on SMAP; report the best on held-out MSL."""
    sweep: list[dict] = []
    best: dict | None = None
    for variant, fn in variants.items():
        smap_res = [fn(ch) for ch in smap]
        for combo in itertools.product(*grid.values()):
            cfg = DetectorConfig(**dict(zip(grid.keys(), combo)))
            metrics = evaluate(smap, smap_res, cfg)
            row = {"variant": variant, "config": asdict(cfg), **metrics}
            sweep.append(row)
            log(
                f"    SMAP {variant} {asdict(cfg)} -> F1 {metrics['f1']:.3f} (P {metrics['precision']:.2f} R {metrics['recall']:.2f})"
            )
            if best is None or metrics["f1"] > best["f1"]:
                best = row
    assert best is not None
    cfg = DetectorConfig(**best["config"])
    msl_res = [variants[best["variant"]](ch) for ch in msl]
    return {
        "variant": best["variant"],
        "config": best["config"],
        "smap_tuning": {k: v for k, v in best.items() if k not in ("variant", "config")},
        "msl_held_out": evaluate(msl, msl_res, cfg),
        "sweep": sweep,
    }


def _cached(fn: ResidualFn, cache_path: Path | None) -> ResidualFn:
    """Memoise per-channel residuals on disk (LSTM inference over ~500k windows takes a few minutes)."""
    store: dict[str, np.ndarray] = {}
    if cache_path is not None and cache_path.exists():
        with np.load(cache_path) as data:
            store = {k: data[k] for k in data.files}

    def wrapped(ch: Channel) -> np.ndarray:
        key = f"{ch.spacecraft}_{ch.chan_id}"
        if key not in store:
            store[key] = fn(ch)
            if cache_path is not None:
                np.savez_compressed(cache_path, **store)
        return store[key]

    return wrapped


def run_validation(
    data_dir: Path,
    out_path: Path | None = None,
    predictor: LstmPredictor | None = None,
    log: Callable[[str], None] = print,
    cache_dir: Path | None = None,
) -> dict:
    started = time.perf_counter()
    smap, msl = load("SMAP", data_dir), load("MSL", data_dir)
    methods = []

    log("Statistical predictor (rolling mean):")
    stat = tune_and_test(
        smap,
        msl,
        {f"rolling_mean_{w}": (lambda ch, w=w: rolling_mean_residuals(ch.values, w)) for w in ROLLING_WINDOWS},
        THRESHOLD_GRID,
        log,
    )
    methods.append(
        {
            "id": "statistical",
            "name": "Statistical (rolling mean)",
            "description": "Predicts each value as the mean of the previous samples. No training.",
            **stat,
        }
    )

    if predictor is not None:
        log(f"LSTM predictor (model {predictor.fingerprint}):")
        cache = None if cache_dir is None else cache_dir / f"lstm_residuals_{predictor.fingerprint}.npz"
        lstm = tune_and_test(
            smap, msl, {"lstm": _cached(lambda ch: predictor.residuals(ch.values), cache)}, LSTM_THRESHOLD_GRID, log
        )
        meta = predictor.meta
        methods.append(
            {
                "id": "lstm",
                "name": "LSTM (trained)",
                "description": f"{meta.get('layers')}-layer LSTM, window {meta.get('window')}, horizon {meta.get('horizon', 1)}, trained on unlabelled SMAP/MSL train splits.",
                "model": {
                    k: meta.get(k)
                    for k in (
                        "window",
                        "horizon",
                        "hidden",
                        "layers",
                        "epochs_run",
                        "best_val_mse",
                        "created_at",
                        "device",
                        "sha256",
                    )
                },
                **lstm,
            }
        )

    report = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "dataset": "NASA SMAP & MSL labelled telemetry anomalies (Hundman et al., KDD 2018)",
        "protocol": "Thresholds tuned on SMAP, evaluated on held-out MSL; a labelled anomaly counts as detected if any flagged run overlaps it",
        "detector": "Dynamic-threshold residual detector (same scoring core as Live Mode)",
        "reference": "Published baseline for this benchmark: Telemanom (LSTM predictor + nonparametric dynamic thresholding)",
        "methods": methods,
        "runtime_s": round(time.perf_counter() - started, 1),
    }
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
