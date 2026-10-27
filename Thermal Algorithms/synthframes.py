"""
Synthetic FLIR Lepton 3.5 radiometric sequences for testing Heimdall without hardware.

Produces 160x120 uint16 frames in centikelvin (the same format the Lepton
outputs in radiometric TLinear mode at 0.01 K resolution), plus ground truth.

What it simulates:
- Night/dusk forest scene: cold sky, treeline, ground, tree trunks, texture
- People standing, sitting or prone at set distances, some partly behind trunks
- Distractors: a sun-warmed rock, a deer, single-frame "flicker" hot spots
- Shoulder-mount motion: slow scanning pan + walking sway and bounce
- Sensor effects: optical blur, ~50 mK temporal noise, fixed-pattern noise,
    and periodic FFC (shutter) freezes

Usage:
python synth_frames.py --out sample.npz --frames 300 --seed 1
"""
import argparse
import json

import cv2
import numpy as np

W, H = 160, 120
HFOV_DEG = 57.0
IFOV = np.deg2rad(HFOV_DEG) / W          # radians per pixel (~6.2 mrad)
FPS = 8.7
CAM_HEIGHT_M = 1.5                       # shoulder height
SS = 4                                   # supersampling factor for rendering

PANO_W, PANO_H = 520, 200                # world strip the camera pans across
HORIZON = 70                             # panorama row of the horizon


def c_to_ck(t_c):
    """Celsius -> Lepton centikelvin uint16."""
    return np.clip(np.round((t_c + 273.15) * 100.0), 0, 65535).astype(np.uint16)


def px(meters, distance_m):
    """Size in pixels of an object `meters` across at `distance_m`."""
    return meters / distance_m / IFOV


def feet_row(distance_m):
    """Panorama row where something standing on flat ground at distance_m touches it."""
    return HORIZON + np.arctan(CAM_HEIGHT_M / distance_m) / IFOV


