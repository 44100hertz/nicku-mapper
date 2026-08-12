#!/usr/bin/env python3
"""parse_boundary.py — decode the 0x38AC structure (11 records, consecutive u16 ranges)."""
import struct

PATH = "nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb"
d = open(PATH, "rb").read()
SECT = 0x594
sect = d[SECT:SECT + 0x34680]

def u32(o): return struct.unpack_from(">I", sect, o)[0]
def f32(o): return struct.unpack_from(">f", sect, o)[0]
def u16(o): return struct.unpack_from(">H", sect, o)[0]

# dump 0x38AC..0x3B08 labeled
print("=== raw dump 0x38AC..0x3B08 ===")
for o in range(0x38AC, 0x3B08, 0x10):
    row = " ".join("%08x" % u32(o + i) for i in range(0, 16, 4))
    fr = " ".join("%9.3f" % f32(o + i) for i in range(0, 16, 4))
    print("%04x  %s  | %s" % (o, row, fr))

# Hypothesis: structure = list of records. Try to find record boundaries via the u16 runs.
print()
print("=== u16 view (to find index lists) ===")
for o in range(0x38AC, 0x3B08, 0x10):
    u = [u16(o + i) for i in range(0, 16, 2)]
    print("%04x: %s" % (o, " ".join("%04x" % v for v in u)))
