#!/usr/bin/env python3
"""w4s: dump GXInit tail + game GX-state functions."""
import os, sys, re

EXTRACT = os.environ.get("NICK_EXTRACT", "/run/media/samp/787be337-88e4-4b95-92f9-45d37615cd02/games/console (other)/gcn+wii/extract")
sys.path.insert(0, os.path.join(EXTRACT, "tools"))
from dol import Dol
from capstone import Cs, CS_ARCH_PPC, CS_MODE_BIG_ENDIAN

DOL = os.path.join(EXTRACT, "nicku-ntsc", "P-GNOE", "sys", "main.dol")
dol = Dol.load(DOL)
md = Cs(CS_ARCH_PPC, CS_MODE_BIG_ENDIAN)
INS = []
for s in dol.sections:
    sd = s["data"]
    off = 0
    while off + 4 <= len(sd):
        r = list(md.disasm(sd[off:off + 4], s["ram"] + off))
        if r:
            INS.append((r[0].address, r[0].mnemonic, r[0].op_str))
        off += 4

def dump_range(lo, hi, title, limit=200):
    print(f"\n===== {title} 0x{lo:08x}-0x{hi:08x} =====")
    cnt = 0
    for a, m, o in INS:
        if lo <= a < hi:
            print(f"  0x{a:08x}: {m} {o}")
            cnt += 1
            if limit and cnt >= limit:
                break

dump_range(0x80037640, 0x80037668, "GXInit tail")
dump_range(0x80041d90, 0x80041df8, "game fn calling 0x8003780c (104B)")
dump_range(0x80041f58, 0x80041f60, "game GX-state fn (start)")
