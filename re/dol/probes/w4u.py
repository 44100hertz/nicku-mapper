#!/usr/bin/env python3
"""w4u: dump 0x8003abbc (0x98 primitive cmd fn) + callers."""
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

def dump_range(lo, hi, title, limit=160):
    print(f"\n===== {title} 0x{lo:08x}-0x{hi:08x} =====")
    cnt = 0
    for a, m, o in INS:
        if lo <= a < hi:
            print(f"  0x{a:08x}: {m} {o}")
            cnt += 1
            if limit and cnt >= limit:
                break

dump_range(0x8003abbc, 0x8003ac40, "primitive-cmd fn (132B)")

print("\n== callers of 0x8003abbc ==")
for i in range(len(INS)):
    a, m, o = INS[i]
    if m == "bl" and imm(o) == 0x8003abbc:
        # caller window
        w = None
        for j in range(i - 1, max(0, i - 400), -1):
            if INS[j][1] == "blr":
                w = INS[j][0] + 4
                break
        print(f"  0x{a:08x} (func from 0x{w:x})")
