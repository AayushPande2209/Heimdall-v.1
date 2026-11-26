#!/usr/bin/env python3
"""Field recorder using the validated VSYNC capture and detector worker."""
import argparse
import json
import multiprocessing as mp
import os
from pathlib import Path
import queue
import signal
import sys
import threading
import time
import traceback

import numpy as np

from .run_live import detector_worker
from .rgb import RGBRecorder
from .sources import FakeSource, LeptonSource

FRAME_BYTES = 160 * 120 * 2
stop = threading.Event()


def request_stop(signum, frame):
    stop.set()


def atomic_json(path, value):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w") as handle:
        json.dump(value, handle, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def main(argv=None):
    stop.clear()
    parser = argparse.ArgumentParser()
    parser.add_argument("name", nargs="?", default="session_fake")
    parser.add_argument("--session-dir", type=Path, default=Path("sessions"))
    parser.add_argument("--heartbeat", type=Path)
    parser.add_argument("--boot-count", type=int, default=0)
    parser.add_argument("--detection", choices=("on", "off"), default="off")
    parser.add_argument("--model", type=Path)
    parser.add_argument("--record-rgb", choices=("on", "off"), default="off")
    parser.add_argument("--rgb-width", type=int, default=1536)
    parser.add_argument("--rgb-height", type=int, default=864)
    parser.add_argument("--rgb-fps", type=int, default=30)
    parser.add_argument("--rgb-bitrate", type=int, default=4000000)
    parser.add_argument("--press-monotonic", type=float)
    parser.add_argument("--fake", action="store_true", help="record deterministic fake frames")
    parser.add_argument("--frames", type=int, help="stop after this many frames")
    args = parser.parse_args(argv)
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    rec = args.session_dir.expanduser()
    rec.mkdir(parents=True, exist_ok=True)
    heartbeat = args.heartbeat or rec / f"{args.name}.heartbeat"
    raw_path = rec / f"{args.name}.raw"
    txt_path = rec / f"{args.name}.txt"
    meta_path = rec / f"{args.name}.meta.json"
    output_dir = rec / f"{args.name}.detections"
    if any(p.exists() for p in (raw_path, txt_path, meta_path, output_dir)):
        raise FileExistsError(args.name)
    if args.detection == "on":
        if args.model is None:
            parser.error("--model is required when detection is on")
        output_dir.mkdir(parents=True)
    started_wall = time.time()
    started_mono_ns = time.monotonic_ns()
    started_mono = started_mono_ns / 1_000_000_000
    meta = dict(session=args.name, boot_count=args.boot_count, started_wall_time=started_wall,
                wall_clock_trusted=False, detection=args.detection, status="recording", frame_count=0,
                thermal_timestamp_origin_monotonic_ns=started_mono_ns,
                rgb_requested=args.record_rgb == "on")
    atomic_json(meta_path, meta)
    write_queue = queue.Queue()
    writer_errors = []
    written = [0]

    def writer():
        try:
            with raw_path.open("xb", buffering=1024 * 1024) as raw, txt_path.open("x", buffering=1024 * 1024) as stamps:
                frames = []
                times = []
                last_sync = time.monotonic()

                def flush(sync):
                    if frames:
                        raw.write(b"".join(frames))
                        stamps.write("".join(times))
                        written[0] += len(frames)
                        frames.clear()
                        times.clear()
                    if sync:
                        raw.flush(); stamps.flush()
                        os.fsync(raw.fileno()); os.fsync(stamps.fileno())

                while True:
                    try:
                        item = write_queue.get(timeout=0.5)
                    except queue.Empty:
                        item = "tick"
                    if item is None:
                        break
                    if item != "tick":
                        frame_bytes, elapsed = item
                        frames.append(frame_bytes)
                        times.append(f"{elapsed:.4f}\n")
                    now = time.monotonic()
                    if len(frames) >= 32 or now - last_sync >= 5:
                        flush(now - last_sync >= 5)
                        if now - last_sync >= 5:
                            last_sync = now
                flush(True)
        except BaseException as exc:
            writer_errors.append(repr(exc))

    worker = None
    detector_queue = None
    detector_results = None
    if args.detection == "on":
        detector_queue = mp.Queue(maxsize=2)
        detector_results = mp.Queue(maxsize=1)
        worker = mp.Process(target=detector_worker,
                            args=(detector_queue, detector_results, str(output_dir),
                                  str(args.model), 0.5, 5))
        worker.start()
    writer_thread = threading.Thread(target=writer, name="lepton-writer")
    writer_thread.start()
    rgb = None
    if args.record_rgb == "on":
        rgb = RGBRecorder(rec, args.name, args.rgb_width, args.rgb_height,
                          args.rgb_fps, args.rgb_bitrate, lambda line: print(line, flush=True))
        rgb.start()
    source = None
    frames = resyncs = drops = 0
    max_gap = 0.0
    last_frame = None
    reason = "stopped"
    last_heartbeat = 0.0
    first_frame_latency = None
    try:
        meta["thermal_capture_start_monotonic_ns"] = time.monotonic_ns()
        source = FakeSource(args.frames or 8) if args.fake else LeptonSource()
        print(f"recording {args.name}", flush=True)
        while not stop.is_set():
            frame = source.read()
            if rgb is not None:
                rgb.poll()
            now = time.monotonic()
            if frame is None:
                if args.fake:
                    reason = "complete"
                    break
                resyncs += 1
                source.resync()
                continue
            elapsed = now - started_mono
            if first_frame_latency is None and args.press_monotonic is not None:
                first_frame_latency = round(now - args.press_monotonic, 3)
                print(f"FIRST_FRAME_LATENCY session={args.name} seconds={first_frame_latency}", flush=True)
            if last_frame is not None:
                max_gap = max(max_gap, now - last_frame)
            last_frame = now
            payload = frame.tobytes()
            if len(payload) != FRAME_BYTES:
                raise RuntimeError(f"partial frame: {len(payload)} bytes")
            write_queue.put((payload, elapsed))
            frames += 1
            if detector_queue is not None:
                try:
                    detector_queue.put_nowait((elapsed, np.array(frame, copy=True)))
                except queue.Full:
                    drops += 1
            if now - last_heartbeat >= 1:
                heartbeat_tmp = heartbeat.with_suffix(".tmp")
                heartbeat_tmp.write_text(f"{frames} {now}\n")
                os.replace(heartbeat_tmp, heartbeat)
                last_heartbeat = now
            if frames % 50 == 0:
                print(f"{frames} frames {frames / max(elapsed, .1):.2f} fps drops={drops}", flush=True)
        if reason == "stopped":
            reason = "signal"
    except BaseException as exc:
        reason = "error"
        print(f"capture error: {exc!r}\n{traceback.format_exc()}", file=sys.stderr, flush=True)
    finally:
        if source is not None:
            source.close()
        if rgb is not None:
            meta["rgb"] = rgb.stop()
        write_queue.put(None)
        writer_thread.join()
        if worker is not None:
            try:
                detector_queue.put(None, timeout=10)
                worker.join(timeout=30)
                if worker.is_alive():
                    worker.terminate(); worker.join(timeout=5)
                    reason = "detector_timeout"
            except BaseException as exc:
                reason = "detector_error"
                print(f"detector stop error: {exc!r}", file=sys.stderr, flush=True)
        if writer_errors or written[0] != frames:
            reason = "writer_error"
        elapsed = max(.001, time.monotonic() - started_mono)
        meta.update(status="closed" if reason in ("signal", "complete") else "error", stop_reason=reason,
                    ended_wall_time=time.time(), duration_seconds=round(elapsed, 3),
                    frame_count=frames, written_frames=written[0], fps=round(frames / elapsed, 3),
                    max_gap_seconds=round(max_gap, 4), capture_resyncs=resyncs,
                    press_to_first_frame_seconds=first_frame_latency,
                    detector_dropped_frames=drops, writer_errors=writer_errors,
                    invalid_segments=getattr(source, "invalid_segments", 0),
                    vsync_timeouts=getattr(source, "vsync_timeouts", 0))
        if detector_results is not None and not detector_results.empty():
            meta["detector_summary"] = detector_results.get()
        atomic_json(meta_path, meta)
        print(json.dumps(meta), flush=True)
    return 0 if reason in ("signal", "complete") else 1


if __name__ == "__main__":
    raise SystemExit(main())
