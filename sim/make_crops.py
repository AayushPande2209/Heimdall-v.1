"""
Synthetic training crops for the Heimdall crop classifier (exercise 3).

Each crop is what the pipeline would cut around a confirmed track: one warm
object, roughly centred, resized to 64 x 32 (height x width), in degrees C.

Positives:  people standing / sitting / prone, 6-20 m, sometimes behind a trunk
Negatives:  deer, sun-warmed rock, stump, warm leaf-litter patch
            (the things the hot-spot detector actually confuses with people)

python3 -m sim.make_crops --n 8000 --seed 1 --out data/synthetic/crops_train.npz
python3 -m sim.make_crops --n 2000 --seed 2 --out data/synthetic/crops_val.npz

Output .npz:
crops     (N, 64, 32) float32   temperatures in C
labels    (N,)        float32   1 = person, 0 = not
kinds     (N,)        str       person / deer / rock / stump / litter
distance  (N,)        float32   metres
"""
import argparse
from pathlib import Path

import cv2
import numpy as np

from sim.synthframes import (PANO_H, SS, build_background, draw_deer, draw_person, draw_rock,
                             feet_row, px)

ROOT = Path(__file__).resolve().parents[1]

CROP_H, CROP_W = 64, 32
CANVAS_W = 120                       # low-res width of the little scene we render into
NEG_KINDS = ["deer", "rock", "stump", "litter"]


def draw_stump(img, cx, distance, ambient, rng):
    """Upright, uniformly warm, no head: the classic 'is that a person?' stump."""
    fy = feet_row(distance)
    w, h = px(rng.uniform(0.3, 0.5), distance), px(rng.uniform(0.6, 1.3), distance)
    t = ambient + rng.uniform(5, 10)
    cv2.rectangle(img, (int((cx - w / 2) * SS), int((fy - h) * SS)),
                  (int((cx + w / 2) * SS), int(fy * SS)), float(t), -1)
    return [cx - w / 2, fy - h, w, h]


def draw_litter(img, cx, distance, ambient, rng):
    """Warm patch of leaf litter on the ground: flat, irregular, low."""
    fy = feet_row(distance)
    w, h = px(rng.uniform(0.6, 1.5), distance), px(rng.uniform(0.2, 0.4), distance)
    t = ambient + rng.uniform(4, 9)
    cv2.ellipse(img, (int(cx * SS), int((fy - h / 2) * SS)),
                (max(1, int(w / 2 * SS)), max(1, int(h / 2 * SS))),
                rng.uniform(-15, 15), 0, 360, float(t), -1)
    return [cx - w / 2, fy - h, w, h]


def render_one(rng, kind):
    ambient = rng.uniform(0, 20)
    distance = rng.uniform(6, 20)
    bg = build_background(rng, ambient)
    x0 = rng.integers(0, bg.shape[1] - CANVAS_W)
    scene = bg[:, x0:x0 + CANVAS_W]
    hr = cv2.resize(scene, (CANVAS_W * SS, PANO_H * SS), interpolation=cv2.INTER_NEAREST)
    cx = CANVAS_W / 2

    if kind == "person":
        pose = rng.choice(["standing", "standing", "sitting", "prone"])
        box = draw_person(hr, cx, distance, pose, ambient, rng)
    elif kind == "deer":
        box = draw_deer(hr, cx, distance, ambient)
    elif kind == "rock":
        box = draw_rock(hr, cx, rng.uniform(5, 20), ambient)   # varied size
    elif kind == "stump":
        box = draw_stump(hr, cx, distance, ambient, rng)
    else:
        box = draw_litter(hr, cx, distance, ambient, rng)

    # 30% chance a trunk partly covers the object (for every kind, so
    # "has a trunk in front" can't become a shortcut for the label)
    if rng.random() < 0.3:
        bx, _, bw, _ = box
        tw = bw * rng.uniform(0.2, 0.5)
        tx = bx + rng.uniform(0, bw)
        t = ambient + rng.uniform(-0.5, 0.8)
        cv2.rectangle(hr, (int((tx - tw / 2) * SS), 0), (int((tx + tw / 2) * SS), PANO_H * SS), float(t), -1)

    img = cv2.resize(hr, (CANVAS_W, PANO_H), interpolation=cv2.INTER_AREA)
    img = cv2.GaussianBlur(img, (0, 0), 0.6)                          # optics
    img = img + rng.normal(0, 0.05, img.shape).astype(np.float32)     # sensor noise

    # crop like the tracker would: around the box, 2:1 tall, with some slop
    bx, by, bw, bh = box
    side = max(bh, 2 * bw) * rng.uniform(1.2, 1.5)
    ccx = bx + bw / 2 + rng.normal(0, 0.08) * bw
    ccy = by + bh / 2 + rng.normal(0, 0.08) * bh
    patch = cv2.getRectSubPix(img, (max(2, int(round(side / 2))), max(2, int(round(side)))), (ccx, ccy))
    crop = cv2.resize(patch, (CROP_W, CROP_H), interpolation=cv2.INTER_LINEAR)
    return crop.astype(np.float32), distance


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=8000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default=str(ROOT / "data" / "synthetic" / "crops_train.npz"))
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)

    crops, labels, kinds, dists = [], [], [], []
    for i in range(args.n):
        kind = "person" if i % 2 == 0 else NEG_KINDS[(i // 2) % len(NEG_KINDS)]
        crop, d = render_one(rng, kind)
        crops.append(crop)
        labels.append(1.0 if kind == "person" else 0.0)
        kinds.append(kind)
        dists.append(d)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.out, crops=np.stack(crops), labels=np.array(labels, np.float32),
                        kinds=np.array(kinds), distance=np.array(dists, np.float32))
    print(f"wrote {args.out}: {args.n} crops ({int(sum(labels))} person)")


if __name__ == "__main__":
    main()
