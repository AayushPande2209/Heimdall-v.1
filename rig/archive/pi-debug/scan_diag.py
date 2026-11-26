import time
import spidev

PKT = 164
CH = 24

spi = spidev.SpiDev()
spi.open(0, 0)
spi.mode = 3
spi.max_speed_hz = 10_000_000
time.sleep(0.25)
buf = bytearray()
while len(buf) < PKT * 48:
    buf.extend(spi.xfer2([0] * (PKT * CH)))
spi.close()

scores = []
for offset in range(PKT):
    old = 0
    valid = 0
    transitions = 0
    starts = 0
    previous = None
    headers = []
    for k in range(40):
        pos = offset + k * PKT
        b0, b1 = buf[pos], buf[pos + 1]
        discard = (b0 & 0x0F) == 0x0F
        if discard:
            old += 1
            previous = None
            continue
        if b1 < 60:
            old += 1
            valid += 1
            starts += b1 == 0
            if previous is not None and b1 == previous + 1:
                transitions += 1
            previous = b1
            if len(headers) < 12:
                headers.append((b0, b1))
        else:
            previous = None
    sequence_score = transitions * 20 + valid + starts * 2
    scores.append((sequence_score, transitions, valid, starts, old, offset, headers))

print("top sequence-aware offsets")
for row in sorted(scores, reverse=True)[:10]:
    print(row)
print("top old-score offsets")
for row in sorted(scores, key=lambda x: (x[4], -x[5]), reverse=True)[:10]:
    print(row)
