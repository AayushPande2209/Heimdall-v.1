#!/usr/bin/env python3
"""Boot supervisor, GPIO button and LED, session management."""
import configparser
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

HOME = Path.home()
from .lepton_gpio import read_words

stop = False
test_short = False
test_hold = False


def term(signum, frame):
    global stop
    stop = True


def test_signal(signum, frame):
    global test_short, test_hold
    if signum == signal.SIGUSR1:
        test_short = True
    else:
        test_hold = True


def config():
    c = configparser.ConfigParser()
    c.read_dict({"rig": {"auto_record": "on", "detection": "on", "hold_seconds": "2.0",
                          "button_pin": "26", "led_pin": "16", "minimum_free_gb": "1.0",
                          "session_dir": str(HOME / "rec")}})
    c.read(HOME / "rig.conf")
    return c["rig"]


def logger():
    log = logging.getLogger("heimdall-rig")
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    for handler in (logging.StreamHandler(sys.stdout),
                    RotatingFileHandler(HOME / "rig.log", maxBytes=5_000_000, backupCount=3)):
        handler.setFormatter(fmt)
        log.addHandler(handler)
    return log


class GPIO:
    def __init__(self, button, led, log):
        self.req = None
        self.log = log
        try:
            import gpiod
            settings_in = gpiod.LineSettings(direction=gpiod.line.Direction.INPUT,
                                            bias=gpiod.line.Bias.PULL_UP)
            settings_out = gpiod.LineSettings(direction=gpiod.line.Direction.OUTPUT,
                                             output_value=gpiod.line.Value.INACTIVE)
            self.req = gpiod.request_lines("/dev/gpiochip0", consumer="heimdall-rig",
                                           config={button: settings_in, led: settings_out})
            self.button = button
            self.led = led
            self.gpiod = gpiod
            log.info("GPIO ready: button=%s pull-up, LED=%s", button, led)
        except Exception as exc:
            log.error("GPIO unavailable: %r", exc)

    def pressed(self):
        if self.req is None:
            return False
        try:
            return self.req.get_value(self.button) == self.gpiod.line.Value.INACTIVE
        except Exception as exc:
            self.log.error("button read failed: %r", exc)
            return False

    def set_led(self, on):
        if self.req is not None:
            try:
                value = self.gpiod.line.Value.ACTIVE if on else self.gpiod.line.Value.INACTIVE
                self.req.set_value(self.led, value)
            except Exception as exc:
                self.log.error("LED write failed: %r", exc)

    def close(self):
        if self.req is not None:
            self.set_led(False)
            self.req.release()


def next_session(rec, detector):
    number = 1
    while True:
        name = f"session_{number:04d}"
        if not any(rec.glob(name + ".*")) and not (detector / name).exists():
            return name
        number += 1


def boot_count():
    path = HOME / "rig_boot_count"
    try:
        number = int(path.read_text()) + 1
    except (FileNotFoundError, ValueError):
        number = 1
    tmp = path.with_suffix(".tmp")
    tmp.write_text(str(number) + "\n")
    os.replace(tmp, path)
    return number


def ready():
    status = read_words(0x0002)[0]
    return not (status & 1) and not (status & 0xff00)


def marker(rec, name, frame, log):
    path = rec / f"{name}.markers.txt"
    with path.open("a") as out:
        out.write(f"{time.time():.3f} frame={frame} event=short_press\n")
        out.flush()
        os.fsync(out.fileno())
    log.info("short press marker session=%s frame=%s", name, frame)


def poweroff(log):
    log.info("button hold: requesting poweroff")
    if os.environ.get("RIG_TEST_POWEROFF_LOG"):
        Path(os.environ["RIG_TEST_POWEROFF_LOG"]).write_text("poweroff requested\n")
        return
    subprocess.run(["sudo", "-n", "/usr/bin/systemctl", "poweroff"], check=True)


