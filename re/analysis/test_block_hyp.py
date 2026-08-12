#!/usr/bin/env python3
"""Test hypothesis: C..E block = [A bytes vertex data][B bytes triangle data].
Also dump chunk (k+1) heads and the block heads for meshes 0,1,2."""
import struct

PATH = "nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb"
d = open(PATH, "rb").read()
SECT = 0x594
sect = d[SECT:SECT + 0x34680]

def u32(o): return struct.unpack_from(">I", sect, o)[0]
def s16(o): return struct.unpack_from(">h", sect, o)[0]

# chunk sizes + bases
hdrx = 0x20
sizes = []
for i in range(87):
    sizes.append(struct.unpack_from(">I", d, hdrx + i * 16)[0])
bases = []
acc = 0
for sz in sizes:
    bases.append(acc)
    acc += sz

print("chunk0 base=0x%x size=0x%x" % (bases[0], sizes[0]))

for k in (0, 1, 2, 5, 6):
    off = 0x3B08 + 0x34 * k
    A, B, C, D = u32(off + 20), u32(off + 24), u32(off + 32), u32(off + 36)
    cbase, csize = bases[k + 1], sizes[k + 1]
    print()
    print("### mesh %d: rec@0x%x A=0x%x B=0x%x C=0x%x D=0x%x chunk%d@0x%x size=0x%x" %
          (k, off, A, B, C, D, k + 1, cbase, csize))
    print("  block head (32B):", sect[C:C + 32].hex(" "))
    print("  chunk head (48B):", sect[cbase:cbase + 48].hex(" "))
    # chunk as u16 triples (first 12)
    tri = [struct.unpack_from(">HHH", sect, cbase + 6 * i) for i in range(min(12, csize // 6))]
    print("  chunk u16 triples:", tri)

# decode first 384 bytes of mesh0 block as s16x3
off0 = 0x4C80
print()
print("=== mesh0 block [0x4c80..0x5040) first 32 verts as s16x3 ===")
for i in range(24):
    x, y, z = s16(off0 + 6 * i), s16(off0 + 6 * i + 2), s16(off0 + 6 * i + 4)
    print("  v%d: %6d %6d %6d" % (i, x, y, z))
