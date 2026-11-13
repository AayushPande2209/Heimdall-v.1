"""
Heimdall pipeline: ties the detector and tracker together, one frame at a time.

    pipe = HeimdallPipeline()
    for raw, ffc_active in frames:          # raw = uint16 centikelvin from the Lepton
        out = pipe.process(raw, ffc_active)
        for t in out["alerts"]:
            ...                              # bearing, confidence, bbox
"""
import time

import numpy as np

from hotspot import HFOV_DEG, DetectorConfig, HotspotDetector, raw_to_celsius
from tracker import MotionEstimator, Tracker, TrackerConfig


class HeimdallPipeline:
    def __init__(self, det_cfg: DetectorConfig | None = None, trk_cfg: TrackerConfig | None = None,
                 min_alert_score: float = 0.55):
        self.detector = HotspotDetector(det_cfg)
        self.trk_cfg = trk_cfg or TrackerConfig()
        self.motion = MotionEstimator(self.trk_cfg)
        self.tracker = Tracker(self.trk_cfg)
        self.min_alert_score = min_alert_score

    def process(self, raw: np.ndarray, ffc_active: bool = False):
        t0 = time.perf_counter()
        if ffc_active:
            # Shutter is closed / image frozen: skip, don't age tracks, and
            # forget the previous frame so the next shift estimate isn't
            # computed against a stale image.
            self.motion.reset()
            return dict(blobs=[], alerts=[], shift=(0.0, 0.0), skipped=True,
                        ms=(time.perf_counter() - t0) * 1000)

        blobs, dbg = self.detector.detect(raw, return_debug=True)
        shift, resp = self.motion.update(dbg["temp"])
        confirmed = self.tracker.update(blobs, shift)
        alerts = []
        for t in confirmed:
            if t.score < self.min_alert_score:
                continue
            # bearing relative to the camera's centre line, degrees (+ = right)
            bearing = (t.x - 80) * HFOV_DEG / 160
            alerts.append(dict(track_id=t.id, bbox=t.bbox, x=t.x, y=t.y,
                            score=round(t.score, 3), bearing_deg=round(bearing, 1)))
        return dict(blobs=blobs, alerts=alerts, shift=shift, phase_resp=resp, skipped=False,
                    debug=dbg, ms=(time.perf_counter() - t0) * 1000)