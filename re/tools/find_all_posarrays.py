#!/usr/bin/env python3
"""find_all_posarrays.py — find all large smooth s16x3 runs in SECT."""
import struct

D = "/home/cyan/code/nickmapper-lua/asset-extract/nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb"
d = open(D, "rb").read()
sect = d[0x594:0x594 + 0x34680]

# chunk map
sizes = []
o = 0x20
for i in range(87):
    sizes.append(struct.unpack_from(">I", d, o)[0])
    o += 16
starts = []
acc = 0
for s in sizes:
    starts.append(acc)
    acc += s


def chunk_of(off):
    for k in range(87):
        if starts[k] <= off < starts[k] + sizes[k]:
            return k
    return -1


# find runs of s16 triples where consecutive deltas are small (<200) and |v| < 5000
runs = []
off = 0
while off + 6 <= len(sect):
    x, y, z = struct.unpack_from(">hhh", sect, off)
    if abs(x) > 5000 or abs(y) > 5000 or abs(z) > 5000:
        off += 2
        continue
    # try to grow a run
    n = 1
    i = off + 6
    prev = (x, y, z)
    while i + 6 <= len(sect):
        a, b, c = struct.unpack_from(">hhh", sect, i)
        if abs(a) > 5000 or abs(b) > 5000 or abs(c) > 5000:
            break
        d = max(abs(a - prev[0]), abs(b - prev[1]), abs(c - prev[2]))
        if d > 400:
            break
        prev = (a, b, c)
        i += 6
        n += 1
    if n >= 60:
        runs.append((off, n))
    off += 6 * max(n, 1)

runs.sort(key=lambda t: -t[1])
print("smooth s16x3 runs n>=60 (dedup'd):")
seen = set()
for off, n in runs:
    if off in seen:
        continue
    seen.add(off)
    ch = chunk_of(off)
    xs, ys, zs = [], [], []
    for j in range(0, min(n, 8) * 6, 6):
        a, b, c = struct.unpack_from(">hhh", sect, off + j)
        xs.append(a)
        ys.append(b)
        zs.append(c)
    print("  off=0x%05x n=%4d chunk=%2d  head: (%d,%d,%d),(%d,%d,%d)  raw x[%d..%d] y[%d..%d] z[%d..%d]" % (
        off, n, ch, xs[0], ys[0], zs[0], xs[1], ys[1], zs[1], min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))
    if len(seen) >= 25:
        break
print("total candidate runs:", len(seen))
