"""Frame sources for the field recorder.

Hardware imports are intentionally lazy so this module can be imported and
tested on machines without Raspberry Pi GPIO or SPI libraries.
"""
from __future__ import annotations

import numpy as np


class FakeSource:
    """Deterministic 160x120 centikelvin frames for development and CI."""

    def __init__(self, frame_limit: int = 8):
        if frame_limit < 1:
            raise ValueError("frame_limit must be positive")
        self.frame_limit = frame_limit
        self.completed_frames = 0
        self.invalid_segments = 0
        self.vsync_timeouts = 0

    def read(self):
        if self.completed_frames >= self.frame_limit:
            return None
        frame = np.full((120, 160), 28_315, dtype=np.uint16)
        frame[:, (self.completed_frames * 7) % 160] += 100
        self.completed_frames += 1
        return frame

    def resync(self):
        return None

    def close(self):
        return None


class LeptonSource:
    """FLIR Lepton source backed by the Raspberry Pi VSYNC/SPI capture code."""

    def __init__(self):
        from .lepton_grab import Stream

        self._stream = Stream()
        self._stream.hard()

    def read(self):
        from .lepton_grab import grab

        return grab(self._stream)

    def resync(self):
        self._stream.hard()

    def close(self):
        self._stream.close()

    def __getattr__(self, name):
        return getattr(self._stream, name)
