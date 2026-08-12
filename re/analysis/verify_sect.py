#!/usr/bin/env python3
"""Independent verification of SECT structure of SBWorld_Detail_Level01_01.trb"""
import struct

PATH = "nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb"
SECT_FILE_OFF = 0x594
SECT_SIZE = 0x34680

d = open(PATH, "rb").read()
sect = d[SECT_FILE_OFF:SECT_FILE_OFF + SECT_SIZE]

def u32(off):
    return struct.unpack_from(">I", sect, off)[0]

def f32(off):
    return struct.unpack_from(">f", sect, off)[0]

def u16(off):
    return struct.unpack_from(">H", sect, off)[0]

def i16(off):
    return struct.unpack_from(">h", sect, off)[0]

print("=== SECT 0x00..0x100 as u32/float mix ===")
for off in range(0, 0x100, 4):
    v = u32(off)
    f = struct.unpack(">f", struct.pack(">I", v))[0]
    extra = ""
    if 0x40 <= off < 0x50:
        extra = "  name: %r" % sect[0x40:0x4c]
    print("+0x%04x  %08x  %14.4f%s" % (off, v, f, extra))
