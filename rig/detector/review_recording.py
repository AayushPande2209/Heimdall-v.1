#!/usr/bin/env python3
"""Summarize and render an existing Heimdall offline detector run."""

import argparse
from collections import defaultdict
import json
from pathlib import Path

import cv2
import numpy as np


FRAME_SHAPE = (120, 160)
FRAME_BYTES = 120 * 160 * 2
SCALE = 4


def group_summary(rows, cutoff):
    selected = [r for r in rows if r.get("cnn") is not None and float(r["cnn"]) >= cutoff]
    tracks = defaultdict(list)
    for row in selected:
        tracks[int(row["track_id"])].append(row)
    per_track = []
    for track_id in sorted(tracks):
        track_rows = sorted(tracks[track_id], key=lambda r: int(r["frame_index"]))
        per_track.append({
            "track_id": track_id,
            "rows": len(track_rows),
            "first_frame": int(track_rows[0]["frame_index"]),
            "first_time": float(track_rows[0]["timestamp"]),
            "last_frame": int(track_rows[-1]["frame_index"]),
            "last_time": float(track_rows[-1]["timestamp"]),
            "max_cnn": max(float(r["cnn"]) for r in track_rows),
            "max_area_px": max(int(r.get("area_px", 0)) for r in track_rows),
        })
    return {"cutoff": cutoff, "rows": len(selected), "tracks": len(per_track), "per_track": per_track}


def colorize(raw):
    temp = raw.astype(np.float32) / 100.0 - 273.15
    lo, hi = np.percentile(temp, (2, 98))
    gray = np.clip((temp - lo) * (255.0 / max(hi - lo, 0.01)), 0, 255).astype(np.uint8)
    image = cv2.applyColorMap(gray, cv2.COLORMAP_INFERNO)
    return cv2.resize(image, (160 * SCALE, 120 * SCALE), interpolation=cv2.INTER_NEAREST)


def draw_frame(raw, rows, frame_index, timestamp):
    image = colorize(raw)
    cv2.rectangle(image, (0, 0), (639, 32), (0, 0, 0), -1)
    cv2.putText(image, f"frame {frame_index}   t={timestamp:.3f}s", (8, 23),
                cv2.FONT_HERSHEY_SIMPLEX, 0.62, (255, 255, 255), 1, cv2.LINE_AA)
    for row in sorted(rows, key=lambda r: r.get("cnn") is None):
        cnn = row.get("cnn")
        green = cnn is not None and float(cnn) >= 0.5
        color = (0, 255, 0) if green else (150, 150, 150)
        x, y, w, h = (float(v) for v in row["bbox"])
        p1 = (round(x * SCALE), round(y * SCALE))
        p2 = (round((x + w) * SCALE), round((y + h) * SCALE))
        cv2.rectangle(image, p1, p2, color, 2)
        cnn_text = f"cnn={float(cnn):.3f}" if cnn is not None else "cnn=null"
        label = f"id={row['track_id']} {cnn_text} area={row.get('area_px', '?')}"
        text_y = max(43, p1[1] - 5)
        cv2.putText(image, label, (max(2, p1[0]), text_y), cv2.FONT_HERSHEY_SIMPLEX,
                    0.43, color, 1, cv2.LINE_AA)
    return image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--home", default=str(Path.home()))
    parser.add_argument("--top-frames", type=int, default=10)
    args = parser.parse_args()

    home = Path(args.home).expanduser()
    raw_path = home / "rec" / f"{args.name}.raw"
    timestamp_path = home / "rec" / f"{args.name}.txt"
    detections_path = home / "det" / "output" / args.name / "detections.jsonl"
    review_dir = home / "det" / "review" / args.name
    review_dir.mkdir(parents=True, exist_ok=True)

    size = raw_path.stat().st_size
    if size % FRAME_BYTES:
        raise ValueError("raw file has a partial frame")
    frame_count = size // FRAME_BYTES
    timestamps = np.atleast_1d(np.loadtxt(timestamp_path, dtype=np.float64))
    if len(timestamps) != frame_count:
        raise ValueError(f"raw/timestamp mismatch: {frame_count} vs {len(timestamps)}")
    frames = np.memmap(raw_path, mode="r", dtype="<u2", shape=(frame_count,) + FRAME_SHAPE)
    rows = [json.loads(line) for line in detections_path.read_text().splitlines() if line.strip()]
    by_frame = defaultdict(list)
    for row in rows:
        by_frame[int(row["frame_index"])].append(row)

    duration = float(timestamps[-1] - timestamps[0]) if frame_count > 1 else 0.0
    fps = (frame_count - 1) / duration if duration > 0 else 8.8
    summaries = [group_summary(rows, cutoff) for cutoff in (0.5, 0.7, 0.9)]
    summary = {
        "recording": args.name,
        "frame_numbering": "zero-based, matching detections.jsonl",
        "frames": frame_count,
        "duration_seconds": round(duration, 4),
        "video_fps": round(fps, 6),
        "all_pipeline_alert_rows": len(rows),
        "cnn_non_null_rows": sum(r.get("cnn") is not None for r in rows),
        "cnn_null_rows": sum(r.get("cnn") is None for r in rows),
        "threshold_summaries": summaries,
    }
    (review_dir / "review_summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    video_path = review_dir / f"{args.name}_review.mp4"
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (640, 480))
    if not writer.isOpened():
        raise RuntimeError("OpenCV could not open the MP4 writer")
    for frame_index in range(frame_count):
        writer.write(draw_frame(np.asarray(frames[frame_index]), by_frame[frame_index],
                                frame_index, float(timestamps[frame_index])))
    writer.release()
    if not video_path.is_file() or video_path.stat().st_size == 0:
        raise RuntimeError("MP4 was not written")

    frame_max_cnn = {}
    for row in rows:
        if row.get("cnn") is not None:
            idx = int(row["frame_index"])
            frame_max_cnn[idx] = max(frame_max_cnn.get(idx, float("-inf")), float(row["cnn"]))
    top = sorted(frame_max_cnn, key=lambda idx: (-frame_max_cnn[idx], idx))[:args.top_frames]
    for rank, frame_index in enumerate(top, 1):
        image = draw_frame(np.asarray(frames[frame_index]), by_frame[frame_index], frame_index,
                           float(timestamps[frame_index]))
        path = review_dir / f"top_{rank:02d}_cnn_{frame_max_cnn[frame_index]:.3f}_frame_{frame_index}.png"
        cv2.imwrite(str(path), image)
    for frame_index in [138, 139, 140, 141, 142, 143, 227]:
        if frame_index >= frame_count:
            raise IndexError(f"requested frame {frame_index} outside {frame_count} frames")
        image = draw_frame(np.asarray(frames[frame_index]), by_frame[frame_index], frame_index,
                           float(timestamps[frame_index]))
        cv2.imwrite(str(review_dir / f"requested_frame_{frame_index}.png"), image)

    print(json.dumps(summary, indent=2))
    print(f"video={video_path} size={video_path.stat().st_size}")
    print(f"pngs={len(list(review_dir.glob('*.png')))}")


if __name__ == "__main__":
    main()
