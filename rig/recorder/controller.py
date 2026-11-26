#!/usr/bin/env python3
"""Heimdall field controller: boot to READY, press to record, hold to power off."""
import configparser
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

from .lepton_gpio import read_words

HOME = Path.home()
terminate = False
short_events = 0
hold_events = 0


def on_term(signum, frame):
    global terminate
    terminate = True


def on_test_signal(signum, frame):
    global short_events, hold_events
    if signum == signal.SIGUSR1:
        short_events += 1
    else:
        hold_events += 1


def load_config():
    parser = configparser.ConfigParser()
    parser.read_dict({"rig": {"auto_record_on_boot": "false", "detection": "on",
                              "hold_seconds": "2.0", "button_pin": "26", "led_pin": "16",
                              "minimum_free_gb": "1.0", "session_dir": str(HOME / "rec"),
                              "record_rgb": "true", "rgb_width": "1536", "rgb_height": "864",
                              "rgb_fps": "30", "rgb_bitrate": "4000000"}})
    parser.read(HOME / "rig.conf")
    return parser["rig"]


def make_logger():
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
            self.gpiod = gpiod
            self.button = button
            self.led = led
            self.req = gpiod.request_lines(
                "/dev/gpiochip0", consumer="heimdall-rig",
                config={button: gpiod.LineSettings(direction=gpiod.line.Direction.INPUT,
                                                   bias=gpiod.line.Bias.PULL_UP),
                        led: gpiod.LineSettings(direction=gpiod.line.Direction.OUTPUT,
                                               output_value=gpiod.line.Value.INACTIVE)})
            log.info("GPIO ready: button BCM%s pull-up, LED BCM%s", button, led)
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

    def led_on(self, on):
        if self.req is not None:
            try:
                value = self.gpiod.line.Value.ACTIVE if on else self.gpiod.line.Value.INACTIVE
                self.req.set_value(self.led, value)
            except Exception as exc:
                self.log.error("LED write failed: %r", exc)

    def close(self):
        if self.req is not None:
            self.led_on(False)
            self.req.release()


def next_session(rec, output):
    number = 1
    while True:
        name = f"session_{number:04d}"
        if not any(rec.glob(name + ".*")) and not (output / name).exists():
            return name
        number += 1


def boot_count():
    path = HOME / "rig_boot_count"
    try:
        value = int(path.read_text()) + 1
    except (FileNotFoundError, ValueError):
        value = 1
    temp = path.with_suffix(".tmp")
    temp.write_text(f"{value}\n")
    os.replace(temp, path)
    return value


def lepton_ready():
    status = read_words(0x0002)[0]
    if status & 0xff01:
        raise RuntimeError(f"Lepton CCI status 0x{status:04x}")


def marker(rec, name, frame, log):
    path = rec / f"{name}.markers.txt"
    with path.open("a") as output:
        output.write(f"{time.time():.3f} frame={frame} event=short_press\n")
        output.flush()
        os.fsync(output.fileno())
    log.info("MARKER session=%s frame=%s", name, frame)


def request_poweroff(log):
    log.info("POWER_OFF requested")
    test_log = os.environ.get("RIG_TEST_POWEROFF_LOG")
    if test_log:
        Path(test_log).write_text("poweroff requested\n")
        return
    subprocess.run(["sudo", "-n", "/usr/bin/systemctl", "poweroff"], check=True)


def ready_led(now):
    phase = now % 2.0
    return phase < .12 or .30 <= phase < .42


