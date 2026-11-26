import time
from lep import Stream
st = Stream(); st.hard()
t0 = time.time(); z = d = g = 0; last = t0
while time.time() - t0 < 40:
    p = st.packet()
    if (p[0] & 0x0F) == 0x0F: g += 1
    elif not any(p): z += 1
    else: d += 1
    if time.time() - last >= 0.5:
        print("%5.1fs  data %4d   zero %4d   discard %4d" % (time.time() - t0, d, z, g))
        z = d = g = 0; last = time.time()
