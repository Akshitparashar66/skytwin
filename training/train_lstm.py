"""Train SkyTwin's LSTM telemetry predictor on NASA SMAP/MSL nominal telemetry and export it to ONNX.

Runs unattended (Colab or local): downloads data, trains with early stopping, checkpoints every epoch
(and resumes from a checkpoint after a disconnect), exports ONNX, verifies it with onnxruntime, and
writes metadata. Only the unlabelled *train* splits are used, so no anomaly labels leak into training.

Usage:  python train_lstm.py --data-dir data --out-dir out
Smoke:  python train_lstm.py --data-dir data --out-dir out --epochs 1 --max-windows 5000
"""

import argparse
import hashlib
import json
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import torch
from torch import nn

MIRROR = "https://huggingface.co/datasets/thuml/Time-Series-Library/resolve/main"
SPACECRAFT = ("SMAP", "MSL")


def download(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    for sc in SPACECRAFT:
        dest = data_dir / f"{sc}_train.npy"
        if not dest.exists():
            print(f"Downloading {dest.name} ...", flush=True)
            urllib.request.urlretrieve(f"{MIRROR}/{sc}/{sc}_train.npy", dest)


def load_series(data_dir: Path) -> list[np.ndarray]:
    """Column 0 (the telemetry value) of each spacecraft's concatenated nominal train split."""
    return [np.load(data_dir / f"{sc}_train.npy")[:, 0].astype(np.float32) for sc in SPACECRAFT]


def make_windows(series: list[np.ndarray], window: int, horizon: int = 1, val_fraction: float = 0.1):
    """Windows of `window` values predicting the value `horizon` steps after the window ends.

    horizon > 1 stops the model from simply copying the latest sample, which otherwise lets it track
    anomalies instead of exposing them. The last `val_fraction` of each series is validation."""
    xs_tr, ys_tr, xs_va, ys_va = [], [], [], []
    for s in series:
        views = np.lib.stride_tricks.sliding_window_view(s[:-horizon], window)
        targets = s[window + horizon - 1 :]
        split = int(len(targets) * (1 - val_fraction))
        xs_tr.append(views[:split])
        ys_tr.append(targets[:split])
        xs_va.append(views[split:])
        ys_va.append(targets[split:])
    return (
        np.ascontiguousarray(np.concatenate(xs_tr)),
        np.concatenate(ys_tr),
        np.ascontiguousarray(np.concatenate(xs_va)),
        np.concatenate(ys_va),
    )


class Predictor(nn.Module):
    def __init__(self, hidden: int = 64, layers: int = 2, dropout: float = 0.2):
        super().__init__()
        self.lstm = nn.LSTM(1, hidden, num_layers=layers, batch_first=True, dropout=dropout if layers > 1 else 0.0)
        self.head = nn.Linear(hidden, 1)

    def forward(self, window: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(window)
        return self.head(out[:, -1, :])


def evaluate(model: nn.Module, x: np.ndarray, y: np.ndarray, device: str, batch: int) -> float:
    model.eval()
    total, n = 0.0, 0
    with torch.no_grad():
        for i in range(0, len(x), batch):
            xb = torch.from_numpy(x[i : i + batch]).unsqueeze(-1).to(device)
            yb = torch.from_numpy(y[i : i + batch]).unsqueeze(-1).to(device)
            total += nn.functional.mse_loss(model(xb), yb, reduction="sum").item()
            n += len(xb)
    return total / max(n, 1)


def export_onnx(model: nn.Module, window: int, path: Path) -> None:
    model = model.eval().cpu()
    dummy = torch.zeros(1, window, 1)
    kwargs = dict(
        input_names=["window"],
        output_names=["prediction"],
        dynamic_axes={"window": {0: "batch"}, "prediction": {0: "batch"}},
        opset_version=17,
    )
    try:
        torch.onnx.export(model, (dummy,), str(path), dynamo=False, **kwargs)
    except TypeError:  # older torch without the `dynamo` flag
        torch.onnx.export(model, (dummy,), str(path), **kwargs)


def verify_onnx(model: nn.Module, path: Path, x: np.ndarray) -> float:
    import onnxruntime as ort

    sample = x[:64][:, :, None].astype(np.float32)
    onnx_out = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"]).run(None, {"window": sample})[0]
    with torch.no_grad():
        torch_out = model.eval().cpu()(torch.from_numpy(sample)).numpy()
    return float(np.max(np.abs(onnx_out - torch_out)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--out-dir", type=Path, default=Path("out"))
    ap.add_argument("--window", type=int, default=100)
    ap.add_argument("--horizon", type=int, default=30, help="predict this many steps past the window end")
    ap.add_argument("--hidden", type=int, default=64)
    ap.add_argument("--layers", type=int, default=2)
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch", type=int, default=512)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--patience", type=int, default=5)
    ap.add_argument("--max-windows", type=int, default=0, help="subsample training windows (smoke tests)")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    rng = np.random.default_rng(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    args.out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Device: {device}" + (f" ({torch.cuda.get_device_name(0)})" if device == "cuda" else ""), flush=True)

    download(args.data_dir)
    x_tr, y_tr, x_va, y_va = make_windows(load_series(args.data_dir), args.window, args.horizon)
    if args.max_windows:
        keep = rng.choice(len(x_tr), size=min(args.max_windows, len(x_tr)), replace=False)
        x_tr, y_tr = x_tr[keep], y_tr[keep]
        x_va, y_va = x_va[: args.max_windows // 5], y_va[: args.max_windows // 5]
    print(f"Windows: {len(x_tr):,} train, {len(x_va):,} validation (window={args.window}, horizon={args.horizon})", flush=True)

    model = Predictor(args.hidden, args.layers).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, factor=0.5, patience=2)

    ckpt_path = args.out_dir / "checkpoint.pt"
    start_epoch, best, best_state, stale, history = 0, float("inf"), None, 0, []
    if ckpt_path.exists():
        ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
        if ckpt["config"] == vars(args) | {"data_dir": str(args.data_dir), "out_dir": str(args.out_dir)}:
            model.load_state_dict(ckpt["model"])
            opt.load_state_dict(ckpt["opt"])
            start_epoch, best, best_state, stale, history = (
                ckpt["epoch"] + 1, ckpt["best"], ckpt["best_state"], ckpt["stale"], ckpt["history"],
            )  # fmt: skip
            print(f"Resuming from checkpoint after epoch {start_epoch}", flush=True)

    config = vars(args) | {"data_dir": str(args.data_dir), "out_dir": str(args.out_dir)}
    started = time.time()
    for epoch in range(start_epoch, args.epochs):
        if stale >= args.patience:
            break
        model.train()
        order = rng.permutation(len(x_tr))
        t0 = time.time()
        for i in range(0, len(order), args.batch):
            idx = order[i : i + args.batch]
            xb = torch.from_numpy(x_tr[idx]).unsqueeze(-1).to(device)
            yb = torch.from_numpy(y_tr[idx]).unsqueeze(-1).to(device)
            opt.zero_grad()
            loss = nn.functional.mse_loss(model(xb), yb)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        val = evaluate(model, x_va, y_va, device, args.batch * 4)
        sched.step(val)
        if val < best - 1e-7:
            best, stale = val, 0
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        else:
            stale += 1
        history.append({"epoch": epoch + 1, "val_mse": val, "seconds": round(time.time() - t0, 1)})
        print(f"epoch {epoch + 1:3d}  val_mse {val:.6f}  best {best:.6f}  {time.time() - t0:5.1f}s", flush=True)
        torch.save(
            {"config": config, "model": model.state_dict(), "opt": opt.state_dict(), "epoch": epoch,
             "best": best, "best_state": best_state, "stale": stale, "history": history},
            ckpt_path,
        )  # fmt: skip

    model.load_state_dict(best_state)
    onnx_path = args.out_dir / "lstm_detector.onnx"
    export_onnx(model, args.window, onnx_path)
    diff = verify_onnx(model, onnx_path, x_va)
    if diff > 1e-3:
        raise SystemExit(f"ONNX output differs from PyTorch by {diff:.2e}")

    meta = {
        "model": "LSTM multi-step predictor",
        "window": args.window,
        "horizon": args.horizon,
        "hidden": args.hidden,
        "layers": args.layers,
        "trained_on": [f"{sc}_train (unlabelled nominal telemetry)" for sc in SPACECRAFT],
        "train_windows": int(len(x_tr)),
        "val_windows": int(len(x_va)),
        "epochs_run": len(history),
        "best_val_mse": best,
        "history": history,
        "device": device,
        "torch": torch.__version__,
        "onnx_max_abs_diff": diff,
        "sha256": hashlib.sha256(onnx_path.read_bytes()).hexdigest(),
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "train_seconds": round(time.time() - started, 1),
    }
    (args.out_dir / "lstm_detector.json").write_text(json.dumps(meta, indent=2))
    print(f"\nDone. best val MSE {best:.6f}; ONNX verified (max diff {diff:.1e}).")
    print(f"Copy these two files into SkyTwin's backend/models/:\n  {onnx_path}\n  {args.out_dir / 'lstm_detector.json'}")


if __name__ == "__main__":
    main()
