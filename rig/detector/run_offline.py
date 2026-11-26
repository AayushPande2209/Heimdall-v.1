#!/usr/bin/env python3
"""Run the complete Heimdall detector on a saved Lepton recording."""

import argparse
import json
import os
from pathlib import Path
import statistics
import sys
import time

import cv2
import numpy as np

HOME = Path.home()
sys.path.insert(0, str(HOME))

from det.crop_classifier import CropClassifier
from det.hotspot import raw_to_celsius
from det.pipeline import HeimdallPipeline


FRAME_SHAPE = (120, 160)
FRAME_BYTES = FRAME_SHAPE[0] * FRAME_SHAPE[1] * np.dtype("<u2").itemsize


def recording_paths(value):
    candidate = Path(value).expanduser()
    raw = candidate if candidate.suffix == ".raw" else HOME / "rec" / (value + ".raw")
    timestamps = raw.with_suffix(".txt")
    return raw, timestamps


def thermal_details(alert, blobs):
    if not blobs:
        return {}
    ax, ay, aw, ah = alert["bbox"]
    center = (float(ax) + float(aw) / 2, float(ay) + float(ah) / 2)
    blob = min(blobs, key=lambda b: (b.x - center[0]) ** 2 + (b.y - center[1]) ** 2)
    return {
        "peak_c": round(blob.peak_c, 2),
        "mean_c": round(blob.mean_c, 2),
        "mean_delta_c": round(blob.mean_delta, 2),
        "estimated_range_m": round(blob.est_range_m, 1),
        "area_px": blob.area,
    }


def annotated_image(raw, alerts, label):
    temp = raw_to_celsius(raw)
    lo, hi = np.percentile(temp, (2, 98))
    gray = np.clip((temp - lo) * (255.0 / max(hi - lo, 0.01)), 0, 255).astype(np.uint8)
    image = cv2.applyColorMap(gray, cv2.COLORMAP_INFERNO)
    image = cv2.resize(image, (640, 480), interpolation=cv2.INTER_NEAREST)
    for alert in alerts:
        x, y, w, h = alert["bbox"]
        p1 = (round(float(x) * 4), round(float(y) * 4))
        p2 = (round((float(x) + float(w)) * 4), round((float(y) + float(h)) * 4))
        cv2.rectangle(image, p1, p2, (0, 255, 0), 2)
        text = f"id={alert['track_id']} hot={alert['score']:.2f} cnn={alert.get('cnn')}"
        cv2.putText(image, text, (p1[0], max(18, p1[1] - 5)), cv2.FONT_HERSHEY_SIMPLEX,
                    0.45, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(image, label, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                (255, 255, 255), 1, cv2.LINE_AA)
    return image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("recording", help="recording name in ~/rec, or path to .raw")
    parser.add_argument("--model", default=str(HOME / "det" / "heimdall_cnn_full.onnx"))
    parser.add_argument("--cutoff", type=float, default=0.5)
    parser.add_argument("--max-frames", type=int, default=0, help="0 processes the full recording")
    parser.add_argument("--annotated", type=int, default=6)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    raw_path, timestamp_path = recording_paths(args.recording)
    if not raw_path.is_file() or not timestamp_path.is_file():
        raise FileNotFoundError(f"missing {raw_path} or {timestamp_path}")
    raw_size = raw_path.stat().st_size
    if raw_size % FRAME_BYTES:
        raise ValueError(f"raw size is not an exact frame multiple: {raw_size}")
    raw_count = raw_size // FRAME_BYTES
    timestamps = np.atleast_1d(np.loadtxt(timestamp_path, dtype=np.float64))
    if raw_count != len(timestamps):
        raise ValueError(f"raw/timestamp mismatch: {raw_count} vs {len(timestamps)}")
    count = raw_count if args.max_frames <= 0 else min(raw_count, args.max_frames)
    frames = np.memmap(raw_path, mode="r", dtype="<u2", shape=(raw_count,) + FRAME_SHAPE)

    output = Path(args.output).expanduser() if args.output else HOME / "det" / "output" / raw_path.stem
    output.mkdir(parents=True, exist_ok=True)
    log_path = output / "detections.jsonl"
    summary_path = output / "summary.json"

    classifier = CropClassifier(args.model, cutoff=args.cutoff)
    pipeline = HeimdallPipeline(classifier=classifier)
    processing_ms = []
    alert_rows = 0
    alert_frames = 0
    track_ids = set()
    saved = 0
    wall_start = time.perf_counter()
    cpu_start = time.process_time()
    with log_path.open("w", buffering=1024 * 1024) as log:
        for index in range(count):
            raw = np.asarray(frames[index])
            result = pipeline.process(raw)
            processing_ms.append(float(result["ms"]))
            enriched = []
            for alert in result["alerts"]:
                row = {
                    "timestamp": round(float(timestamps[index]), 4),
                    "frame_index": index,
                    "track_id": int(alert["track_id"]),
                    "bbox": [round(float(v), 2) for v in alert["bbox"]],
                    "score": float(alert["score"]),
                    "cnn": alert.get("cnn"),
                    "bearing_deg": float(alert["bearing_deg"]),
                }
                row.update(thermal_details(alert, result["blobs"]))
                log.write(json.dumps(row, separators=(",", ":")) + "\n")
                enriched.append(row)
                alert_rows += 1
                track_ids.add(row["track_id"])
            if enriched:
                alert_frames += 1
                if saved < args.annotated:
                    label = f"frame {index}  t={timestamps[index]:.2f}s"
                    cv2.imwrite(str(output / f"alert_{saved + 1:02d}_frame_{index}.png"),
                                annotated_image(raw, enriched, label))
                    saved += 1

    cpu_seconds = time.process_time() - cpu_start
    wall_seconds = time.perf_counter() - wall_start
    if saved < args.annotated:
        preview_indices = np.linspace(0, count - 1, args.annotated - saved, dtype=int)
        for index in preview_indices:
            label = f"frame {index}  t={timestamps[index]:.2f}s  no logged alert"
            cv2.imwrite(str(output / f"preview_{saved + 1:02d}_frame_{index}.png"),
                        annotated_image(np.asarray(frames[index]), [], label))
            saved += 1

    duration_min = max(float(timestamps[count - 1] - timestamps[0]) / 60.0, 1e-9) if count > 1 else 0.0
    ordered = sorted(processing_ms)
    summary = {
        "recording": str(raw_path),
        "frames": count,
        "recording_minutes": round(duration_min, 4),
        "alert_rows": alert_rows,
        "alert_frames": alert_frames,
        "unique_track_ids": len(track_ids),
        "alerts_per_minute": round(alert_rows / duration_min, 3) if duration_min else 0.0,
        "unique_tracks_per_minute": round(len(track_ids) / duration_min, 3) if duration_min else 0.0,
        "processing_ms_mean": round(statistics.fmean(processing_ms), 3),
        "processing_ms_median": round(statistics.median(processing_ms), 3),
        "processing_ms_p95": round(ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))], 3),
        "processing_ms_max": round(max(processing_ms), 3),
        "wall_seconds": round(wall_seconds, 3),
        "throughput_fps": round(count / wall_seconds, 3),
        "cpu_seconds": round(cpu_seconds, 3),
        "cpu_percent_one_core_basis": round(cpu_seconds / wall_seconds * 100, 1),
        "cnn_cutoff": args.cutoff,
        "hotspot_cutoff": pipeline.min_alert_score,
        "jsonl": str(log_path),
        "annotated_pngs": saved,
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
