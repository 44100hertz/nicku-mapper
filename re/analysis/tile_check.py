#!/usr/bin/env python3
"""tile_check.py — do the 86 C-blocks tile chunk0? is posIdx a cumulative C-block index?"""
import struct

PATH = "nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb"
d = open(PATH, "rb").read()
SECT = 0x594
sect = d[SECT:SECT + 0x34680]

def u32(o): return struct.unpack_from(">I", sect, o)[0]
def f32(o): return struct.unpack_from(">f", sect, o)[0]
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

print("=== all mesh records: C, D, E, F, G, bounds ===")
recs = []
for k in range(86):
    off = 0x3B08 + 0x34 * k
    C, D, E, F, G = u32(off + 0x20), u32(off + 0x24), u32(off + 0x28), u32(off + 0x2C), u32(off + 0x30)
    fs = [f32(off + 4 * i) for i in range(4)]
    recs.append((k, off, C, D, E, F, G, fs))
    print("k=%2d C=%04x D=%04x E=%04x F=%5d G=%08x bounds=%s" % (k, C, D, E, F, G, ["%.2f" % v for v in fs]))

print()
print("=== C-block tiling: sort by C, check gaps ===")
srt = sorted(recs, key=lambda r: r[2])
prev_end = None
for k, off, C, D, E, F, G, fs in srt:
    gap = ""
    if prev_end is not None:
        gap = "gap=%d" % (C - prev_end)
    prev_end = C + D
    print("k=%2d C=%04x..%04x F=%5d %s" % (k, C, C + D, F, gap))

print()
print("=== global pool hypothesis: cumulative triple index vs u16 posIdx ===")
# cumulative: sum of F over meshes in C order
cum = {}
total = 0
for k, off, C, D, E, F, G, fs in srt:
    cum[k] = total
    total += F
print("total triples in C-blocks:", total)

# u16 stream posIdx max per chunk vs cumulative range
for k in (0, 1, 2, 3, 5, 13):
    if k >= 86:
        continue
    off = 0x3B08 + 0x34 * k
    A = u32(off + 0x14)
    cb = bases[k + 1]
    cs = sizes[k + 1]
    n = min(A, cs) // 6
    mx = 0
    for i in range(n):
        p = u16(cb + 6 * i)
        if p > mx:
            mx = p
    print("mesh k=%2d: u16stream(%d bytes=%d recs) maxPosIdx=%5d  cumStart=%d cumEnd=%d" %
          (k, n * 6, n, mx, cum.get(k, -1), cum.get(k, -1) + recs[k][5]))
