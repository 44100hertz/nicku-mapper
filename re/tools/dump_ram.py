#!/usr/bin/env python3
"""dump_ram.py — dump raw bytes of main.dol at a RAM address."""
import struct
import sys

sys.path.insert(0, "/home/cyan/code/nickmapper-lua/asset-extract/tools")
from re_dol import load_sections, addr_to_off

d, secs = load_sections()


def dump(addr, n, label=""):
    off = addr_to_off(d, secs, addr)
    if off is None:
        print("no section for", hex(addr))
        return
    print("--- %s @0x%08x (file 0x%x) ---" % (label, addr, off))
    b = d[off:off + n]
    for i in range(0, len(b), 16):
        row = b[i:i + 16]
        print("  %08x: %-47s %s" % (addr + i, " ".join("%02x" % x for x in row),
                                    "".join(chr(x) if 32 <= x < 127 else "." for x in row)))


if __name__ == "__main__":
    addr = int(sys.argv[1], 16)
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 128
    dump(addr, n, sys.argv[3] if len(sys.argv) > 3 else "")