def main():
    global short_events, hold_events
    signal.signal(signal.SIGTERM, on_term)
    signal.signal(signal.SIGINT, on_term)
    signal.signal(signal.SIGUSR1, on_test_signal)
    signal.signal(signal.SIGUSR2, on_test_signal)
    cfg = load_config()
    log = make_logger()
    rec = Path(cfg["session_dir"]).expanduser()
    rec.mkdir(parents=True, exist_ok=True)
    gpio = GPIO(int(cfg["button_pin"]), int(cfg["led_pin"]), log)
    boot = boot_count()
    heartbeat = Path(os.environ.get("RUNTIME_DIRECTORY", "/tmp")) / "heimdall-rig-heartbeat"
    child = None
    session = None
    error = False
    shutdown = False
    expected_stop = False
    ignore_until = 0.0
    blink_until = 0.0
    raw_pressed = stable_pressed = False
    raw_since = time.monotonic()
    pressed_since = None
    hold_fired = False
    auto = cfg.getboolean("auto_record_on_boot")
    next_auto_try = time.monotonic()
    auto_wait_started = time.monotonic()
    child_started = 0.0
    last_valid_heartbeat = 0.0
    last_disk_check = 0.0
    last_rgb_check = 0.0
    rgb_failed = False
    log.info("READY boot_count=%s auto_record_on_boot=%s", boot, auto)

    def start_session(now, source):
        nonlocal child, session, error, ignore_until, child_started, last_valid_heartbeat, rgb_failed
        if child is not None:
            return
        free = shutil.disk_usage(rec).free
        if free < cfg.getfloat("minimum_free_gb") * 1_000_000_000:
            error = True
            log.error("START_REJECTED disk free=%s bytes below threshold", free)
            return
        try:
            governor = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor").read_text().strip()
            if governor != "performance":
                raise RuntimeError(f"CPU governor is {governor}, waiting for performance")
            lepton_ready()
            session = next_session(rec, HOME / "det" / "output")
            heartbeat.unlink(missing_ok=True)
            command = [str(HOME / "det" / ".venv" / "bin" / "python"), "-m", "rig.recorder.recorder",
                       session, "--session-dir", str(rec), "--heartbeat", str(heartbeat),
                       "--boot-count", str(boot), "--detection", cfg["detection"],
                       "--press-monotonic", str(now),
                       "--record-rgb", "on" if cfg.getboolean("record_rgb") else "off",
                       "--rgb-width", cfg["rgb_width"], "--rgb-height", cfg["rgb_height"],
                       "--rgb-fps", cfg["rgb_fps"], "--rgb-bitrate", cfg["rgb_bitrate"]]
            if cfg["detection"] == "on":
                command += ["--model", str(HOME / "det" / "heimdall_cnn_full.onnx")]
            child = subprocess.Popen(command, cwd=HOME)
            child_started = time.monotonic()
            last_valid_heartbeat = child_started
            ignore_until = child_started + 1.0
            error = False
            rgb_failed = False
            log.info("START source=%s session=%s pid=%s", source, session, child.pid)
        except Exception as exc:
            child = None
            session = None
            if source == "auto" and now - auto_wait_started < 60:
                error = False
                log.info("AUTO_WAIT reason=%r", exc)
            else:
                error = True
                log.error("START_FAILED source=%s reason=%r", source, exc)

    def stop_recorder():
        nonlocal child, session, expected_stop, ignore_until
        if child is None:
            return
        expected_stop = True
        log.info("STOP session=%s pid=%s", session, child.pid)
        child.terminate()
        try:
            child.wait(timeout=100)
        except subprocess.TimeoutExpired:
            log.error("STOP_TIMEOUT session=%s", session)
            child.kill()
            child.wait()
        log.info("STOPPED session=%s exit=%s", session, child.returncode)
        child = None
        session = None
        ignore_until = time.monotonic() + 1.0

    def short_press(now, source):
        nonlocal error, blink_until
        if shutdown or now < ignore_until:
            log.info("PRESS_IGNORED source=%s", source)
            return
        if child is None:
            start_session(now, source)
        else:
            try:
                frame = int(heartbeat.read_text().split()[0])
                marker(rec, session, frame, log)
                blink_until = now + .15
            except Exception as exc:
                error = True
                log.error("MARKER_FAILED reason=%r", exc)

    def hold(now, source):
        nonlocal shutdown, error
        if shutdown or now < ignore_until:
            log.info("HOLD_IGNORED source=%s", source)
            return
        log.info("HOLD source=%s", source)
        shutdown = True
        stop_recorder()
        gpio.led_on(False)
        for _ in range(3):
            gpio.led_on(True)
            time.sleep(.1)
            gpio.led_on(False)
            time.sleep(.1)
        try:
            request_poweroff(log)
        except Exception as exc:
            log.error("POWER_OFF_FAILED reason=%r", exc)
            error = True
            shutdown = False

    try:
        while not terminate:
            now = time.monotonic()
            if child is not None and child.poll() is not None:
                log.error("RECORDER_EXIT session=%s code=%s expected=%s", session, child.returncode, expected_stop)
                child = None
                session = None
                error = True
                ignore_until = now + 1.0
                expected_stop = False
            sample = gpio.pressed()
            if sample != raw_pressed:
                raw_pressed = sample
                raw_since = now
            if now - raw_since >= .06 and stable_pressed != raw_pressed:
                stable_pressed = raw_pressed
                if stable_pressed:
                    pressed_since = now
                    hold_fired = False
                else:
                    if pressed_since is not None and not hold_fired:
                        short_press(now, "button")
                    pressed_since = None
            if stable_pressed and pressed_since is not None and not hold_fired:
                if now - pressed_since >= cfg.getfloat("hold_seconds"):
                    hold_fired = True
                    hold(now, "button")
            while short_events:
                short_events -= 1
                short_press(time.monotonic(), "SIGUSR1")
            while hold_events:
                hold_events -= 1
                hold(time.monotonic(), "SIGUSR2")
            if auto and child is None and not shutdown and now >= next_auto_try:
                start_session(now, "auto")
                next_auto_try = now + (10 if error else 1)
                if error and now - auto_wait_started >= 60:
                    log.error("AUTO_START_WAIT_EXCEEDED_60S")
            if child is not None and cfg.getboolean("record_rgb") and now - last_rgb_check >= 1:
                last_rgb_check = now
                rgb_status = rec / f"{session}.rgb.status.json"
                if rgb_status.exists():
                    try:
                        import json
                        state = json.loads(rgb_status.read_text()).get("state")
                        if state == "error" and not rgb_failed:
                            rgb_failed = True
                            log.error("RGB_FAILED session=%s; thermal capture continues", session)
                    except (OSError, ValueError):
                        pass
            if child is not None and now - last_disk_check >= 5:
                last_disk_check = now
                free = shutil.disk_usage(rec).free
                if free < cfg.getfloat("minimum_free_gb") * 1_000_000_000:
                    log.error("DISK_LOW during recording free=%s; stopping", free)
                    error = True
                    stop_recorder()
            if child is not None:
                if heartbeat.exists():
                    try:
                        last_valid_heartbeat = float(heartbeat.read_text().split()[1])
                    except (OSError, ValueError, IndexError):
                        pass
                age = now - last_valid_heartbeat
                if age > 5:
                    if not error:
                        log.error("CAPTURE_STALLED age=%.2f", age)
                    error = True
                elif heartbeat.exists() and error:
                    log.info("CAPTURE_RECOVERED")
                    error = False
            if not shutdown:
                led = (int(now * 10) % 2 == 0) if (error or rgb_failed) else (True if child else ready_led(now))
                if now < blink_until:
                    led = False
                gpio.led_on(led)
            time.sleep(.025)
    finally:
        log.info("CONTROLLER_STOPPING")
        stop_recorder()
        gpio.close()
        log.info("CONTROLLER_STOPPED")


if __name__ == "__main__":
    main()
