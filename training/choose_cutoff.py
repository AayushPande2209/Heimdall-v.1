"""Choose a classification cutoff using validation crops only.

Run with: python3 -m training.choose_cutoff
"""
from pathlib import Path

import numpy as np
import onnxruntime as ort

ROOT = Path(__file__).resolve().parents[1]


def normalize(crops):
    med = np.median(crops, axis=(1, 2), keepdims=True)
    std = crops.std(axis=(1, 2), keepdims=True)
    return (crops - med) / (std + 1e-6)


def main():
    with np.load(ROOT / "data" / "fpir_full" / "crops_val.npz", allow_pickle=False) as data:
        x = normalize(data["crops"]).astype(np.float32)[:, None]
        kinds = data["kinds"]
    session = ort.InferenceSession(str(ROOT / "models" / "heimdall_cnn_full.onnx"), providers=["CPUExecutionProvider"])
    logits = session.run(["logit"], {"crop": x})[0].reshape(-1)
    probability = 1.0 / (1.0 + np.exp(-np.clip(logits, -80, 80)))
    print("cutoff  person found  hard_neg called person  rand_neg called person")
    chosen = None
    for cutoff in (0.5, 0.4, 0.3, 0.25, 0.2, 0.15, 0.1):
        found = 100 * np.mean(probability[kinds == "person"] > cutoff)
        hard = 100 * np.mean(probability[kinds == "hard_neg"] > cutoff)
        random = 100 * np.mean(probability[kinds == "rand_neg"] > cutoff)
        print(f"{cutoff:6.2f} {found:12.1f}% {hard:22.1f}% {random:22.1f}%")
        if chosen is None and cutoff >= 0.2 and found >= 95.0:
            chosen = cutoff
    print("chosen cutoff:", chosen if chosen is not None else "none meets 95% at or above 0.2")


if __name__ == "__main__":
    main()
