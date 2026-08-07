#!/usr/bin/env python3
"""w4t: find GXBegin-equivalent (fifo cmd 0x98/0x90/0x80) + draw callers."""
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

def imm(ops):
    m = re.findall(r'-?0x[0-9a-fA-F]+|(?<![\w.])-?\d+', ops)
    if not m:
        return None
    try:
        return int(m[-1], 0)
    except ValueError:
        return None

# find li rX, 0x98 (or 0x90/0x80) followed within 5 insns by a stb/stw to -0x8000(fifo)
print("== li 0x98/0x90/0x80 near fifo store ==")
for i in range(len(INS)):
    a, m, o = INS[i]
    if m == "li":
        v = imm(o)
        if v in (0x98, 0x90, 0x80, 0xa0, 0x88):
            for j in range(i + 1, min(i + 6, len(INS))):
                a2, m2, o2 = INS[j]
                if m2 in ("stb", "stw", "sth") and "-0x8000" in o2:
                    print(f"  li {v:#x} @0x{a:08x} -> {m2} @0x{a2:08x}: {o2}")
                    break

# find 'li rX, 0x98' anywhere (GX_TRIANGLE_STRIP cmd)
print("\n== all li rX, 0x98 ==")
for a, m, o in INS:
    if m == "li" and imm(o) == 0x98:
        print(f"  0x{a:08x}: {m} {o}")
