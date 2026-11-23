"""Recorder tests that run without Raspberry Pi hardware."""
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from rig.recorder import recorder
from rig.recorder.sources import FakeSource


class FakeSourceTests(unittest.TestCase):
    def test_fake_source_shape_type_and_limit(self):
        source = FakeSource(frame_limit=2)
        first = source.read()
        second = source.read()
        self.assertEqual(first.shape, (120, 160))
        self.assertEqual(first.dtype, np.uint16)
        self.assertFalse(np.array_equal(first, second))
        self.assertIsNone(source.read())


class RecorderTests(unittest.TestCase):
    def test_fake_recording_writes_complete_session(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = recorder.main([
                "test_session",
                "--fake",
                "--frames", "4",
                "--session-dir", str(root),
            ])
            self.assertEqual(result, 0)
            self.assertEqual((root / "test_session.raw").stat().st_size, 4 * 120 * 160 * 2)
            self.assertEqual(len((root / "test_session.txt").read_text().splitlines()), 4)
            metadata = json.loads((root / "test_session.meta.json").read_text())
            self.assertEqual(metadata["status"], "closed")
            self.assertEqual(metadata["stop_reason"], "complete")
            self.assertEqual(metadata["frame_count"], 4)
            self.assertEqual(metadata["written_frames"], 4)


if __name__ == "__main__":
    unittest.main()
