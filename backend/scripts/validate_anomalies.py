"""Benchmark the anomaly detectors on NASA SMAP/MSL and write data/validation_report.json.

Includes the trained LSTM automatically if backend/models/lstm_detector.onnx + .json exist.
Usage:  python scripts/download_nasa.py && python scripts/validate_anomalies.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from skytwin.nasa.dataset import DEFAULT_DATA_DIR, available  # noqa: E402
from skytwin.nasa.lstm import LstmPredictor  # noqa: E402
from skytwin.nasa.validation import run_validation  # noqa: E402

REPORT = ROOT / "data" / "validation_report.json"


def main() -> int:
    if not available(DEFAULT_DATA_DIR):
        print("NASA dataset not found. Run: python scripts/download_nasa.py", file=sys.stderr)
        return 1
    predictor = LstmPredictor.load()
    if predictor is None:
        print("No trained model in backend/models/ — benchmarking the statistical detector only.")
    report = run_validation(DEFAULT_DATA_DIR, REPORT, predictor=predictor, cache_dir=ROOT / "data")
    print()
    for m in report["methods"]:
        s, h = m["smap_tuning"], m["msl_held_out"]
        print(f"{m['name']}  [{m['variant']}] {m['config']}")
        print(
            f"  SMAP (tuning):  {s['true_positives']}/{s['labelled_anomalies']}  P {s['precision']:.2f} R {s['recall']:.2f} F1 {s['f1']:.2f}"
        )
        print(
            f"  MSL (held out): {h['true_positives']}/{h['labelled_anomalies']}  P {h['precision']:.2f} R {h['recall']:.2f} F1 {h['f1']:.2f}"
        )
    print(f"Report written to {REPORT} ({report['runtime_s']} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
