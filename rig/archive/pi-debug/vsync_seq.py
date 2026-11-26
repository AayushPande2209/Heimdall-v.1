import argparse
import time

import gpiod
import spidev

from lepton_gpio import enable_vsync

PACKET_SIZE = 164
PACKETS_PER_SEGMENT = 60
CHUNK_PACKETS = (24, 24, 12)

parser = argparse.ArgumentParser()
parser.add_argument("--delay-us", type=int, default=0)
parser.add_argument("--edges", type=int, default=500)
parser.add_argument("--speed-mhz", type=int, default=10)
args = parser.parse_args()

enable_vsync(verbose=False)

line_settings = gpiod.LineSettings(
    direction=gpiod.line.Direction.INPUT,
    edge_detection=gpiod.line.Edge.RISING,
    bias=gpiod.line.Bias.DISABLED,
)
request = gpiod.request_lines(
    "/dev/gpiochip0",
    consumer="lepton-vsync-probe",
    config={22: line_settings},
)

spi = spidev.SpiDev()
spi.open(0, 0)
spi.mode = 3
spi.max_speed_hz = args.speed_mhz * 1_000_000

counts = {}
valid = invalid = timeouts = 0
start = time.monotonic()
try:
    for _ in range(args.edges):
        if not request.wait_edge_events(0.1):
            timeouts += 1
            continue
        events = request.read_edge_events()
        target_ns = events[-1].timestamp_ns + args.delay_us * 1000
        while time.monotonic_ns() < target_ns:
            pass
        data = bytearray()
        for packet_count in CHUNK_PACKETS:
            data.extend(spi.xfer2([0] * (PACKET_SIZE * packet_count)))

        packet_numbers = [data[i * PACKET_SIZE + 1] for i in range(PACKETS_PER_SEGMENT)]
        discard = [(data[i * PACKET_SIZE] & 0x0F) == 0x0F for i in range(PACKETS_PER_SEGMENT)]
        sequence_ok = packet_numbers == list(range(PACKETS_PER_SEGMENT))
        if sequence_ok and not any(discard):
            segment = (data[20 * PACKET_SIZE] >> 4) & 0x07
            counts[segment] = counts.get(segment, 0) + 1
            valid += 1
        else:
            if invalid < 10:
                print(
                    "invalid first=%s discard=%d"
                    % (packet_numbers[:12], sum(discard)),
                    flush=True,
                )
            invalid += 1
finally:
    elapsed = time.monotonic() - start
    spi.close()
    request.release()

print(
    "done elapsed=%.3f valid=%d invalid=%d timeouts=%d segments=%s"
    % (elapsed, valid, invalid, timeouts, counts)
)
