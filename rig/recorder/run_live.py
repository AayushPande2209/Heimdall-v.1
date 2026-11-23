#!/usr/bin/env python3
"""Capture, record, and detect live Lepton frames without blocking capture."""

import argparse
import json
import multiprocessing as mp
import os
from pathlib import Path
import queue
import statistics
import sys
import threading
import time
import traceback

import numpy as np

HOME = Path.home()
sys.path.insert(0, str(HOME))

from lep_vsync import Stream, grab


def detector_worker(input_queue, result_queue, output_dir, model_path, cutoff, nice_value):
    try:
        if nice_value:
            os.nice(nice_value)
        os.environ.setdefault("OMP_NUM_THREADS", "1")
        os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
        from det.crop_classifier import CropClassifier
        from det.pipeline import HeimdallPipeline

        output = Path(output_dir)
        log_path = output / "detections.jsonl"
        classifier = CropClassifier(model_path, cutoff=cutoff)
        pipeline = HeimdallPipeline(classifier=classifier)
        processed = 0
        alert_rows = 0
        alert_frames = 0
        track_ids = set()
        processing_ms = []
        cpu_start = time.process_time()
        wall_start = time.perf_counter()
        with log_path.open("w", buffering=1024 * 1024) as log:
            while True:
                item = input_queue.get()
                if item is None:
                    break
                timestamp, raw = item
                result = pipeline.process(raw)
                processed += 1
                processing_ms.append(float(result["ms"]))
                if result["alerts"]:
                    alert_frames += 1
                for alert in result["alerts"]:
                    row = {
                        "timestamp": round(float(timestamp), 4),
                        "track_id": int(alert["track_id"]),
                        "bbox": [round(float(v), 2) for v in alert["bbox"]],
                        "score": float(alert["score"]),
                        "cnn": alert.get("cnn"),
                        "bearing_deg": float(alert["bearing_deg"]),
                    }
                    log.write(json.dumps(row, separators=(",", ":")) + "\n")
                    alert_rows += 1
                    track_ids.add(row["track_id"])
        wall_seconds = time.perf_counter() - wall_start
        cpu_seconds = time.process_time() - cpu_start
        ordered = sorted(processing_ms)
        result_queue.put({
            "processed_frames": processed,
            "alert_rows": alert_rows,
            "alert_frames": alert_frames,
            "unique_track_ids": len(track_ids),
            "processing_ms_mean": round(statistics.fmean(processing_ms), 3) if processing_ms else 0.0,
            "processing_ms_median": round(statistics.median(processing_ms), 3) if processing_ms else 0.0,
            "processing_ms_p95": round(ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))], 3)
            if ordered else 0.0,
            "processing_ms_max": round(max(processing_ms), 3) if processing_ms else 0.0,
            "detector_cpu_seconds": round(cpu_seconds, 3),
            "detector_wall_seconds": round(wall_seconds, 3),
            "detector_cpu_percent_one_core_basis": round(cpu_seconds / max(wall_seconds, 1e-9) * 100, 1),
            "cnn_cutoff": cutoff,
            "hotspot_cutoff": pipeline.min_alert_score,
            "jsonl": str(log_path),
        })
    except BaseException as exc:
        result_queue.put({"error": repr(exc), "traceback": traceback.format_exc()})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("duration", type=float, help="capture duration in seconds")
    parser.add_argument("name", help="new recording name under ~/rec")
    parser.add_argument("--model", default=str(HOME / "det" / "heimdall_cnn_full.onnx"))
    parser.add_argument("--cutoff", type=float, default=0.5)
    parser.add_argument("--detector-nice", type=int, default=5)
    args = parser.parse_args()

    rec_dir = HOME / "rec"
    rec_dir.mkdir(exist_ok=True)
    raw_path = rec_dir / f"{args.name}.raw"
    timestamp_path = rec_dir / f"{args.name}.txt"
    output_dir = HOME / "det" / "output" / args.name
    summary_path = output_dir / "live_summary.json"
    if raw_path.exists() or timestamp_path.exists() or output_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing output for {args.name}")
    output_dir.mkdir(parents=True)

    write_queue = queue.Queue()
    writer_errors = []

    def writer():
        try:
            with raw_path.open("wb", buffering=1024 * 1024) as raw_file, timestamp_path.open(
                "w", buffering=1024 * 1024
            ) as timestamp_file:
                raw_batch, timestamp_batch = [], []
                while True:
                    item = write_queue.get()
                    if item is None:
                        break
                    frame_bytes, elapsed = item
                    raw_batch.append(frame_bytes)
                    timestamp_batch.append(f"{elapsed:.4f}\n")
                    if len(raw_batch) >= 32:
                        raw_file.write(b"".join(raw_batch))
                        timestamp_file.write("".join(timestamp_batch))
                        raw_batch.clear()
                        timestamp_batch.clear()
                if raw_batch:
                    raw_file.write(b"".join(raw_batch))
                    timestamp_file.write("".join(timestamp_batch))
        except BaseException as exc:
            writer_errors.append(exc)

    detector_queue = mp.Queue(maxsize=2)
    detector_results = mp.Queue(maxsize=1)
    detector = mp.Process(
        target=detector_worker,
        args=(detector_queue, detector_results, str(output_dir), args.model, args.cutoff,
              args.detector_nice),
        name="heimdall-detector",
    )
    writer_thread = threading.Thread(target=writer, name="lepton-writer")
    detector.start()
    writer_thread.start()

    stream = Stream()
    stream.hard()
    frames = 0
    capture_resyncs = 0
    detector_drops = 0
    max_write_queue = 0
    max_detector_queue = 0
    main_cpu_start = time.process_time()
    started = time.time()
    print(f"recording and detecting {args.duration:.0f} s -> ~/rec/{args.name}", flush=True)
    try:
        while time.time() - started < args.duration:
            frame = grab(stream)
            if frame is None:
                capture_resyncs += 1
                stream.hard()
                continue
            elapsed = time.time() - started
            write_queue.put((frame.tobytes(), elapsed))
            max_write_queue = max(max_write_queue, write_queue.qsize())
            try:
                detector_queue.put_nowait((elapsed, np.array(frame, copy=True)))
                max_detector_queue = max(max_detector_queue, detector_queue.qsize())
            except queue.Full:
                detector_drops += 1
            frames += 1
            if frames % 50 == 0:
                print(f"  {frames} frames  {frames / elapsed:.1f} fps  detector drops {detector_drops}",
                      flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        elapsed = max(0.1, time.time() - started)
        stream.close()
        write_queue.put(None)
        writer_thread.join()
        detector_queue.put(None, timeout=10)
        detector.join(timeout=30)
        if detector.is_alive():
            detector.terminate()
            detector.join(timeout=5)
            raise RuntimeError("detector process did not stop cleanly")

    if writer_errors:
        raise writer_errors[0]
    if detector.exitcode != 0:
        raise RuntimeError(f"detector process exit code {detector.exitcode}")
    detector_summary = detector_results.get(timeout=5)
    if "error" in detector_summary:
        raise RuntimeError(detector_summary["error"] + "\n" + detector_summary["traceback"])

    capture_cpu_seconds = time.process_time() - main_cpu_start
    summary = {
        "recording": str(raw_path),
        "duration_seconds": round(elapsed, 3),
        "captured_frames": frames,
        "capture_fps": round(frames / elapsed, 3),
        "capture_resyncs": capture_resyncs,
        "max_write_queue": max_write_queue,
        "detector_queue_capacity": 2,
        "max_detector_queue": max_detector_queue,
        "detector_dropped_frames": detector_drops,
        "capture_cpu_seconds": round(capture_cpu_seconds, 3),
        "capture_cpu_percent_one_core_basis": round(capture_cpu_seconds / elapsed * 100, 1),
        "invalid_segments": getattr(stream, "invalid_segments", 0),
        "recoveries": getattr(stream, "recoveries", 0),
        "vsync_timeouts": getattr(stream, "vsync_timeouts", 0),
        "phase_corrections": getattr(stream, "phase_corrections", 0),
    }
    summary.update(detector_summary)
    summary["combined_cpu_percent_one_core_basis"] = round(
        summary["capture_cpu_percent_one_core_basis"]
        + summary["detector_cpu_percent_one_core_basis"], 1
    )
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
