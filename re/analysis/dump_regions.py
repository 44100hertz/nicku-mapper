#!/usr/bin/env python3
"""Dump regions of SECT for structural analysis."""
import struct

PATH = "nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb"
SECT_FILE_OFF = 0x594
d = open(PATH, "rb").read()
sect = d[SECT_FILE_OFF:SECT_FILE_OFF + 0x34680]

def u32(off):
    return struct.unpack_from(">I", sect, off)[0]

def dump(lo, hi, label):
    print("=== %s (0x%x..0x%x) ===" % (label, lo, hi))
    for off in range(lo, hi, 4):
        v = u32(off)
        # annotate ASCII runs
        ascii_ctx = ""
        for a in range(off, min(off + 16, len(sect))):
            b = sect[a]
            if 0x20 <= b < 0x7f:
                ascii_ctx += chr(b)
            else:
                ascii_ctx += "."
        print("+0x%04x  %08x  |%s|" % (off, v, ascii_ctx))
    print()

dump(0x40, 0x1D40, "SkeletonHeader+Skeleton region")
