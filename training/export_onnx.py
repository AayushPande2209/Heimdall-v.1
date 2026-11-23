"""Export the classifier and compare ONNX against PyTorch on validation.

Run with: python3 -m training.export_onnx
"""
from pathlib import Path
import time

import numpy as np
import onnxruntime as ort
import torch
from torch import nn

ROOT = Path(__file__).resolve().parents[1]


def normalize(crops):
    med = np.median(crops, axis=(1, 2), keepdims=True)
    std = crops.std(axis=(1, 2), keepdims=True)
    return (crops - med) / (std + 1e-6)


def build_model():
    return nn.Sequential(
        nn.Conv2d(1, 8, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        nn.Conv2d(8, 16, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        nn.Conv2d(16, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        nn.Flatten(), nn.Linear(1024, 32), nn.ReLU(), nn.Linear(32, 1))


def main():
    model = build_model()
    local_models = ROOT / "models" / "_local"
    local_models.mkdir(parents=True, exist_ok=True)
    model.load_state_dict(torch.load(local_models / "heimdall_cnn_full.pt", map_location="cpu", weights_only=True))
    model.eval()
    target = local_models / "heimdall_cnn_full.onnx"
    torch.onnx.export(model, torch.zeros(1, 1, 64, 32, dtype=torch.float32), target,
                      input_names=["crop"], output_names=["logit"], opset_version=17,
                      dynamic_axes={"crop": {0: "batch"}, "logit": {0: "batch"}},
                      dynamo=False)
    with np.load(ROOT / "data" / "fpir_full" / "crops_val.npz", allow_pickle=False) as data:
        x = normalize(data["crops"][:256]).astype(np.float32)[:, None]
    with torch.no_grad():
        reference = model(torch.from_numpy(x)).numpy()
    session = ort.InferenceSession(str(target), providers=["CPUExecutionProvider"])
    actual = session.run(["logit"], {"crop": x})[0]
    difference = float(np.max(np.abs(reference - actual)))
    if reference.shape != actual.shape or difference >= 1e-4:
        raise RuntimeError(f"ONNX/PyTorch mismatch: {reference.shape}, {actual.shape}, {difference}")
    print(f"max absolute logit difference (256 validation crops): {difference:.9g}")
    print(f"ONNX file size: {target.stat().st_size} bytes ({target.stat().st_size / 1024:.1f} KiB)")
    for batch in (1, 8):
        feed = x[:batch]
        for _ in range(20):
            session.run(["logit"], {"crop": feed})
        repeats = 200
        start = time.perf_counter()
        for _ in range(repeats):
            session.run(["logit"], {"crop": feed})
        ms_per_crop = (time.perf_counter() - start) * 1000 / (repeats * batch)
        print(f"batch {batch}: {ms_per_crop:.4f} ms per crop")


if __name__ == "__main__":
    main()
