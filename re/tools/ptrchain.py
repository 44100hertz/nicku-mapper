#!/usr/bin/env python3
"""ptrchain.py — follow pointer chains from a data address up to code."""
import struct
import sys

sys.path.insert(0, "/home/cyan/code/nickmapper-lua/asset-extract/tools")
from re_dol import load_sections, addr_to_off

d, secs = load_sections()


def find_u32(v):
    hits = []
    for a, o, s in secs:
        blob = d[o:o + s]
        for i in range(0, len(blob) - 4, 4):
            if struct.unpack_from(">I", blob, i)[0] == v:
                hits.append(a + i)
    return hits


def is_code(addr):
    return (0x80003100 <= addr < 0x80199A20) and not (0x80042480 <= addr < 0x800B6F40 and addr > 0x80051E00 and addr < 0x80051E00 + 0x400)

if __name__ == "__main__":
    start = int(sys.argv[1], 16)
    cur = start
    for depth in range(8):
        hits = find_u32(cur)
        print("addr 0x%08x referenced at: %s" % (cur, [hex(h) for h in hits[:10]]))
        if not hits:
            break
        nxt = hits[0]
        cur = nxt
