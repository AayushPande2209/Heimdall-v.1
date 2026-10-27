"""
Heimdall hot-spot detector: single-frame stages 1-4.

1. Radiometric raw (centikelvin) -> degrees C, light denoise
2. Local background (median) and local noise (MAD) estimate
3. Dual threshold: human-plausible temperature band AND local contrast
4. Connected components -> blobs, each with features and a 0-1 score

No trained model needed. Everything is NumPy/OpenCV, sized for a Pi 4.
"""
from dataclasses import dataclass, field

import cv2
import numpy as np
from scipy.ndimage import median_filter

HFOV_DEG = 57.0
IFOV = np.deg2rad(HFOV_DEG) / 160      # radians per pixel


@dataclass
class DetectorConfig:
    # Stage 3: temperature band (apparent surface temp of a clothed person, C).
    # Wide on purpose: clothing reads cool, cold wind lowers it further.
    t_min: float = 12.0
    t_max: float = 40.0
    # Stage 3: contrast. A pixel must be min_delta C above background AND
    # k_sigma times the local noise level.
    min_delta: float = 3.0
    k_sigma: float = 3.0
    noise_floor: float = 0.15          # C; never trust noise estimates below this
    # Stage 2: background window in full-res pixels (computed at 1/4 res).
    bg_window: int = 32
    downsample: int = 4
    # Stage 4: blob size limits in pixels.
    min_area: int = 2
    max_area: int = 2500
    # Plausible person sizes for the distance estimate.
    person_height_m: float = 1.7
    max_range_m: float = 120.0


@dataclass
class Blob:
    x: float                 # centroid, px
    y: float
    bbox: tuple              # (x, y, w, h)
    area: int
    peak_c: float
    mean_c: float
    mean_delta: float        # mean contrast above background, C
    peak_z: float            # peak contrast in noise units
    aspect: float            # h / w
    fill: float              # area / bbox area
    est_range_m: float       # if upright person; inf if implausible
    score: float = 0.0
    features: dict = field(default_factory=dict)


def raw_to_celsius(raw: np.ndarray) -> np.ndarray:
    """Lepton TLinear (0.01 K resolution) -> degrees C as float32."""
    return raw.astype(np.float32) / 100.0 - 273.15


