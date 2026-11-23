"""
Heimdall pipeline: ties the detector and tracker together, one frame at a time.

    pipe = HeimdallPipeline()
    for raw, ffc_active in frames:          # raw = uint16 centikelvin from the Lepton
        out = pipe.process(raw, ffc_active)
        for t in out["alerts"]:
            ...                              # bearing, confidence, bbox
"""
import time
from collections import deque

import numpy as np

from .hotspot import HFOV_DEG, DetectorConfig, HotspotDetector, raw_to_celsius
from .tracker import MotionEstimator, Tracker, TrackerConfig


class HeimdallPipeline:
    def __init__(self, det_cfg: DetectorConfig | None = None, trk_cfg: TrackerConfig | None = None,
                 min_alert_score: float = 0.55, classifier=None):
        self.detector = HotspotDetector(det_cfg)
        self.trk_cfg = trk_cfg or TrackerConfig()
        self.motion = MotionEstimator(self.trk_cfg)
        self.tracker = Tracker(self.trk_cfg)
        self.min_alert_score = min_alert_score
        self.classifier = classifier
        self.cnn_scores = {}

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
        if self.classifier is not None:
            live_ids = {t.id for t in self.tracker.tracks}
            for track_id in list(self.cnn_scores):
                if track_id not in live_ids:
                    del self.cnn_scores[track_id]
            matched = [t for t in self.tracker.tracks if t.hits[-1] == 1]
            probabilities = self.classifier.score(dbg["temp"], [t.bbox for t in matched])
            for track, probability in zip(matched, probabilities):
                if probability is not None:
                    self.cnn_scores.setdefault(track.id, deque(maxlen=8)).append(probability)
        alerts = []
        for t in confirmed:
            if t.score < self.min_alert_score:
                continue
            history = self.cnn_scores.get(t.id) if self.classifier is not None else None
            cnn_mean = float(np.mean(history)) if history is not None and len(history) >= 3 else None
            if self.classifier is not None and cnn_mean is not None and cnn_mean < self.classifier.cutoff:
                continue
            # bearing relative to the camera's centre line, degrees (+ = right)
            bearing = (t.x - 80) * HFOV_DEG / 160
            alert = dict(track_id=t.id, bbox=t.bbox, x=t.x, y=t.y,
                         score=round(t.score, 3), bearing_deg=round(bearing, 1))
            if self.classifier is not None:
                alert["cnn"] = round(cnn_mean, 3) if cnn_mean is not None else None
            alerts.append(alert)
        return dict(blobs=blobs, alerts=alerts, shift=shift, phase_resp=resp, skipped=False,
                    debug=dbg, ms=(time.perf_counter() - t0) * 1000)
