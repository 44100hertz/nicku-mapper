#!/usr/bin/env python3
"""w4m: find strip-walking code via 'addi rX,rX,6' / 'mulli rX,rX,6'."""
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

# 1. addi rX, rX, 6 (record walk)
print("== addi rX, rX, 6 (strip record walk) ==")
for i in range(len(INS)):
    a, m, o = INS[i]
    if m == "addi":
        r = re.findall(r'r(\d+)', o)
        v = imm(o)
        if r and len(r) == 2 and r[0] == r[1] and v == 6:
            lo = max(0, i - 8)
            ctx = " ".join(f"{INS[j][1]} {INS[j][2]}" for j in range(lo, i))
            print(f"  0x{a:08x}: {m} {o}   | prev: {ctx[:120]}")

# 2. mulli rX, rX, 6 or mulli with 6
print("\n== mulli ..., 6 ==")
for a, m, o in INS:
    if m == "mulli" and imm(o) == 6:
        print(f"  0x{a:08x}: {m} {o}")

# 3. lhz triplets: lhz with disp 0,2,4 within 3 insns
print("\n== lhz triple (0,2,4) candidates ==")
for i in range(len(INS) - 3):
    seq = []
    for j in range(i, min(i + 4, len(INS))):
        a, m, o = INS[j]
        if m == "lhz" and any(f"0x{d}(r" in o for d in (0, 2, 4, 6)):
            v = imm(o)
            seq.append((a, v))
        else:
            break
    if len(seq) >= 2 and any(x[1] == 2 for x in seq):
        print(f"  " + " ".join(f"0x{a:x}(d={v})" for a, v in seq))
