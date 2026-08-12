#!/usr/bin/env python3
"""Decode all 52-byte mesh records + cross-correlate with chunk sizes and blocks."""
import struct

PATH = "nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb"
d = open(PATH, "rb").read()
SECT = 0x594
sect = d[SECT:SECT + 0x34680]

def u32(o): return struct.unpack_from(">I", sect, o)[0]
def f32(o): return struct.unpack_from(">f", sect, o)[0]
def i16(o): return struct.unpack_from(">h", sect, o)[0]

# chunk sizes from HDRX
hdrx = 0x20
chunk_sizes = []
for i in range(87):
    sz = struct.unpack_from(">I", d, hdrx + 8 + i * 16)[0]
    chunk_sizes.append(sz)
# chunk i base offset within SECT
chunk_base = []
acc = 0
for sz in chunk_sizes:
    chunk_base.append(acc)
    acc += sz
print("chunk0 size 0x%x, mesh chunks 1..86" % chunk_sizes[0])

print()
print("=== mesh records (offset 0x3B08 + 0x34*k), k=0..85 ===")
print("k  off    x0      x1      y0      y1      [4]  A       B       [7]  C       D       E       F       G      chunk(k+1)size")
recs = []
for k in range(86):
    off = 0x3B08 + 0x34 * k
    vals = [u32(off + 4 * i) for i in range(13)]
    fs = [f32(off + 4 * i) for i in range(4)]
    recs.append((off, vals, fs))
    csize = chunk_sizes[k + 1]
    print("%2d  %04x  %8.3f %8.3f %8.3f %8.3f  %08x %08x %08x %08x %08x %08x %08x %08x %08x  %5x"
          % (k, off, fs[0], fs[1], fs[2], fs[3], vals[4], vals[5], vals[6], vals[7],
             vals[8], vals[9], vals[10], vals[11], vals[12], csize))

print()
print("=== checks: E==C+D? ; D multiple of A or B? ; chunk size relation ===")
import collections
for k in range(2, 86):
    off, vals, fs = recs[k]
    C, D, E, F, G = vals[8], vals[9], vals[10], vals[11], vals[12]
    A, B = vals[5], vals[6]
    csize = chunk_sizes[k + 1]
    flags = []
    if E != C + D:
        flags.append("E!=C+D")
    if D and A and D % A == 0:
        flags.append("D%%A==0 (D/A=%d)" % (D // A))
    if D and B and D % B == 0:
        flags.append("D%%B==0 (D/B=%d)" % (D // B))
    if csize % 6 == 0:
        flags.append("chunk%%6==0 (recs=%d)" % (csize // 6))
    if csize and F and csize % F == 0:
        flags.append("chunk%%F==0 (%d)" % (csize // F))
    if flags:
        print("mesh %2d: %s" % (k, "; ".join(flags)))
