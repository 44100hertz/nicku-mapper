#!/usr/bin/env python3
"""w4b: deeper DOL probes."""
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
print("total insns:", len(INS))
from collections import Counter
per_sec = Counter(a >> 24 for a, m, o in INS)
print("per high-byte:", dict(per_sec))

def imm(ops):
    m = re.findall(r'-?0x[0-9a-fA-F]+|(?<![\w.])-?\d+', ops)
    if not m:
        return None
    try:
        return int(m[-1], 0)
    except ValueError:
        return None

# 1. any lis 0xCC00 ?
print("\n== lis 0xCC00 sites ==")
n = 0
for a, m, o in INS:
    if m == "lis" and imm(o) is not None and (imm(o) & 0xFFFF0000) == 0xCC000000:
        print(f"  0x{a:08x}: {m} {o}")
        n += 1
print("count:", n)

# 2. any stw with 0x8000 disp ?
print("\n== stw ..,0x8000(rX) sites ==")
n = 0
for a, m, o in INS:
    if m == "stw" and "0x8000" in o:
        print(f"  0x{a:08x}: {m} {o}")
        n += 1
print("count:", n)

# 3. li 0x34 / mulli 52 (mesh record stride) and li 6
print("\n== li rX, 0x34 / 52 ==")
for a, m, o in INS:
    if m == "li" and imm(o) in (0x34, 52):
        print(f"  0x{a:08x}: {m} {o}")
print("\n== mulli rX, rY, 52 ==")
for a, m, o in INS:
    if m == "mulli" and imm(o) in (52, 6, 12):
        print(f"  0x{a:08x}: {m} {o}")

# 4. dump functions
def dump_range(lo, hi, title):
    print(f"\n===== {title} 0x{lo:08x}-0x{hi:08x} =====")
    for a, m, o in INS:
        if lo <= a < hi:
            print(f"  0x{a:08x}: {m} {o}")

dump_range(0x80037e0c, 0x80038740, "func with r5=6 calls")
