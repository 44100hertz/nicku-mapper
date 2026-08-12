#!/usr/bin/env python3
"""Final checks: pointer table tail (0x3748..0x3B08), 0x38AC struct, chunk-B distribution."""
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

print("=== pointer table 0x3748..0x3B08 ===")
for off in range(0x3748, 0x3B08, 4):
    v = u32(off)
    print("+0x%04x: %08x" % (off, v))

print()
print("=== 0x38AC struct (first 32 u32s) ===")
for off in range(0x38AC, 0x38AC + 128, 4):
    print("+0x%04x: %08x  (f=%.3f)" % (off, u32(off), struct.unpack(">f", struct.pack(">I", u32(off)))[0]))

print()
print("=== chunk(k+1) - B for all meshes ===")
diffs = []
for k in range(86):
    off = 0x3B08 + 0x34 * k
    B = u32(off + 24)
    csize = sizes[k + 1]
    diffs.append(csize - B)
print("chunk-B values:", [hex(x) for x in diffs])
from collections import Counter
print("Counter:", Counter(diffs))
