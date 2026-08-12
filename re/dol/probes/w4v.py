#!/usr/bin/env python3
"""w4v: draw entry fns 0x8003aaec/0x8003e2d0 + their game callers."""
import os, sys, re

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

def dump_range(lo, hi, title, limit=160):
    print(f"\n===== {title} 0x{lo:08x}-0x{hi:08x} =====")
    cnt = 0
    for a, m, o in INS:
        if lo <= a < hi:
            print(f"  0x{a:08x}: {m} {o}")
            cnt += 1
            if limit and cnt >= limit:
                break

dump_range(0x8003aaec, 0x8003abb8, "draw entry A (204B)")

# callers of the two draw entries from game code
for target, name in ((0x8003aaec, "drawA"), (0x8003e2d0, "drawB")):
    print(f"\n== callers of {name} 0x{target:08x} ==")
    for i in range(len(INS)):
        a, m, o = INS[i]
        if m == "bl" and imm(o) == target:
            rv = {}
            for j in range(i - 1, max(0, i - 10) - 1, -1):
                a2, m2, o2 = INS[j]
                if m2 in ("li", "lis"):
                    r = re.findall(r'r(\d+)', o2)
                    v = imm(o2)
                    if r and int(r[-1]) not in rv and v is not None:
                        rv[int(r[-1])] = v & 0xFFFF
                if m2 == "blr":
                    break
            print(f"  0x{a:08x} r3={rv.get(3)} r4={rv.get(4)} r5={rv.get(5)} r6={rv.get(6)}")
