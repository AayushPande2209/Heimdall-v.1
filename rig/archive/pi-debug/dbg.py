import time
from lep import Stream
st = Stream(); st.hard()
t0 = time.time(); ev = []; frames = 0; have = {}
def log(m): ev.append("%.2f %s" % (time.time() - t0, m))
while time.time() - t0 < 20:
    n = 0; segnum = None; guard = 0; reason = None
    while n < 60:
        guard += 1
        if guard > 3000: reason = "guard n=%d" % n; break
        p = st.packet()
        if (p[0] & 0x0F) == 0x0F: continue
        if n == 0 and p[1] != 0: continue
        if p[1] != n: reason = "seq expected %d got %d" % (n, p[1]); break
        if n == 20: segnum = (p[0] >> 4) & 7
        n += 1
    if reason:
        log("FAIL " + reason + " have=" + str(sorted(have))); have = {}; st.scan(); continue
    if segnum in (1, 2, 3, 4):
        have[segnum] = 1
        if len(have) == 4: frames += 1; log("frame %d" % frames); have = {}
    else:
        log("badseg %s" % segnum)
print("\n".join(ev[:90]))
print("total frames", frames)
