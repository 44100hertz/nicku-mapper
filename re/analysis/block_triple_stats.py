#!/usr/bin/env python3
"""Per-block u8-triple stats: max value per byte position, degeneracy count."""
import struct

PATH = "nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb"
d = open(PATH, "rb").read()
SECT = 0x594
sect = d[SECT:SECT + 0x34680]

def u32(o): return struct.unpack_from(">I", sect, o)[0]

print("k  F      maxA maxB maxC  degen  dupTri  blockBytes 4+3F")
for k in range(86):
    off = 0x3B08 + 0x34 * k
    C, D, F = u32(off+32), u32(off+36), u32(off+44)
    blk = sect[C:C + D]
    # after 4-byte head, read 3-byte triples
    n = (D - 4) // 3
    maxa = maxb = maxc = 0
    degen = 0
    seen = set()
    dup = 0
    for i in range(n):
        a, b, c = blk[4 + 3*i], blk[4 + 3*i + 1], blk[4 + 3*i + 2]
        maxa = max(maxa, a); maxb = max(maxb, b); maxc = max(maxc, c)
        if a == b or b == c or a == c:
            degen += 1
        t = (a, b, c)
        if t in seen:
            dup += 1
        seen.add(t)
    print("%2d %-6d %-4d %-4d %-4d  %-5d %-5d  %-6d %-6d" %
          (k, F, maxa, maxb, maxc, degen, dup, D, 4 + 3 * F))
