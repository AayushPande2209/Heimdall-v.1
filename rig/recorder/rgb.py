"""Nonblocking raw H.264 companion recorder for a thermal session."""
import json
import os
from pathlib import Path
import signal
import subprocess
import time


class RGBRecorder:
    def __init__(self, rec, name, width, height, fps, bitrate, log):
        self.rec = Path(rec)
        self.name = name
        self.log = log
        self.video = self.rec / f"{name}.rgb.h264"
        self.pts = self.rec / f"{name}.rgb.pts"
        self.metadata = self.rec / f"{name}.rgb.camera.json"
        self.stderr_path = self.rec / f"{name}.rgb.log"
        self.status_path = self.rec / f"{name}.rgb.status.json"
        self.width, self.height, self.fps, self.bitrate = width, height, fps, bitrate
        self.proc = None
        self.stderr = None
        self.start_monotonic_ns = None
        self.error = None

    def _status(self, state, detail=None):
        data = {"state": state, "detail": detail, "pid": self.proc.pid if self.proc else None}
        temporary = self.status_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data) + "\n")
        os.replace(temporary, self.status_path)

    def start(self):
        command = ["rpicam-vid", "--timeout", "0", "--nopreview", "--codec", "h264",
                   "--inline", "--width", str(self.width), "--height", str(self.height),
                   "--framerate", str(self.fps), "--bitrate", str(self.bitrate),
                   "--save-pts", str(self.pts), "--metadata", str(self.metadata),
                   "-o", str(self.video)]
        try:
            self.stderr = self.stderr_path.open("xb")
            self.start_monotonic_ns = time.monotonic_ns()
            self.proc = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=self.stderr,
                                         start_new_session=True)
            self._status("starting")
            self.log(f"RGB_START pid={self.proc.pid} command={' '.join(command)}")
        except Exception as exc:
            self.error = repr(exc)
            self._status("error", self.error)
            self.log(f"RGB_ERROR start: {self.error}")
            if self.stderr:
                self.stderr.close()
        return self.proc is not None

    def poll(self):
        if self.proc is not None and self.proc.poll() is not None and self.error is None:
            self.error = f"rpicam-vid exited {self.proc.returncode} during capture"
            self._status("error", self.error)
            self.log(f"RGB_ERROR {self.error}")

    def stop(self):
        if self.proc is not None and self.proc.poll() is None:
            self.proc.send_signal(signal.SIGINT)
            try:
                self.proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
                self.error = "rpicam-vid did not stop after SIGINT"
        if self.stderr:
            self.stderr.close()
        result = {"enabled": True, "command_start_monotonic_ns": self.start_monotonic_ns,
                  "width": self.width, "height": self.height, "fps_requested": self.fps,
                  "bitrate_requested": self.bitrate,
                  "exit_code": self.proc.returncode if self.proc else None,
                  "video": str(self.video), "pts": str(self.pts),
                  "camera_metadata": str(self.metadata)}
        try:
            pts = [float(line) for line in self.pts.read_text().splitlines() if line and not line.startswith("#")]
            camera = json.loads(self.metadata.read_text())
            sensors = [int(row["SensorTimestamp"]) for row in camera]
            result.update(pts_count=len(pts), camera_metadata_count=len(sensors),
                          first_sensor_monotonic_ns=sensors[0],
                          last_sensor_monotonic_ns=sensors[-1],
                          first_pts_ms=pts[0], last_pts_ms=pts[-1],
                          video_bytes=self.video.stat().st_size)
            if len(pts) != len(sensors) or not pts or not self.video.stat().st_size:
                raise RuntimeError("RGB PTS/metadata/video count mismatch or empty")
        except Exception as exc:
            self.error = self.error or repr(exc)
        for path in (self.video, self.pts, self.metadata):
            if path.exists():
                with path.open("rb") as handle:
                    os.fsync(handle.fileno())
        if self.proc is not None and self.proc.returncode != 0:
            self.error = self.error or f"rpicam-vid exit {self.proc.returncode}"
        result["error"] = self.error
        self._status("error" if self.error else "closed", self.error)
        self.log(f"RGB_STOP {json.dumps(result, separators=(',', ':'))}")
        return result
