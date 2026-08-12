#!/usr/bin/env python3
"""w4p: full GX function roster."""
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

GX_LO, GX_HI = 0x800374d8, 0x8003f160

# function windows
starts = []
prev = None
for a, m, o in INS:
    if m == "blr":
        starts.append((prev, a))
        prev = a + 4

def has_fifo(a, b):
    for ad, m, o in INS:
        if ad >= b: return False
        if ad < a: continue
        if m == "stw" and "-0x8000(" in o:
            return True
    return False

roster = []
for (a, b) in starts:
    if a is None: continue
    if GX_LO <= a < GX_HI:
        body = [(ad, m, o) for ad, m, o in INS if a <= ad < b]
        fifo = has_fifo(a, b)
        # classify: count stw/sth, look for lhz/lwz reads
        stws = [o for ad, m, o in body if m == "stw"]
        roster.append((a, b - a, len(body), fifo, body[:6]))

for a, size, nins, fifo, head in sorted(roster):
    h = " | ".join(f"{m} {o}" for ad, m, o in head[:4])
    print(f"  0x{a:08x} size={size:5d} ins={nins:4d} fifo={int(fifo)}  {h[:110]}")
