#!/usr/bin/env python3
"""w4n: dump function containing 0x8003f2c0."""
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

# find function bounds (backward to previous blr, forward to next blr)
idx = next(i for i, x in enumerate(INS) if x[0] == 0x8003f2c0)
lo = idx
while lo > 0 and INS[lo - 1][1] != "blr":
    lo -= 1
hi = idx
while hi < len(INS) and INS[hi][1] != "blr":
    hi += 1
print(f"function 0x{INS[lo][0]:08x} - 0x{INS[hi][0]+4:08x}")
for a, m, o in INS[lo:hi + 1]:
    print(f"  0x{a:08x}: {m} {o}")
