#!/usr/bin/env python3
"""scan_positions.py — scan chunk 0 for candidate position arrays (s16x3, f32x3)."""
import struct

D = "/home/cyan/code/nickmapper-lua/asset-extract/nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb"
d = open(D, "rb").read()
sect = d[0x594:0x594 + 0x34680]

REGION = 0x4C80  # scan [0, 0x4C80): everything before the C-blocks


def is_float(v):
    import math
    return not math.isnan(v) and abs(v) < 1e6


# candidate: s16 x3 with stride 6, value range plausible for this world
# world coords roughly x,y,z in [-15, 40]
def check_s16(off):
    n = 0
    vals = []
    i = off
    while i + 6 <= REGION:
        x, y, z = struct.unpack_from(">hhh", sect, i)
        if abs(x) > 6000 or abs(y) > 6000 or abs(z) > 6000:
            break
        vals.append((x, y, z))
        i += 6
        n += 1
    if n >= 8:
        xs = [v[0] for v in vals]
        ys = [v[1] for v in vals]
        zs = [v[2] for v in vals]
        return (n, min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))
    return None


print("=== s16x3 runs (stride 6) in [0, 0x4C80) ===")
found = 0
off = 0
while off + 6 <= REGION:
    r = check_s16(off)
    if r:
        n, x0, x1, y0, y1, z0, z1 = r
        print("off=0x%04x n=%d x[%d..%d] y[%d..%d] z[%d..%d] head=%s" % (
            off, n, x0, x1, y0, y1, z0, z1,
            " ".join("%04x" % struct.unpack_from(">H", sect, off + j)[0] for j in range(0, 12, 2))))
        found += 1
        off += 6 * n
    else:
        off += 2

print()
print("=== f32x3 runs (stride 12) in [0, 0x4C80) ===")
found = 0
off = 0
while off + 12 <= REGION:
    n = 0
    vals = []
    i = off
    while i + 12 <= REGION:
        x, y, z = struct.unpack_from(">fff", sect, i)
        if not (is_float(x) and is_float(y) and is_float(z)):
            break
        if abs(x) > 200 or abs(y) > 200 or abs(z) > 200:
            break
        vals.append((x, y, z))
        i += 12
        n += 1
    if n >= 6:
        xs = [v[0] for v in vals]
        ys = [v[1] for v in vals]
        zs = [v[2] for v in vals]
        print("off=0x%04x n=%d x[%.1f..%.1f] y[%.1f..%.1f] z[%.1f..%.1f]" % (
            off, n, min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))
        found += 1
        off += 12 * n
    else:
        off += 4

print()
print("done")
