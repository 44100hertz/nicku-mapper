#!/usr/bin/env python3
"""w4i: find data pointers to symbol-name strings + dump referencing code."""
import os, sys, re, struct

EXTRACT = os.environ.get("NICK_EXTRACT", "")
sys.path.insert(0, os.path.join(EXTRACT, "tools"))
from dol import Dol
from capstone import Cs, CS_ARCH_PPC, CS_MODE_BIG_ENDIAN

DOL = os.path.join(EXTRACT, "nicku-ntsc", "P-GNOE", "sys", "main.dol")
dol = Dol.load(DOL)
data = dol.data
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

# 1. scan whole file for BE pointers to the strings
for target in (0x800af028, 0x800af038, 0x800af044, 0x800af050):
    hits = []
    pat = struct.pack(">I", target)
    start = 0
    while True:
        i = data.find(pat, start)
        if i < 0:
            break
        ram = dol.file_to_ram(i)
        hits.append((i, ram))
        start = i + 1
    print(f"ptr 0x{target:08x}: {len(hits)} hits " + ", ".join(f"file 0x{o:x} ram 0x{r:x}" if r else f"file 0x{o:x} (unmapped)" for o, r in hits[:10]))

# 2. dump code around any hits that are in text
print("\n-- code near ptr hits --")
for target in (0x800af028, 0x800af038, 0x800af044):
    pat = struct.pack(">I", target)
    start = 0
    while True:
        i = data.find(pat, start)
        if i < 0:
            break
        ram = dol.file_to_ram(i)
        if ram is not None:
            # find enclosing function via window
            for j in range(len(INS)):
                a, m, o = INS[j]
                if a <= ram < a + 4:
                    lo = max(0, j - 14)
                    print(f"\n-- context around ptr 0x{target:08x} @ file 0x{i:x} ram 0x{ram:x} --")
                    for k in range(lo, min(j + 10, len(INS))):
                        a2, m2, o2 = INS[k]
                        mark = ">>>" if k == j else "   "
                        print(f"  {mark} 0x{a2:08x}: {m2} {o2}")
                    break
        start = i + 1
