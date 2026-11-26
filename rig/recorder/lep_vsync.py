import time

import gpiod
import numpy as np
import spidev

from lepton_gpio import enable_vsync

PACKET_SIZE = 164
PACKETS_PER_SEGMENT = 60
CHUNK_PACKETS = (24, 24, 12)
VSYNC_GPIO = 22
VSYNC_DELAY_NS = 450_000


class Stream:
    def __init__(self, speed=20_000_000):
        enable_vsync(verbose=False)
        settings = gpiod.LineSettings(
            direction=gpiod.line.Direction.INPUT,
            edge_detection=gpiod.line.Edge.RISING,
            bias=gpiod.line.Bias.DISABLED,
        )
        self.gpio = gpiod.request_lines(
            "/dev/gpiochip0",
            consumer="lepton-vsync",
            config={VSYNC_GPIO: settings},
        )
        self.spi = spidev.SpiDev()
        self.spi.open(0, 0)
        self.spi.mode = 3
        self.spi.max_speed_hz = speed
        self.invalid_segments = 0
        self.consecutive_invalid = 0
        self.recoveries = 0
        self.vsync_timeouts = 0
        self.next_slot = None
        self.completed_frames = 0
        self.phase_corrections = 0

    def _resync(self):
        time.sleep(0.20)
        enable_vsync(verbose=False)
        if self.gpio.wait_edge_events(0):
            self.gpio.read_edge_events()
        self.consecutive_invalid = 0
        self.next_slot = None
        self.recoveries += 1

    def _wait_vsync(self, timeout=0.1):
        if not self.gpio.wait_edge_events(timeout):
            self.vsync_timeouts += 1
            return False
        events = self.gpio.read_edge_events()
        target = events[-1].timestamp_ns + VSYNC_DELAY_NS
        while time.monotonic_ns() < target:
            pass
        return True

    def segment(self):
        if not self._wait_vsync():
            return None
        data = bytearray()
        for packet_count in CHUNK_PACKETS:
            data.extend(self.spi.xfer2([0] * (PACKET_SIZE * packet_count)))

        for number in range(PACKETS_PER_SEGMENT):
            pos = number * PACKET_SIZE
            if (data[pos] & 0x0F) == 0x0F or data[pos + 1] != number:
                self.invalid_segments += 1
                self.consecutive_invalid += 1
                self.next_slot = None
                if self.consecutive_invalid >= 4:
                    self._resync()
                return None

        segment_number = (data[20 * PACKET_SIZE] >> 4) & 0x07
        if segment_number not in (0, 1, 2, 3, 4):
            self.invalid_segments += 1
            self.consecutive_invalid += 1
            self.next_slot = None
            if self.consecutive_invalid >= 4:
                self._resync()
            return None

        self.consecutive_invalid = 0
        if segment_number == 0 and self.next_slot is None:
            return None
        if segment_number == 0:
            slot = self.next_slot
        else:
            slot = segment_number
            if self.next_slot is not None and slot != self.next_slot:
                self.phase_corrections += 1
        self.next_slot = slot % 4 + 1

        pixels = np.empty((30, 160), dtype=np.uint16)
        for number in range(PACKETS_PER_SEGMENT):
            pos = number * PACKET_SIZE
            pixels[number // 2, (number % 2) * 80 : (number % 2 + 1) * 80] = (
                np.frombuffer(data, dtype=">u2", count=80, offset=pos + 4)
            )
        return slot, pixels

    def hard(self):
        self._resync()
        return True

    def close(self):
        self.spi.close()
        self.gpio.release()


def grab(stream, tries=240):
    frame = np.empty((120, 160), dtype=np.uint16)
    expected = 1
    for _ in range(tries):
        result = stream.segment()
        if result is None:
            expected = 1
            continue
        segment_number, pixels = result
        if segment_number == 1:
            frame[0:30] = pixels
            expected = 2
            continue
        if segment_number != expected:
            expected = 1
            continue
        start = (segment_number - 1) * 30
        frame[start : start + 30] = pixels
        expected += 1
        if segment_number == 4:
            stream.completed_frames += 1
            expected = 1
            if stream.completed_frames % 3 == 0:
                return frame
    return None
