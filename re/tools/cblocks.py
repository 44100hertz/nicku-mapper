#!/usr/bin/env python3
"""cblocks.py — analyze all C-blocks (mesh record fields C/D) in the level."""
import struct

D = "/home/cyan/code/nickmapper-lua/asset-extract/nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb"
d = open(D, "rb").read()
sect = d[0x594:0x594 + 0x34680]


def dump(off, n, label):
    print("--- %s @SECT+0x%x ---" % (label, off))
    b = sect[off:off + n]
    for i in range(0, len(b), 16):
        row = b[i:i + 16]
        print("  %06x: %s" % (off + i, " ".join("%02x" % x for x in row)))


# mesh records at 0x3B08 + 0x34*k
print("mesh: C      D      E      F      G       first bytes of C-block")
for k in range(86):
    off = 0x3B08 + 0x34 * k
    u = struct.unpack_from(">13I", sect, off)
    C, D, E, F, G = u[8], u[9], u[10], u[11], u[12]
    head = " ".join("%02x" % x for x in sect[C:C + 8])
    print("%3d: %-6x %-6x %-6x %-5x %-8s | %s" % (k, C, D, E, F, hex(G), head))

print()
dump(0x126A0, 0x60, "mesh19 C-block (D=0x40, tiny)")
print()
dump(0x4C80, 0x20, "mesh0 C-block head again")
