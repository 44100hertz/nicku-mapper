#!/usr/bin/env python3
"""w4l: find GXSetArray definition + all GXSetVtxAttrFmt/GXSetArray call sites."""
import os, sys, re, collections

EXTRACT = os.environ.get("NICK_EXTRACT", "")
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

def dump_range(lo, hi, title, limit=200):
    print(f"\n===== {title} 0x{lo:08x}-0x{hi:08x} =====")
    cnt = 0
    for a, m, o in INS:
        if lo <= a < hi:
            print(f"  0x{a:08x}: {m} {o}")
            cnt += 1
            if limit and cnt >= limit:
                break

# find functions with slwi r3, r3, 3 (attr*8) — GXSetArray candidate
print("== slwi r3, r3, 3 sites (GXSetArray?) ==")
for i in range(len(INS)):
    a, m, o = INS[i]
    if m == "slwi" and "r3" in o and ", 3" in o:
        lo = max(0, i - 4)
        print(f"  0x{a:08x}: {m} {o}")
        for j in range(lo, min(i + 12, len(INS))):
            a2, m2, o2 = INS[j]
            print(f"     0x{a2:08x}: {m2} {o2}")
        print()