def estimate_background(temp_c: np.ndarray, cfg: DetectorConfig):
    """Robust local background and noise.

    Median over a large window ignores small hot objects (people), so the
    estimate is the scene behind them. Done at 1/4 resolution because a
    32x32 median at full res is too slow for a Pi; the background is smooth
    anyway, so nothing is lost.
    """
    d = cfg.downsample
    small = cv2.resize(temp_c, (temp_c.shape[1] // d, temp_c.shape[0] // d), interpolation=cv2.INTER_AREA)
    k = max(3, cfg.bg_window // d) | 1
    bg_small = median_filter(small, size=k, mode="nearest")
    # MAD: median absolute deviation, a robust noise measure (1.4826 makes it ~sigma)
    mad_small = 1.4826 * median_filter(np.abs(small - bg_small), size=k, mode="nearest")
    size = (temp_c.shape[1], temp_c.shape[0])
    bg = cv2.resize(bg_small, size, interpolation=cv2.INTER_LINEAR)
    noise = cv2.resize(mad_small, size, interpolation=cv2.INTER_LINEAR)
    return bg, np.maximum(noise, cfg.noise_floor)


def candidate_mask(temp_c, bg, noise, cfg: DetectorConfig):
    delta = temp_c - bg
    z = delta / noise
    in_band = (temp_c >= cfg.t_min) & (temp_c <= cfg.t_max)
    contrast = (delta >= cfg.min_delta) & (z >= cfg.k_sigma)
    mask = (in_band & contrast).astype(np.uint8)
    # join a head and body split by a pixel or two (thin branch, neck)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 3)))
    return mask, delta, z


def _plausibility(lo, hi, v, soft):
    """1 inside [lo, hi], falling off linearly to 0 over `soft` outside."""
    if v < lo:
        return max(0.0, 1 - (lo - v) / soft)
    if v > hi:
        return max(0.0, 1 - (v - hi) / soft)
    return 1.0


def score_blob(b: Blob, cfg: DetectorConfig) -> float:
    """Hand-weighted score in [0, 1]. Tune these weights on real recordings.

    Key idea: how much we trust *absolute temperature* depends on blob size.
    A person 3 px wide shares every pixel with the cold background, so the
    sensor reads a blend (e.g. 17 C instead of 30 C). For small blobs we lean
    on contrast; for big, well-resolved blobs temperature and a hot "core"
    (face/hands warmer than clothing) become strong evidence.
    """
    resolved = min(1.0, b.area / 40.0)       # 0 = a few px, 1 = well resolved
    # contrast: saturates around 8 C above background
    s_contrast = min(1.0, b.mean_delta / 8.0)
    # temperature: most human-like when peak is skin-ish (28-36 C)
    s_temp = _plausibility(26.0, 36.5, b.peak_c, 8.0)
    # hot core: people have a warmer head/hands than body; rocks are uniform
    s_core = min(1.0, max(0.0, (b.peak_c - b.mean_c) / 3.0))
    # shape: upright (aspect >= 1.5) or prone (<= 0.5) both OK; tiny blobs get
    # a neutral 0.5 because shape is meaningless at 1-3 px
    if b.area < 6:
        s_shape = 0.5
    else:
        upright = _plausibility(1.4, 4.5, b.aspect, 1.0)
        prone = _plausibility(0.15, 0.55, b.aspect, 0.3)
        s_shape = max(upright, prone, 0.4 * _plausibility(0.55, 1.4, b.aspect, 0.5))
    # compact blobs (filled bbox) are more person-like than streaks
    s_fill = _plausibility(0.35, 1.0, b.fill, 0.3)
    # range: blobs implying a person farther than max range are suspicious
    s_range = 1.0 if b.est_range_m <= cfg.max_range_m else 0.5
    w = dict(contrast=0.35, temp=0.2 * resolved, core=0.15 * resolved, shape=0.15, fill=0.05, range=0.1)
    s = dict(contrast=s_contrast, temp=s_temp, core=s_core, shape=s_shape, fill=s_fill, range=s_range)
    b.features = {k: round(v, 3) for k, v in s.items()}
    b.features["resolved"] = round(resolved, 2)
    return sum(w[k] * s[k] for k in w) / sum(w.values())


def find_blobs(mask, temp_c, delta, z, cfg: DetectorConfig):
    n, labels, stats, cents = cv2.connectedComponentsWithStats(mask, connectivity=8)
    blobs = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area < cfg.min_area or area > cfg.max_area:
            continue
        sel = labels[y:y + h, x:x + w] == i
        t = temp_c[y:y + h, x:x + w][sel]
        d = delta[y:y + h, x:x + w][sel]
        zz = z[y:y + h, x:x + w][sel]
        long_side = max(h, w)   # 1.7 m body length: height if upright, width if lying down
        est = cfg.person_height_m / (long_side * IFOV) if long_side > 0 else float("inf")
        b = Blob(x=float(cents[i][0]), y=float(cents[i][1]), bbox=(int(x), int(y), int(w), int(h)),
                area=int(area), peak_c=float(t.max()), mean_c=float(t.mean()),
                mean_delta=float(d.mean()), peak_z=float(zz.max()),
                 aspect=float(h) / float(w), fill=float(area) / float(w * h), est_range_m=float(est))
        b.score = score_blob(b, cfg)
        blobs.append(b)
    blobs.sort(key=lambda b: -b.score)
    return blobs


class HotspotDetector:
    def __init__(self, cfg: DetectorConfig | None = None):
        self.cfg = cfg or DetectorConfig()

    def detect(self, raw: np.ndarray, return_debug=False):
        temp = raw_to_celsius(raw)
        temp = cv2.GaussianBlur(temp, (3, 3), 0)                       # stage 1
        bg, noise = estimate_background(temp, self.cfg)                # stage 2
        mask, delta, z = candidate_mask(temp, bg, noise, self.cfg)     # stage 3
        blobs = find_blobs(mask, temp, delta, z, self.cfg)             # stage 4
        if return_debug:
            return blobs, dict(temp=temp, bg=bg, noise=noise, mask=mask, delta=delta)
        return blobs