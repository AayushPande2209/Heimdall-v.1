import spidev, time
import numpy as np

PKT, CH = 164, 24

class Stream:
    def __init__(self, speed=10000000):
        self.spi = spidev.SpiDev(); self.spi.open(0, 0)
        self.spi.mode = 0b11; self.spi.max_speed_hz = speed
        self.buf = bytearray()
    def fill(self, n):
        while len(self.buf) < n:
            self.buf.extend(self.spi.xfer2([0] * (PKT * CH)))
    def scan(self):
        self.buf = bytearray(); self.fill(PKT * 48)
        best, score = 0, -1
        for o in range(PKT):
            s = 0
            for k in range(40):
                p = o + k * PKT
                if (self.buf[p] & 0x0F) == 0x0F: s += 1
                elif self.buf[p+1] < 60: s += 1
            if s > score: score, best = s, o
        del self.buf[:best]
        return score
    def hard(self):
        self.buf = bytearray(); time.sleep(0.25); return self.scan()
    def packet(self):
        self.fill(PKT)
        p = bytes(self.buf[:PKT]); del self.buf[:PKT]
        return p
    def close(self): self.spi.close()

def grab(st, tries=80):
    frame = np.zeros((120, 160), dtype=np.uint16); have = {}
    for _ in range(tries):
        seg = np.zeros((30, 160), dtype=np.uint16)
        n, segnum, ok, guard = 0, None, True, 0
        while n < 60:
            guard += 1
            if guard > 3000: ok = False; break
            p = st.packet()
            if (p[0] & 0x0F) == 0x0F: continue
            if n == 0 and p[1] != 0: continue
            if p[1] != n: ok = False; break
            if n == 20: segnum = (p[0] >> 4) & 0x07
            seg[n//2, (n%2)*80:(n%2)*80+80] = np.frombuffer(p[4:], dtype='>u2')
            n += 1
        if not ok:
            st.hard()
            have = {}
            continue
        if segnum in (1, 2, 3, 4):
            frame[(segnum-1)*30:segnum*30] = seg; have[segnum] = True
            if len(have) == 4: return frame
    return None
