import time
from lep import Stream
st = Stream(); st.hard()
t0 = time.time(); last = t0; runs = 0; exp = 0; junk = 0; hdr = []
while time.time() - t0 < 30:
    p = st.packet()
    if (p[0] & 0x0F) == 0x0F or not any(p): continue
    n = p[1]
    if n == exp:
        exp += 1
        if exp == 60: runs += 1; exp = 0
    else:
        junk += 1
        if len(hdr) < 8 and time.time() - t0 > 6: hdr.append("%.1fs expected %d got %d  %s" % (time.time() - t0, exp, n, p[:24].hex()))
        exp = 1 if n == 0 else 0
    if time.time() - last >= 1:
        print("%5.1fs  complete segments %3d   out-of-order %5d" % (time.time() - t0, runs, junk))
        runs = 0; junk = 0; last = time.time()
print("\n".join(hdr))
