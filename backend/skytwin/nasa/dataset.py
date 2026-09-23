"""Loader for the NASA SMAP/MSL labelled telemetry anomaly dataset (Hundman et al., KDD 2018).

The mirrored files concatenate every channel's test series in chan_id order (SMAP excludes P-2);
labeled_anomalies.csv gives each channel's length and anomaly index ranges, which lets us split the
series back into per-channel telemetry. Column 0 is the telemetry value; the rest are command flags.
"""

import ast
import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "nasa"
EXCLUDED = {"SMAP": {"P-2"}, "MSL": set()}


@dataclass(frozen=True)
class Channel:
    spacecraft: str
    chan_id: str
    values: np.ndarray
    anomalies: tuple[tuple[int, int], ...]


def available(data_dir: Path = DEFAULT_DATA_DIR) -> bool:
    return all((data_dir / f).exists() for f in ("labeled_anomalies.csv", "SMAP_test.npy", "MSL_test.npy"))


def load(spacecraft: str, data_dir: Path = DEFAULT_DATA_DIR) -> list[Channel]:
    with open(data_dir / "labeled_anomalies.csv", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["spacecraft"] == spacecraft and r["chan_id"] not in EXCLUDED[spacecraft]]
    rows.sort(key=lambda r: r["chan_id"])
    series = np.load(data_dir / f"{spacecraft}_test.npy", mmap_mode="r")[:, 0]
    expected = sum(int(r["num_values"]) for r in rows)
    if expected != len(series):
        raise ValueError(f"{spacecraft}: label file expects {expected} values, data has {len(series)}")

    channels, offset = [], 0
    for r in rows:
        n = int(r["num_values"])
        spans = tuple((int(a), int(b)) for a, b in ast.literal_eval(r["anomaly_sequences"]))
        channels.append(Channel(spacecraft, r["chan_id"], np.asarray(series[offset : offset + n], dtype=float), spans))
        offset += n
    return channels