def build_background(rng, ambient):
    """Low-res world panorama in degrees C (no objects yet)."""
    y = np.arange(PANO_H, dtype=np.float32)[:, None]
    sky = ambient - 22.0
    ground = ambient + 0.5 + 2.0 * np.clip((y - HORIZON) / (PANO_H - HORIZON), 0, 1)
    scene = np.where(y < HORIZON - 25, sky, ground).astype(np.float32)
    scene = np.broadcast_to(scene, (PANO_H, PANO_W)).copy()

    # canopy band between sky and horizon: near ambient, slightly mottled
    canopy = (y >= HORIZON - 25) & (y < HORIZON)
    scene[np.broadcast_to(canopy, scene.shape)] = ambient - 1.0

    # low-frequency texture (leaf litter, brush) +/- ~1 C
    tex = rng.normal(0, 1, (PANO_H // 8, PANO_W // 8)).astype(np.float32)
    tex = cv2.resize(tex, (PANO_W, PANO_H), interpolation=cv2.INTER_CUBIC)
    scene += 0.8 * tex

    # a few warm leaf-litter patches that are NOT people (clutter)
    for _ in range(6):
        cx, cy = rng.integers(0, PANO_W), rng.integers(HORIZON + 10, PANO_H)
        r = rng.integers(3, 9)
        cv2.circle(scene, (int(cx), int(cy)), int(r), float(ambient + rng.uniform(2, 4)), -1)
    scene = cv2.GaussianBlur(scene, (0, 0), 1.5)
    return scene


def draw_person(img, cx, distance, pose, ambient, rng):
    """Draw a person into a supersampled image. Returns bbox in panorama px (low-res)."""
    fy = feet_row(distance)
    cloth = min(ambient + rng.uniform(9, 14), 29.0)    # clothing surface
    skin = rng.uniform(30.5, 33.0)                      # face/hands
    if pose == "standing":
        h, w = px(1.7, distance), px(0.5, distance)
    elif pose == "sitting":
        h, w = px(1.0, distance), px(0.6, distance)
    else:  # prone
        h, w = px(0.35, distance), px(1.7, distance)

    top = fy - h
    s = SS
    body_c = (int(cx * s), int((fy - h * 0.43) * s))
    body_ax = (max(1, int(w / 2 * s)), max(1, int(h * 0.43 * s)))
    cv2.ellipse(img, body_c, body_ax, 0, 0, 360, float(cloth), -1)
    head_r = max(1, int(min(w, h) * 0.22 * s)) if pose == "prone" else max(1, int(h * 0.065 * s))
    if pose == "prone":
        head_c = (int((cx + w / 2 - head_r / s) * s), int((fy - h * 0.5) * s))
    else:
        head_c = (int(cx * s), int((top + h * 0.07) * s))
    cv2.circle(img, head_c, head_r, float(skin), -1)
    return [cx - w / 2, top, w, h]


def draw_deer(img, cx, distance, ambient):
    fy = feet_row(distance)
    s = SS
    bw, bh = px(1.5, distance), px(0.55, distance)
    leg = px(0.7, distance)
    fur = ambient + 9.0
    cv2.ellipse(img, (int(cx * s), int((fy - leg - bh / 2) * s)),
                (max(1, int(bw / 2 * s)), max(1, int(bh / 2 * s))), 0, 0, 360, float(fur), -1)
    for dx in (-0.35, 0.35):
        x = int((cx + dx * bw) * s)
        cv2.line(img, (x, int((fy - leg) * s)), (x, int(fy * s)), float(fur - 2), max(1, int(px(0.08, distance) * s)))
    hr = max(1, int(px(0.15, distance) * s))
    cv2.circle(img, (int((cx + bw / 2) * s), int((fy - leg - bh) * s)), hr, float(fur + 2), -1)
    return [cx - bw / 2 - hr / s, fy - leg - bh - hr / s, bw + 2 * hr / s, leg + bh + hr / s]


def draw_rock(img, cx, distance, ambient):
    fy = feet_row(distance)
    s = SS
    w, h = px(0.9, distance), px(0.5, distance)
    cv2.ellipse(img, (int(cx * s), int((fy - h / 2) * s)),
                (max(1, int(w / 2 * s)), max(1, int(h / 2 * s))), 0, 0, 360, float(ambient + 10.0), -1)
    return [cx - w / 2, fy - h, w, h]


def draw_trunk(img, cx, near_distance, ambient, rng, width_px=None):
    """Foreground trunk/sapling that can occlude objects behind it."""
    s = SS
    w = px(0.3, near_distance) if width_px is None else width_px
    t = ambient + rng.uniform(-0.5, 0.8)
    x0, x1 = int((cx - w / 2) * s), int((cx + w / 2) * s)
    cv2.rectangle(img, (x0, 0), (x1, PANO_H * s), float(t), -1)


def build_world(rng, ambient):
    scene = build_background(rng, ambient)
    hr = cv2.resize(scene, (PANO_W * SS, PANO_H * SS), interpolation=cv2.INTER_NEAREST)

    # objects in world (panorama) coordinates; the camera pans across them
    objects = [
        dict(kind="person", cx=95, d=8.0, pose="standing"),
        dict(kind="person", cx=180, d=15.0, pose="sitting"),
        dict(kind="person", cx=250, d=22.0, pose="standing", occluded=True),
        dict(kind="person", cx=330, d=12.0, pose="prone"),
        dict(kind="person", cx=400, d=35.0, pose="standing"),
        dict(kind="person", cx=455, d=50.0, pose="standing"),
        dict(kind="deer", cx=140, d=18.0),
        dict(kind="rock", cx=300, d=9.0),
    ]
    gt = []
    for o in objects:
        if o["kind"] == "person":
            box = draw_person(hr, o["cx"], o["d"], o["pose"], ambient, rng)
        elif o["kind"] == "deer":
            box = draw_deer(hr, o["cx"], o["d"], ambient)
        else:
            box = draw_rock(hr, o["cx"], o["d"], ambient)
        gt.append(dict(kind=o["kind"], distance_m=o["d"], pose=o.get("pose"),
                    occluded=bool(o.get("occluded")), box=box))
        if o.get("occluded"):
            # sapling in front covering ~45% of the person's width (left side)
            draw_trunk(hr, o["cx"] - box[2] * 0.27, 3.0, ambient, rng, width_px=box[2] * 0.45)

    # a few more trunks for clutter
    for cx in rng.uniform(0, PANO_W, 5):
        draw_trunk(hr, cx, rng.uniform(4, 12), ambient, rng)

    world = cv2.resize(hr, (PANO_W, PANO_H), interpolation=cv2.INTER_AREA)
    return world, gt


def camera_offset(t, rng_phase):
    """Top-left of the camera window in panorama px at frame t (shoulder motion)."""
    sec = t / FPS
    pan = (PANO_W - W) / 2 + (PANO_W - W) / 2 * 0.95 * np.sin(2 * np.pi * sec / 30.0 + rng_phase)
    sway = 5.0 * np.sin(2 * np.pi * 0.9 * sec)           # side-to-side with stride
    bounce = 2.5 * np.sin(2 * np.pi * 1.8 * sec + 0.7)   # vertical bounce each step
    x = pan + sway
    y = (HORIZON - 45) + bounce
    return x, y


def generate(n_frames=300, seed=1, ambient=10.0, ffc_every=200, ffc_len=3):
    rng = np.random.default_rng(seed)
    world, gt_world = build_world(rng, ambient)
    fpn = rng.normal(0, 0.03, (H, W)).astype(np.float32)     # fixed-pattern noise
    phase = rng.uniform(0, 2 * np.pi)

    frames = np.zeros((n_frames, H, W), np.uint16)
    ffc = np.zeros(n_frames, bool)
    gt_frames = []
    prev = None
    for t in range(n_frames):
        in_ffc = ffc_every > 0 and t > 0 and (t % ffc_every) < ffc_len
        x, y = camera_offset(t, phase)
        if in_ffc and prev is not None:
            frames[t] = prev            # image freezes during the shutter event
            ffc[t] = True
        else:
            M = np.float32([[1, 0, -x], [0, 1, -y]])
            img = cv2.warpAffine(world, M, (W, H), flags=cv2.INTER_LINEAR,
                                borderMode=cv2.BORDER_REFLECT)
            img = cv2.GaussianBlur(img, (0, 0), 0.6)           # optics
            img = img + fpn + rng.normal(0, 0.05, (H, W)).astype(np.float32)  # NETD
            frames[t] = c_to_ck(img)
            prev = frames[t]

        # transient single-frame flicker (sunlit leaf / bird / noise burst)
        if not in_ffc and rng.random() < 0.08:
            fx, fy_ = rng.integers(5, W - 5), rng.integers(HORIZON - 40, H - 5)
            patch = frames[t, fy_:fy_ + 2, fx:fx + 2].astype(np.float32)
            frames[t, fy_:fy_ + 2, fx:fx + 2] = c_to_ck(np.full_like(patch, ambient + 12, dtype=np.float32))

        objs = []
        for i, g in enumerate(gt_world):
            bx, by, bw, bh = g["box"]
            fb = [bx - x, by - y, bw, bh]
            visible = fb[0] + fb[2] > 0 and fb[0] < W and fb[1] + fb[3] > 0 and fb[1] < H
            if visible:
                objs.append(dict(id=i, kind=g["kind"], distance_m=g["distance_m"], pose=g["pose"],
                                occluded=g["occluded"], box=[round(v, 2) for v in fb]))
        gt_frames.append(objs)
    return frames, ffc, gt_frames


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="sample.npz")
    ap.add_argument("--frames", type=int, default=300)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--ambient", type=float, default=10.0, help="ambient air temp, C")
    args = ap.parse_args()
    frames, ffc, gt = generate(args.frames, args.seed, args.ambient)
    np.savez_compressed(args.out, frames=frames, ffc=ffc, gt=json.dumps(gt),
                        meta=json.dumps(dict(fps=FPS, hfov_deg=HFOV_DEG, ambient_c=args.ambient)))
    print(f"wrote {args.out}: {frames.shape[0]} frames, {ffc.sum()} FFC frames")


if __name__ == "__main__":
    main()