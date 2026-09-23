# Training the LSTM anomaly detector

SkyTwin's NASA benchmark compares two predictors that feed the same dynamic-threshold detector:
a statistical rolling mean (no training) and a **trained LSTM** that predicts the telemetry value 30 steps
after each 100-sample window. (Predicting only 1 step ahead lets the model copy the last sample and hide anomalies.) This folder trains the LSTM.

## Train on Google Colab (hands-off)

1. Open [colab.research.google.com](https://colab.research.google.com) → **File → Upload notebook** →
   `training/SkyTwin_LSTM_Training.ipynb`.
2. **Runtime → Change runtime type → T4 GPU**.
3. **Runtime → Run all**, approve the Google Drive prompt in the first cell, then leave it.
   Checkpoints go to Drive every epoch. If Colab disconnects, **Run all** again and it resumes.
   The pip cell prints red *dependency conflict* messages about `protobuf`. They're expected and harmless.
4. When done, download `MyDrive/skytwin_model/lstm_detector.onnx` and `lstm_detector.json`.

## Plug it into SkyTwin

```bash
# copy both files into backend/models/, then from backend/:
.venv/Scripts/python scripts/validate_anomalies.py     # adds an "LSTM (trained)" row to the benchmark
```

The first run takes a few minutes: the LSTM predicts ~500k windows on CPU, and the residuals are cached in
`backend/data/`. Restart the API and the Live Mode "NASA benchmark" card shows both detectors side by side.

## Protocol (why the numbers are honest)

- Training uses only the **unlabelled nominal train splits** (`SMAP_train`, `MSL_train`); anomaly labels are never seen.
- Thresholds are tuned on SMAP test; the reported numbers are on **MSL test**, which tuning never saw.
- The LSTM powers the benchmark only. Live Mode keeps using physics-twin residuals, because a model trained on
  NASA's normalised channels doesn't transfer to SkyTwin's physical telemetry without retraining.

## Local run / smoke test

```bash
pip install torch onnx onnxscript onnxruntime numpy
python training/train_lstm.py --data-dir training/data --out-dir training/out --epochs 1 --max-windows 5000
```

`build_notebook.py` regenerates the notebook from `train_lstm.py`. Edit the script, then rebuild; never edit the notebook by hand.
