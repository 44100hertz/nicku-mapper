#!/usr/bin/env python3
"""find_u32.py — find where a u32 value appears in main.dol."""
import struct
import sys

sys.path.insert(0, "/home/cyan/code/nickmapper-lua/asset-extract/tools")
from re_dol import load_sections

d, secs = load_sections()


def find(v, label=""):
    hits = []
    for a, o, s in secs:
        blob = d[o:o + s]
        for i in range(0, len(blob) - 4, 4):
            if struct.unpack_from(">I", blob, i)[0] == v:
                hits.append(a + i)
    print("%s 0x%08x: %d hits %s" % (label, v, len(hits), [hex(h) for h in hits[:10]]))


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        v = int(arg, 16)
        find(v)
