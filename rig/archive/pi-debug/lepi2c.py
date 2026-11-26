import subprocess, time
A = "0x2a"
def tx(*a):
    return subprocess.run(["i2ctransfer", "-y", "1"] + list(a), capture_output=True, text=True)
def wr(reg, val):
    tx("w4@" + A, "0x%02x" % (reg >> 8), "0x%02x" % (reg & 255), "0x%02x" % (val >> 8), "0x%02x" % (val & 255))
def rd(reg, n=1):
    r = tx("w2@" + A, "0x%02x" % (reg >> 8), "0x%02x" % (reg & 255), "r%d" % (2 * n))
    b = [int(x, 16) for x in r.stdout.split()]
    if len(b) < 2 * n: return None
    return [(b[i] << 8) | b[i + 1] for i in range(0, 2 * n, 2)]
def wait():
    s = None
    for _ in range(100):
        s = rd(2)
        if s and not (s[0] & 1): break
        time.sleep(0.005)
    return s
def cmd(cid, words):
    wait(); wr(6, words); wr(4, cid)
    s = wait()
    return s, rd(8, words)
t0 = time.time()
while time.time() - t0 < 30:
    st, cam = cmd(0x0204, 4)
    st2, up = cmd(0x020C, 2)
    ms = (up[0] | (up[1] << 16)) if up else None
    print("%5.1fs cam_status=%s uptime_ms=%s i2c_status=%s" % (time.time() - t0, cam, ms, st))
    time.sleep(0.15)
