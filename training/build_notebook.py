"""Regenerate SkyTwin_LSTM_Training.ipynb from train_lstm.py (so the notebook never drifts from the tested script).

Usage:  python training/build_notebook.py
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = (HERE / "train_lstm.py").read_text(encoding="utf-8")


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip().splitlines(keepends=True)}


def code(text: str) -> dict:
    return {
        "cell_type": "code",
        "metadata": {},
        "execution_count": None,
        "outputs": [],
        "source": text.strip().splitlines(keepends=True),
    }


cells = [
    md(
        """
# SkyTwin — train the LSTM anomaly detector

Trains a next-value LSTM predictor on NASA SMAP/MSL **nominal (unlabelled) training telemetry** and exports it
to ONNX for SkyTwin. Anomaly labels are never used here; SkyTwin tunes thresholds on SMAP and scores on held-out MSL.

**How to run (hands-off):**
1. `Runtime → Change runtime type → T4 GPU` (CPU works too, just slower).
2. `Runtime → Run all`.
3. Approve the Google Drive prompt that appears in the first cell. That's the only click needed.
4. Walk away. Typical T4 run: ~10–20 min. Checkpoints are saved to Drive every epoch; if Colab disconnects,
   just `Run all` again and it resumes.

**Output:** `MyDrive/skytwin_model/lstm_detector.onnx` and `lstm_detector.json`.
Copy both into SkyTwin's `backend/models/`, then run `python scripts/validate_anomalies.py` from `backend/`.
"""
    ),
    code(
        """
import os
import subprocess

gpu = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True).stdout.strip()
print(gpu or "No GPU found: training will run on CPU (slower). Runtime > Change runtime type > T4 GPU.")

OUT = "/content/skytwin_model"
try:
    from google.colab import drive
    drive.mount("/content/drive")
    OUT = "/content/drive/MyDrive/skytwin_model"
except Exception as exc:  # not in Colab, or Drive declined
    print("Google Drive not mounted, saving inside this runtime instead:", exc)
os.makedirs(OUT, exist_ok=True)
print("Output folder:", OUT)
"""
    ),
    code(
        """
# Red "dependency conflicts" about protobuf / google-ai-generativelanguage / ydf / grpcio are EXPECTED and harmless:
# onnx needs a newer protobuf than some preinstalled Colab packages that this notebook never uses.
!pip install -q onnx onnxscript onnxruntime
print("Install finished. Ignore any protobuf conflict messages above.")
"""
    ),
    code("%%writefile train_lstm.py\n" + SCRIPT),
    code(
        """
# Full training run. Tweak --epochs / --hidden / --window here if you want to experiment.
!python train_lstm.py --data-dir /content/data --out-dir "{OUT}" --epochs 40 --hidden 64 --layers 2 --window 100 --horizon 30
"""
    ),
    code(
        """
import json
import shutil

meta = json.load(open(f"{OUT}/lstm_detector.json"))
print(f"Best validation MSE: {meta['best_val_mse']:.6f} after {meta['epochs_run']} epochs on {meta['device']} ({meta['train_seconds']} s)")
archive = shutil.make_archive("/content/skytwin_model", "zip", OUT, ".")
print("Files:", [f for f in os.listdir(OUT) if f.startswith("lstm_detector")])
try:
    from google.colab import files
    files.download(archive)  # only works if the tab is open; the files are in Drive either way
except Exception:
    pass
"""
    ),
]

notebook = {
    "cells": cells,
    "metadata": {
        "accelerator": "GPU",
        "colab": {"provenance": [], "gpuType": "T4"},
        "kernelspec": {"name": "python3", "display_name": "Python 3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 0,
}

out = HERE / "SkyTwin_LSTM_Training.ipynb"
out.write_text(json.dumps(notebook, indent=1), encoding="utf-8")
print(f"Wrote {out}")
