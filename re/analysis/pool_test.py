#!/usr/bin/env python3
"""pool_test.py — test whether u16-stream posIdx indexes the cumulative C-block pool."""
import struct

PATH = "nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb"
d = open(PATH, "rb").read()
SECT = 0x594
sect = d[SECT:SECT + 0x34680]

def u32(o): return struct.unpack_from(">I", sect, o)[0]
def u16(o): return struct.unpack_from(">H", sect, o)[0]

hdrx = 0x20
sizes = []
for i in range(87):
    sizes.append(struct.unpack_from(">I", d, hdrx + i * 16)[0])
bases = []
acc = 0
for sz in sizes:
    bases.append(acc)
    acc += sz

# cumulative pool start per mesh (mesh order)
recs = []
cum = 0
for k in range(86):
    off = 0x3B08 + 0x34 * k
    A, B, C, D, F, G = u32(off + 0x14), u32(off + 0x18), u32(off + 0x20), u32(off + 0x24), u32(off + 0x2C), u32(off + 0x30)
    recs.append((A, B, C, D, F, G, cum))
    cum += F
total_pool = cum
print("total pool triples (sum F):", total_pool)

print()
print("k   A(bytes)  maxPosInAreg  cumStart cumEnd  F     G          max<cumEnd?")
ok = True
for k in range(86):
    A, B, C, D, F, G, cumStart = recs[k]
    cumEnd = cumStart + F
    cb = bases[k + 1]
    cs = sizes[k + 1]
    n = min(A, cs) // 6
    mx = 0
    for i in range(n):
        p = u16(cb + 6 * i)
        if p > mx:
            mx = p
    fit = mx < cumEnd or F == 0
    if not fit:
        ok = False
    print("%2d  %6d  %6d  %6d %6d  %5d  %08x  %s" %
          (k, A, mx, cumStart, cumEnd, F, G, "OK" if fit else "OVERFLOW"))
print()
print("ALL FIT:", ok)
