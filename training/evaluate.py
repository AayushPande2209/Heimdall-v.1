"""
Look inside a trained model's results without training anything.

  python3 -m training.evaluate models/_local/heimdall_cnn_full.pt
  python3 -m training.evaluate models/_local/heimdall_cnn_fp.pt --split val

Prints:
  1. How many people it finds at different confidence cutoffs, and how many
     non-people it wrongly calls people at each cutoff.
  2. Person accuracy for every video sequence, so you can see whether misses
     are spread out or come from one or two scenes.
Saves:
  missed_<split>_<model>.png      48 person crops the model called "not person"
  false_alarms_<split>_<model>.png  up to 24 non-person crops it called "person"
"""
import argparse
from pathlib import Path

import cv2
import numpy as np
import torch
from torch import nn

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "fpir_full"
RESULTS = ROOT / "results"


def normalize(crops):                       # must match train_fp.py exactly
    med = np.median(crops, axis=(1, 2), keepdims=True)
    std = crops.std(axis=(1, 2), keepdims=True)
    return (crops - med) / (std + 1e-6)


def build_model():                          # must match train_fp.py exactly
    return nn.Sequential(
        nn.Conv2d(1, 8, kernel_size=3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        nn.Conv2d(8, 16, kernel_size=3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        nn.Conv2d(16, 32, kernel_size=3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        nn.Flatten(),
        nn.Linear(1024, 32), nn.ReLU(),
        nn.Linear(32, 1),
    )


def tile(crops, captions, cols=12, scale=3):
    tiles = []
    for c, cap in zip(crops, captions):
        g = cv2.normalize(c, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        g = cv2.resize(g, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
        g = cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)
        g = cv2.copyMakeBorder(g, 0, 26, 1, 1, cv2.BORDER_CONSTANT, value=(0, 0, 0))
        for i, line in enumerate(cap.split("\n")):
            cv2.putText(g, line, (2, 64 * scale + 10 + 11 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.3,
                        (255, 255, 255), 1, cv2.LINE_AA)
        tiles.append(g)
    while len(tiles) % cols:
        tiles.append(np.zeros_like(tiles[0]))
    rows = [np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)]
    return np.vstack(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("checkpoint")
    ap.add_argument("--split", default="test")
    args = ap.parse_args()

    d = np.load(DATA / f"crops_{args.split}.npz", allow_pickle=False)
    crops, labels, kinds, seq = d["crops"], d["labels"], d["kinds"], d["seq"]
    pose, vis = d["pose"], d["visibility"]

    checkpoint = Path(args.checkpoint)
    if not checkpoint.is_absolute():
        checkpoint = ROOT / checkpoint
    model = build_model()
    model.load_state_dict(torch.load(checkpoint, map_location="cpu"))
    model.eval()
    with torch.no_grad():
        x = torch.tensor(normalize(crops), dtype=torch.float32).unsqueeze(1)
        p = torch.sigmoid(model(x).squeeze(1)).numpy()

    person = kinds == "person"
    print(f"{checkpoint.name} on {args.split}: {person.sum()} person crops, {(~person).sum()} non-person\n")

    print("cutoff   people found   hard_neg called person   rand_neg called person")
    for cut in [0.5, 0.4, 0.3, 0.2, 0.1, 0.05]:
        found = (p[person] > cut).mean() * 100
        fa_h = (p[kinds == "hard_neg"] > cut).mean() * 100
        fa_r = (p[kinds == "rand_neg"] > cut).mean() * 100
        print(f"  {cut:4.2f}      {found:5.1f}%             {fa_h:5.1f}%                   {fa_r:5.1f}%")

    print("\nperson accuracy by sequence (cutoff 0.5):")
    print("  sequence   people   found   lying share   avg score")
    for s in sorted(set(seq[person])):
        m = person & (seq == s)
        lying = (pose[m] == "lying").mean() * 100
        print(f"  {s[:3]:<9} {m.sum():6d}   {100 * (p[m] > 0.5).mean():5.1f}%      {lying:5.1f}%       {p[m].mean():.2f}")

    RESULTS.mkdir(parents=True, exist_ok=True)
    tag = checkpoint.stem
    miss = np.where(person & (p <= 0.5))[0]
    rng = np.random.default_rng(0)
    pick = rng.choice(miss, size=min(48, len(miss)), replace=False) if len(miss) else []
    if len(pick):
        caps = [f"{seq[i][:3]} {pose[i][:2]}{vis[i]}\np={p[i]:.2f}" for i in pick]
        cv2.imwrite(str(RESULTS / f"missed_{args.split}_{tag}.png"), tile(crops[pick], caps))
    fa = np.where(~person & (p > 0.5))[0][:24]
    if len(fa):
        caps = [f"{seq[i][:3]} {kinds[i][:4]}\np={p[i]:.2f}" for i in fa]
        cv2.imwrite(str(RESULTS / f"false_alarms_{args.split}_{tag}.png"), tile(crops[fa], caps))
    print(f"\nsaved missed_{args.split}_{tag}.png ({len(pick)} of {len(miss)} misses)"
          + (f" and false_alarms_{args.split}_{tag}.png ({len(fa)})" if len(fa) else ""))


if __name__ == "__main__":
    main()
