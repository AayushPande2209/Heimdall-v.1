"""
Heimdall stage 5: motion compensation + tracking + confirmation.

The rig is on a shoulder, so the whole image shifts every frame. We estimate
that global shift (phase correlation on the thermal image; swap in IMU yaw/
pitch later), move every track by it, then match the new frame's blobs to
tracks. A track only becomes an alert once it has been seen in N of the last
M frames, which kills single-frame flicker and noise.
"""
from collections import deque
from dataclasses import dataclass, field
from itertools import count

import cv2
import numpy as np


@dataclass
class TrackerConfig:
    n_confirm: int = 5        # seen in at least N ...
    m_window: int = 8         # ... of the last M frames (~1 s at 8.7 Hz)
    gate_px: float = 6.0      # base match radius after motion compensation
    gate_scale: float = 0.6   # plus this fraction of the blob's larger side
    min_phase_response: float = 0.05   # below this, distrust the shift estimate


class MotionEstimator:
    """Global frame-to-frame shift via phase correlation."""

    def __init__(self, cfg: TrackerConfig):
        self.cfg = cfg
        self.prev = None
        self.win = cv2.createHanningWindow((160, 120), cv2.CV_32F)

    def _prep(self, temp_c):
        # normalise so a hot person doesn't dominate; we want the background structure
        lo, hi = np.percentile(temp_c, (2, 98))
        return np.clip((temp_c - lo) / max(hi - lo, 1e-3), 0, 1).astype(np.float32)

    def update(self, temp_c):
        cur = self._prep(temp_c)
        if self.prev is None or self.prev.shape != cur.shape:
            if cur.shape != self.win.shape:
                self.win = cv2.createHanningWindow((cur.shape[1], cur.shape[0]), cv2.CV_32F)
            self.prev = cur
            return (0.0, 0.0), 0.0
        (dx, dy), resp = cv2.phaseCorrelate(self.prev, cur, self.win)
        self.prev = cur
        if resp < self.cfg.min_phase_response:
            return (0.0, 0.0), resp
        return (dx, dy), resp

    def reset(self):
        self.prev = None


@dataclass
class Track:
    id: int
    x: float
    y: float
    bbox: tuple
    score: float
    hits: deque = field(default_factory=deque)
    age: int = 0
    confirmed: bool = False
    best_score: float = 0.0


class Tracker:
    def __init__(self, cfg: TrackerConfig | None = None):
        self.cfg = cfg or TrackerConfig()
        self.tracks: list[Track] = []
        self._ids = count(1)

    def _gate(self, t: Track):
        return self.cfg.gate_px + self.cfg.gate_scale * max(t.bbox[2], t.bbox[3])

    def update(self, blobs, shift):
        dx, dy = shift
        # 1. predict: move every track by the camera's apparent shift
        for t in self.tracks:
            t.x += dx
            t.y += dy
            bx, by, bw, bh = t.bbox
            t.bbox = (bx + dx, by + dy, bw, bh)

        # 2. greedy nearest-neighbour matching (fine for a handful of blobs)
        pairs = []
        for ti, t in enumerate(self.tracks):
            g = self._gate(t)
            for bi, b in enumerate(blobs):
                dist = np.hypot(b.x - t.x, b.y - t.y)
                if dist <= g:
                    pairs.append((dist, ti, bi))
        pairs.sort()
        used_t, used_b = set(), set()
        for dist, ti, bi in pairs:
            if ti in used_t or bi in used_b:
                continue
            used_t.add(ti)
            used_b.add(bi)
            t, b = self.tracks[ti], blobs[bi]
            t.x, t.y, t.bbox = b.x, b.y, b.bbox
            t.score = 0.6 * t.score + 0.4 * b.score       # smoothed score
            t.best_score = max(t.best_score, t.score)
            t.hits.append(1)

        # 3. unmatched tracks get a miss
        for ti, t in enumerate(self.tracks):
            if ti not in used_t:
                t.hits.append(0)

        # 4. new tracks for unmatched blobs
        for bi, b in enumerate(blobs):
            if bi not in used_b:
                t = Track(id=next(self._ids), x=b.x, y=b.y, bbox=b.bbox, score=b.score,
                        best_score=b.score, hits=deque([1], maxlen=self.cfg.m_window))
                self.tracks.append(t)

        # 5. confirm / drop
        alive = []
        for t in self.tracks:
            if t.hits.maxlen is None:
                t.hits = deque(t.hits, maxlen=self.cfg.m_window)
            t.age += 1
            if sum(t.hits) >= self.cfg.n_confirm:
                t.confirmed = True
            # drop if it has disappeared for most of the window, or left the frame
            recent_hits = sum(t.hits)
            gone = len(t.hits) == self.cfg.m_window and recent_hits == 0
            unconfirmed_stale = not t.confirmed and len(t.hits) == self.cfg.m_window and recent_hits < 2
            offscreen = t.x < -10 or t.x > 170 or t.y < -10 or t.y > 130
            if not (gone or unconfirmed_stale or offscreen):
                alive.append(t)
        self.tracks = alive
        return [t for t in self.tracks if t.confirmed and t.hits[-1] == 1]