def main():
    signal.signal(signal.SIGTERM, term)
    signal.signal(signal.SIGINT, term)
    signal.signal(signal.SIGUSR1, test_signal)
    signal.signal(signal.SIGUSR2, test_signal)
    cfg = config()
    log = logger()
    rec = Path(cfg["session_dir"]).expanduser()
    rec.mkdir(parents=True, exist_ok=True)
    gpio = GPIO(int(cfg["button_pin"]), int(cfg["led_pin"]), log)
    counter = boot_count()
    log.info("rig service started boot_count=%s; disconnected button is pulled high", counter)
    child = None
    name = None
    heartbeat = Path(os.environ.get("RUNTIME_DIRECTORY", "/tmp")) / "heimdall-rig-heartbeat"
    waiting_since = time.monotonic()
    last_retry = 0
    last_ready_check = 0
    error = False
    press_start = None
    held = False
    blink_until = 0
    shutting_down = False
    raw_pressed = False
    stable_pressed = False
    raw_since = time.monotonic()
    child_started = 0
    last_disk_check = 0
    try:
        while not stop:
            now = time.monotonic()
            if child is not None and child.poll() is not None:
                log.error("recorder exited code=%s session=%s", child.returncode, name)
                child = None
                name = None
                error = True
                last_retry = now
            global test_short, test_hold
            sample = gpio.pressed()
            if sample != raw_pressed:
                raw_pressed = sample
                raw_since = now
            if now - raw_since >= .05:
                stable_pressed = raw_pressed
            pressed = stable_pressed
            if test_short:
                test_short = False
                if child is not None and name:
                    try:
                        frame = int(heartbeat.read_text().split()[0])
                        marker(rec, name, frame, log)
                        blink_until = now + .15
                    except Exception as exc:
                        log.error("test marker failed: %r", exc)
            if test_hold:
                test_hold = False
                press_start = now - float(cfg["hold_seconds"])
                pressed = True
            if pressed and press_start is None:
                press_start = now
                held = False
            if pressed and press_start is not None and not held and now - press_start >= float(cfg["hold_seconds"]):
                held = True
                shutting_down = True
                for _ in range(3):
                    gpio.set_led(True); time.sleep(.1)
                    gpio.set_led(False); time.sleep(.1)
                try:
                    poweroff(log)
                except Exception as exc:
                    log.error("poweroff failed: %r", exc)
                    shutting_down = False
                    error = True
            if not pressed and press_start is not None:
                if not held and child is not None and name:
                    try:
                        frame = int(heartbeat.read_text().split()[0])
                        marker(rec, name, frame, log)
                        blink_until = now + .15
                    except Exception as exc:
                        log.error("marker failed: %r", exc)
                press_start = None
            if child is None and not shutting_down and cfg.getboolean("auto_record") and now - last_retry >= 10 and now - last_ready_check >= 1:
                last_ready_check = now
                free = shutil.disk_usage(rec).free
                if free < float(cfg["minimum_free_gb"]) * 1_000_000_000:
                    if not error:
                        log.error("disk below minimum free space: %s bytes", free)
                    error = True
                    last_retry = now
                else:
                    try:
                        if ready():
                            name = next_session(rec, HOME / "det" / "output")
                            if heartbeat.exists():
                                heartbeat.unlink()
                            command = [str(HOME / "det" / ".venv" / "bin" / "python"),
                                       "-m", "rig.recorder.recorder", name,
                                       "--session-dir", str(rec), "--heartbeat", str(heartbeat),
                                       "--boot-count", str(counter), "--detection", cfg["detection"]]
                            if cfg["detection"] == "on":
                                command.extend(["--model", str(HOME / "det" / "heimdall_cnn_full.onnx")])
                            child = subprocess.Popen(command)
                            child_started = now
                            log.info("started recorder pid=%s session=%s", child.pid, name)
                            error = False
                        elif now - waiting_since >= 60:
                            error = True
                            last_retry = now
                            log.error("Lepton CCI not ready after 60 seconds")
                    except Exception as exc:
                        if now - waiting_since >= 60:
                            error = True
                            last_retry = now
                            log.error("Lepton readiness failed: %r", exc)
            if child is not None and now - last_disk_check >= 5:
                last_disk_check = now
                free = shutil.disk_usage(rec).free
                if free < float(cfg["minimum_free_gb"]) * 1_000_000_000:
                    log.error("disk below minimum during recording: %s bytes; stopping session", free)
                    error = True
                    child.terminate()
            if child is not None and not heartbeat.exists() and now - child_started > 5:
                if not error:
                    log.error("capture has not produced a heartbeat for over 5 seconds")
                error = True
            if child is not None and heartbeat.exists():
                if time.time() - heartbeat.stat().st_mtime > 5:
                    if not error:
                        log.error("capture stalled for over 5 seconds")
                    error = True
                elif error:
                    log.info("capture heartbeat recovered")
                    error = False
            if not shutting_down:
                if error:
                    led = int(now * 10) % 2 == 0
                elif child is None:
                    led = int(now * 2) % 2 == 0
                else:
                    led = True
                if now < blink_until:
                    led = False
                gpio.set_led(led)
            time.sleep(.025)
    finally:
        log.info("stopping rig service")
        gpio.set_led(False)
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=100)
            except subprocess.TimeoutExpired:
                log.error("recorder failed to stop within 100 seconds")
                child.kill(); child.wait()
        gpio.close()
        log.info("rig service stopped")


if __name__ == "__main__":
    main()
