#!/usr/bin/env python3
"""rec38ac.py — parse the 604-byte record at SECT+0x38AC."""
import struct

D = "/home/cyan/code/nicku-mapper/asset-extract/nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb"
d = open(D, "rb").read()
sect = d[0x594:0x594 + 0x34680]

off = 0x38AC
end = 0x3B08
print("parse 0x38AC..0x3B08 as mixed u32/floats:")
i = off
while i < end:
    v = struct.unpack_from(">I", sect, i)[0]
    f = struct.unpack_from(">f", sect, i)[0]
    tag = ""
    if 0x38A0 <= v <= 0x3B08:
        tag = "  <-- ptr into 0x38AC region!"
    if v == 0xFFFFFFFF:
        tag = "  <-0xFFFFFFFF"
    print("  0x%04x: u32=0x%08x f=%.4f%s" % (i, v, f, tag))
    i += 4
