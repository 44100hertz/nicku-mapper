#!/usr/bin/env python3
"""dump_sect.py — dump a SECT range."""
import sys

D = "/home/cyan/code/nickmapper-lua/asset-extract/nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb"
d = open(D, "rb").read()
sect = d[0x594:0x594 + 0x34680]


def dump(off, n):
    b = sect[off:off + n]
    for i in range(0, len(b), 16):
        row = b[i:i + 16]
        print("  %06x: %s  %s" % (off + i, " ".join("%02x" % x for x in row),
                                  "".join(chr(x) if 32 <= x < 127 else "." for x in row)))


off = int(sys.argv[1], 16)
n = int(sys.argv[2], 16)
dump(off, n)
