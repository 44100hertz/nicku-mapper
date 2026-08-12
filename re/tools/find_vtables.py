#!/usr/bin/env python3
"""find_vtables.py — locate vtable runs near class-name strings in main.dol."""
import struct
import re
import sys

sys.path.insert(0, "/home/cyan/code/nickmapper-lua/asset-extract/tools")
from re_dol import load_sections

d, secs = load_sections()


def in_code(v):
    return any(a <= v < a + s for a, o, s in secs)


def fo_of(addr):
    for a, o, s in secs:
        if a <= addr < a + s:
            return o + (addr - a)
    return None


def scan(base, size):
    fo = fo_of(base)
    if fo is None:
        print(f"{base:x} not in sections")
        return
    run = []
    blob = d[fo:fo + size]
    for k in range(0, size, 4):
        v = struct.unpack_from(">I", blob, k)[0]
        loc = base + k
        if in_code(v):
            run.append(loc)
        else:
            if len(run) >= 3:
                print(f"VTABLE @ 0x{run[0]:08x} ({len(run)} entries):")
                for r in run[:6]:
                    vv = struct.unpack_from(">I", blob, r - base)[0]
                    print(f"    0x{r:08x}: 0x{vv:08x}")
                if len(run) > 6:
                    print(f"    ... {len(run) - 6} more")
            run = []
    for m in re.finditer(rb"[\x20-\x7e]{3,}", blob):
        print(f"  str 0x{base + m.start():08x}: {m.group().decode()}")


if __name__ == "__main__":
    start = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0x8004C180
    size = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x2580
    scan(start, size)
