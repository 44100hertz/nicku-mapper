#!/usr/bin/env python3
"""Final: A/B vs chunk content; sum F; find global vertex array location."""
import struct

PATH = "nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb"
d = open(PATH, "rb").read()
SECT = 0x594
sect = d[SECT:SECT + 0x34680]

def u32(o): return struct.unpack_from(">I", sect, o)[0]

hdrx = 0x20
sizes = []
for i in range(87):
    sizes.append(struct.unpack_from(">I", d, hdrx + i * 16)[0])
bases = []
acc = 0
for sz in sizes:
    bases.append(acc)
    acc += sz

sumF = 0
sumA = 0
sumB = 0
sumD = 0
max_pos = 0
print("k  A      B      chunk  c-B    F     maxPosInChunk  D     D-(4+3F)")
for k in range(86):
    off = 0x3B08 + 0x34 * k
    A, B, C, D, F = u32(off+20), u32(off+24), u32(off+32), u32(off+36), u32(off+44)
    sumF += F; sumA += A; sumB += B; sumD += D
    csize = sizes[k + 1]
    cbase = bases[k + 1]
    # max posIdx: chunk as u16 triples
    n = csize // 6
    mx = 0
    for i in range(n):
        p = struct.unpack_from(">H", sect, cbase + 6 * i)[0]
        if p > mx: mx = p
    max_pos = max(max_pos, mx)
    print("%2d %-6x %-6x %-6x %-6x %-6x %-6d %-6x %-6d" % (k, A, B, csize, csize - B, F, mx, D, D - 4 - 3 * F))

print()
print("sumF=%d sumA=0x%x sumB=0x%x sumD=0x%x" % (sumF, sumA, sumB, sumD))
print("max posIdx seen in chunks:", max_pos)
print("sumA/6 =", sumA / 6, " sumA/12 =", sumA / 12)
# where would concatenated A-byte vertex arrays live? first A region = C of mesh0 = 0x4C80
