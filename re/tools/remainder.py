#!/usr/bin/env python3
"""remainder.py — dump the data after F*3 index bytes in big meshes' C-blocks."""
import struct

D = "/home/cyan/code/nickmapper-lua/asset-extract/nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb"
d = open(D, "rb").read()
sect = d[0x594:0x594 + 0x34680]


def dump(off, n, label):
    print("--- %s @SECT+0x%x ---" % (label, off))
    b = sect[off:off + n]
    for i in range(0, len(b), 16):
        row = b[i:i + 16]
        print("  %06x: %s  %s" % (off + i, " ".join("%02x" % x for x in row),
                                  "".join(chr(x) if 32 <= x < 127 else "." for x in row)))


for k in (5, 6, 13):
    off = 0x3B08 + 0x34 * k
    u = struct.unpack_from(">13I", sect, off)
    C, D, F, G = u[8], u[9], u[11], u[12]
    print("mesh %d: C=0x%x D=0x%x F=0x%x G=0x%08x  indexEnd=0x%x rem=%d" % (
        k, C, D, F, G, C + 3 + F * 3, D - 3 - F * 3))
    dump(C + 3 + F * 3, min(D - 3 - F * 3, 0x80), "mesh%d remainder" % k)
    print()
