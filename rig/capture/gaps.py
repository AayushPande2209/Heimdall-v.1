import re, os, sys
L = open(os.path.expanduser('~/rec/%s.txt' % sys.argv[1])).read().split('\n')
print("format check:", L[:2])
ts = []
for l in L:
    m = re.findall(r'\d+\.?\d*', l)
    if m: ts.append(float(m[-1]))
t0 = ts[0]
for i in range(1, len(ts)):
    if ts[i] - ts[i-1] > 0.25:
        print("frame %d at %.1fs: gap %.2fs" % (i, ts[i-1] - t0, ts[i] - ts[i-1]))
print("total frames", len(ts), "over %.1fs" % (ts[-1] - t0))
