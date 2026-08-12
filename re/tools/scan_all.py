#!/usr/bin/env python3
"""scan_all.py — scan whole SECT for long s16x3 runs with plausible world-scale coords."""
import struct

D = "/home/cyan/code/nickmapper-lua/asset-extract/nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb"
d = open(D, "rb").read()
sect = d[0x594:0x594 + 0x34680]

SECT_END = 0x34680

# For each alignment, find runs where s16 triples are "small & plausible":
# world coords ~ -15..45; try scale 1/4, 1/8, 1/16, 1/32 -> s16 range -2048..4096 at 1/32
# Instead: look for runs where consecutive x,y,z change smoothly (position-like)
# Simple filter: |x|,|y|,|z| < 4096 and step between consecutive values < 1000
best = []
for scale in (1, 2, 4, 8, 16):
    LIM = 5000 // scale
    off = 0
    while off + 6 <= SECT_END:
        n = 0
        i = off
        prev = None
        ok = True
        while i + 6 <= SECT_END:
            x, y, z = struct.unpack_from(">hhh", sect, i)
            if abs(x) > LIM or abs(y) > LIM or abs(z) > LIM:
                break
            if prev:
                dx = abs(x - prev[0])
                dy = abs(y - prev[1])
                dz = abs(z - prev[2])
                if max(dx, dy, dz) > 800 // scale + 50:
                    break
            prev = (x, y, z)
            i += 6
            n += 1
        if n >= 40:
            best.append((scale, off, n))
        off += 2

best.sort(key=lambda t: -t[2])
print("long smooth s16x3 runs (scale-tolerant):")
for scale, off, n in best[:15]:
    print("  off=0x%05x n=%d (scale /%d)" % (off, n, scale))
    b = sect[off:off + 6 * min(n, 4)]
    print("    head:", " ".join("%04x" % struct.unpack_from(">H", b, j)[0] for j in range(0, 24, 2)))
