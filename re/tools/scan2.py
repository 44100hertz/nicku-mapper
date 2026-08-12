#!/usr/bin/env python3
"""scan2.py — aggressive scan of [0x40, 0x4C80) for position arrays (u8/u16/s16 variants)."""
import struct

D = "/home/cyan/code/nickmapper-lua/asset-extract/nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb"
d = open(D, "rb").read()
sect = d[0x594:0x594 + 0x34680]

END = 0x4C80


def fmt_range(vals):
    xs = [v[0] for v in vals]
    ys = [v[1] for v in vals]
    zs = [v[2] for v in vals]
    return "x[%d..%d] y[%d..%d] z[%d..%d]" % (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


# u8 xyz stride 3
print("=== u8x3 runs ===")
off = 0x40
while off + 3 <= END:
    n = 0
    vals = []
    i = off
    while i + 3 <= END:
        x, y, z = sect[i], sect[i + 1], sect[i + 2]
        vals.append((x, y, z))
        i += 3
        n += 1
    if n >= 20:
        print("off=0x%04x n=%d %s head=%s" % (off, n, fmt_range(vals),
              " ".join("%02x" % x for x in sect[off:off + 9])))
        off += 3 * n
    else:
        off += 1

print()
print("=== u16x3 runs (BE) ===")
off = 0x40
while off + 6 <= END:
    n = 0
    vals = []
    i = off
    while i + 6 <= END:
        x, y, z = struct.unpack_from(">HHH", sect, i)
        if x > 4096 or y > 4096 or z > 4096:
            break
        vals.append((x, y, z))
        i += 6
        n += 1
    if n >= 20:
        print("off=0x%04x n=%d %s head=%s" % (off, n, fmt_range(vals),
              " ".join("%04x" % struct.unpack_from(">H", sect, off + j)[0] for j in range(0, 12, 2))))
        off += 6 * n
    else:
        off += 2

print()
print("=== dump 0x4C40..0x4C80 (right before C-blocks) ===")
b = sect[0x4C40:0x4C80]
for i in range(0, len(b), 16):
    row = b[i:i + 16]
    print("  %06x: %s" % (0x4C40 + i, " ".join("%02x" % x for x in row)))
