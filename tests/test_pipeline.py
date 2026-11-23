"""Hardware-independent pipeline smoke tests."""
import numpy as np

from heimdall.pipeline import HeimdallPipeline


def test_uniform_frame_has_no_candidates_or_alerts():
    frame = np.full((120, 160), 28_315, dtype=np.uint16)
    output = HeimdallPipeline().process(frame)
    assert output["skipped"] is False
    assert output["blobs"] == []
    assert output["alerts"] == []
