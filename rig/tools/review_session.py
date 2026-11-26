#!/usr/bin/env python3
"""Render thermal footage, detector boxes, markers, and optional synced RGB."""
import argparse
from bisect import bisect_left
from collections import defaultdict
import json
from pathlib import Path

import cv2
import numpy as np

FRAME_BYTES = 120 * 160 * 2


def nearest_index(values, target):
    pos = bisect_left(values, target)
    if pos <= 0:
        return 0
    if pos >= len(values):
        return len(values) - 1
    return pos if abs(values[pos] - target) < abs(values[pos - 1] - target) else pos - 1


def colorize(raw):
    celsius = raw.astype(np.float32) / 100 - 273.15
    lo, hi = np.percentile(celsius, (2, 98))
    gray = np.clip((celsius - lo) * 255 / max(hi - lo, .01), 0, 255).astype(np.uint8)
    image = cv2.applyColorMap(gray, cv2.COLORMAP_INFERNO)
    return cv2.resize(image, (640, 480), interpolation=cv2.INTER_NEAREST)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("--rgb", action="store_true", help="place RGB beside thermal on the common clock")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    directory = args.session_dir.expanduser()
    metas = sorted(directory.glob("session_*.meta.json"))
    if len(metas) != 1:
        parser.error("session directory must contain exactly one session_*.meta.json")
    name = metas[0].name.removesuffix(".meta.json")
    meta = json.loads(metas[0].read_text())
    raw_path = directory / f"{name}.raw"
    stamp_path = directory / f"{name}.txt"
    size = raw_path.stat().st_size
    if size % FRAME_BYTES:
        raise ValueError("partial thermal frame")
    count = size // FRAME_BYTES
    stamps = [float(line) for line in stamp_path.read_text().splitlines() if line.strip()]
    if len(stamps) != count:
        raise ValueError(f"thermal raw/timestamp mismatch {count}/{len(stamps)}")
    frames = np.memmap(raw_path, dtype="<u2", mode="r", shape=(count, 120, 160))
    by_frame = defaultdict(list)
    candidates = [directory / f"{name}.detections" / "detections.jsonl",
                  directory / "detector" / "detections.jsonl"]
    for path in candidates:
        if path.exists():
            for line in path.read_text().splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                idx = int(row["frame_index"]) if "frame_index" in row else nearest_index(stamps, float(row["timestamp"]))
                by_frame[idx].append(row)
            break
    markers = set()
    marker_path = directory / f"{name}.markers.txt"
    if marker_path.exists():
        for line in marker_path.read_text().splitlines():
            for token in line.split():
                if token.startswith("frame="):
                    markers.add(int(token.split("=", 1)[1]))
    rgb_path = directory / f"{name}.rgb.h264"
    rgb_camera = directory / f"{name}.rgb.camera.json"
    use_rgb = args.rgb and rgb_path.exists() and rgb_camera.exists()
    rgb_times = []
    capture = None
    rgb_index = -1
    rgb_image = None
    if use_rgb:
        camera_rows = json.loads(rgb_camera.read_text())
        rgb_times = [row["SensorTimestamp"] / 1e9 for row in camera_rows]
        capture = cv2.VideoCapture(str(rgb_path))
        if not capture.isOpened() or not rgb_times:
            raise RuntimeError("RGB video or timestamps could not be opened")
    thermal_origin = float(meta["thermal_timestamp_origin_monotonic_ns"]) / 1e9
    fps = (count - 1) / (stamps[-1] - stamps[0]) if count > 1 else 8.8
    output = args.output or directory / f"{name}.review.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)
    width = 1280 if use_rgb else 640
    writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, 480))
    if not writer.isOpened():
        raise RuntimeError("OpenCV MP4 writer failed")
    try:
        for idx in range(count):
            image = colorize(frames[idx])
            cv2.rectangle(image, (0, 0), (640, 36), (0, 0, 0), -1)
            label = f"{name} frame {idx}  t={stamps[idx]:.2f}s"
            if idx in markers:
                label += "  MARKER"
            cv2.putText(image, label, (8, 25), cv2.FONT_HERSHEY_SIMPLEX, .55, (255, 255, 255), 1, cv2.LINE_AA)
            for row in by_frame[idx]:
                cnn = row.get("cnn")
                green = cnn is not None and float(cnn) >= .5
                color = (0, 255, 0) if green else (160, 160, 160)
                x, y, w, h = [float(v) for v in row["bbox"]]
                cv2.rectangle(image, (round(x * 4), round(y * 4)),
                              (round((x + w) * 4), round((y + h) * 4)), color, 2)
                cv2.putText(image, f"id {row['track_id']} cnn {cnn}",
                            (max(0, round(x * 4)), max(50, round(y * 4) - 4)),
                            cv2.FONT_HERSHEY_SIMPLEX, .38, color, 1, cv2.LINE_AA)
            if use_rgb:
                target = nearest_index(rgb_times, thermal_origin + stamps[idx])
                while rgb_index < target:
                    ok, frame = capture.read()
                    if not ok:
                        break
                    rgb_index += 1
                    rgb_image = cv2.resize(frame, (640, 480))
                right = rgb_image if rgb_image is not None else np.zeros_like(image)
                right = right.copy()
                cv2.rectangle(right, (0, 0), (640, 36), (0, 0, 0), -1)
                offset = rgb_times[max(0, rgb_index)] - (thermal_origin + stamps[idx]) if rgb_index >= 0 else 0
                cv2.putText(right, f"RGB frame {rgb_index}  offset {offset:+.3f}s", (8, 25),
                            cv2.FONT_HERSHEY_SIMPLEX, .55, (255, 255, 255), 1, cv2.LINE_AA)
                image = np.hstack((image, right))
            writer.write(image)
    finally:
        writer.release()
        if capture:
            capture.release()
    print(json.dumps({"session": name, "thermal_frames": count, "fps": round(fps, 3),
                      "rgb_frames_metadata": len(rgb_times), "markers": len(markers),
                      "output": str(output), "bytes": output.stat().st_size}, indent=2))


if __name__ == "__main__":
    main()
