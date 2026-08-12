#!/usr/bin/env python3
"""find_ptrs_to_range.py — find u32 values pointing into a RAM range."""
import struct
import sys

sys.path.insert(0, "/home/cyan/code/nickmapper-lua/asset-extract/tools")
from re_dol import load_sections

d, secs = load_sections()


def main(lo, hi, label=""):
    hits = []
    for a, o, s in secs:
        blob = d[o:o + s]
        for i in range(0, len(blob) - 4, 4):
            v = struct.unpack_from(">I", blob, i)[0]
            if lo <= v < hi:
                hits.append((a + i, v))
    print("%s [0x%08x, 0x%08x): %d hits" % (label, lo, hi, len(hits)))
    for h, v in hits[:40]:
        print("  value 0x%08x stored at 0x%08x" % (v, h))


if __name__ == "__main__":
    lo = int(sys.argv[1], 16)
    hi = int(sys.argv[2], 16)
    main(lo, hi, sys.argv[3] if len(sys.argv) > 3 else "")
