"""Download the NASA SMAP/MSL labelled telemetry anomaly dataset (~118 MB).

The original telemanom S3 archive is no longer public, so this pulls the widely used preprocessed copy
(all channels concatenated, column 0 = telemetry value) from the Time-Series-Library mirror, plus the
original per-channel label file from the telemanom repository.

Usage:  python scripts/download_nasa.py
"""

import sys
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "nasa"
MIRROR = "https://huggingface.co/datasets/thuml/Time-Series-Library/resolve/main"
FILES = {
    "SMAP_test.npy": f"{MIRROR}/SMAP/SMAP_test.npy",
    "SMAP_test_label.npy": f"{MIRROR}/SMAP/SMAP_test_label.npy",
    "MSL_test.npy": f"{MIRROR}/MSL/MSL_test.npy",
    "MSL_test_label.npy": f"{MIRROR}/MSL/MSL_test_label.npy",
    "labeled_anomalies.csv": "https://raw.githubusercontent.com/khundman/telemanom/master/labeled_anomalies.csv",
}


def download(url: str, dest: Path) -> None:
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=60) as response, open(tmp, "wb") as out:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        while chunk := response.read(1 << 20):
            out.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r  {dest.name}: {done / total:6.1%}", end="", flush=True)
    tmp.replace(dest)
    print(f"\r  {dest.name}: done ({dest.stat().st_size / 1e6:.1f} MB)")


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in FILES.items():
        dest = DATA_DIR / name
        if dest.exists():
            print(f"  {name}: already present")
            continue
        try:
            download(url, dest)
        except OSError as exc:
            print(f"\n  {name}: FAILED ({exc})", file=sys.stderr)
            return 1
    print(f"Dataset ready in {DATA_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
