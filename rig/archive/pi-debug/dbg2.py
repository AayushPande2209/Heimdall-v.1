from lep import Stream
st = Stream(); st.hard()
pk = [st.packet() for _ in range(4000)]
nd = [(i, p) for i, p in enumerate(pk) if (p[0] & 0x0F) != 0x0F]
print("non-discard packets: %d of %d" % (len(nd), len(pk)))
last = -2
for i, p in nd[:70]:
    print("%4d  %s%s" % (i, p[:8].hex(), "" if i == last + 1 else "   <- gap"))
    last = i
