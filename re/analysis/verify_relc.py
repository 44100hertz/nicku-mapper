#!/usr/bin/env python3
"""Parse RELC raw + dump Collision/pointer-table region."""
import struct

PATH = "nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb"
d = open(PATH, "rb").read()

# RELC at file 0x34C14
relc_off = 0x34C14
tag = d[relc_off:relc_off+4]
size = struct.unpack_from(">I", d, relc_off+4)[0]
print("RELC tag=%r size=0x%x" % (tag, size))
pairs = []
for i in range(relc_off+8, relc_off+8+size, 8):
    off = struct.unpack_from(">I", d, i)[0]
    val = struct.unpack_from(">I", d, i+4)[0]
    pairs.append((off, val))
print("RELC entry count:", len(pairs))
print("First 40 offsets:", [hex(o) for o, v in pairs[:40]])

SECT = 0x594
sect = d[SECT:SECT+0x34680]

def u32(o): return struct.unpack_from(">I", sect, o)[0]

print()
print("=== 0x36C0..0x3B08 (Collision + table) ===")
for off in range(0x36C0, 0x3B08, 4):
    v = u32(off)
    # find ASCII
    ascii_ctx = ""
    for a in range(off, min(off + 12, len(sect))):
        b = sect[a]
        ascii_ctx += chr(b) if 0x20 <= b < 0x7f else "."
    rel = ""
    if off in [o for o, vv in pairs]:
        rel = "  <-- RELC"
    print("+0x%04x  %08x  |%s|%s" % (off, v, ascii_ctx, rel))
