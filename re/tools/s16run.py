#!/usr/bin/env python3
"""s16run.py — measure the smooth s16x3 run starting near 0x253C0."""
import struct

D = "/home/cyan/code/nickmapper-lua/asset-extract/nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb"
d = open(D, "rb").read()
sect = d[0x594:0x594 + 0x34680]


def measure(start, stride=6):
    n = 0
    i = start
    vals = []
    while i + 6 <= len(sect):
        x, y, z = struct.unpack_from(">hhh", sect, i)
        if abs(x) > 5000 or abs(y) > 5000 or abs(z) > 5000:
            break
        if vals and max(abs(x - vals[-1][0]), abs(y - vals[-1][1]), abs(z - vals[-1][2])) > 2000:
            break
        vals.append((x, y, z))
        i += stride
        n += 1
        if n > 4000:
            break
    return n, vals


n, vals = measure(0x253C0)
print("run at 0x253C0: n=%d entries (bytes %d)" % (n, n * 6))
xs = [v[0] for v in vals]
ys = [v[1] for v in vals]
zs = [v[2] for v in vals]
print("raw x[%d..%d] y[%d..%d] z[%d..%d]" % (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))
print("scaled /32: x[%.2f..%.2f] y[%.2f..%.2f] z[%.2f..%.2f]" % (
    min(xs) / 32, max(xs) / 32, min(ys) / 32, max(ys) / 32, min(zs) / 32, max(zs) / 32))
print("tail entries:", vals[-6:])
# where does it end?
end = 0x253C0 + n * 6
print("end offset: 0x%x" % end)
b = sect[end:end + 48]
print("after run:", " ".join("%02x" % x for x in b))
# head
print("head entries:", vals[:8])
