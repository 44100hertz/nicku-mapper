#!/usr/bin/env python3
"""find_gx.py — locate GX library code in main.dol via CP register (0xCC008000) writes."""
import struct
from dol import Dol

dol = Dol.load()
hits = []
for s in dol.sections:
    data = s["data"]
    base = s["ram"]
    regs = {}
    for i in range(0, len(data) - 4, 4):
        insn = struct.unpack(">I", data[i : i + 4])[0]
        a = base + i
        op = insn >> 26
        rd = (insn >> 21) & 31
        ra = (insn >> 16) & 31
        imm = insn & 0xFFFF
        sign = imm if not (imm & 0x8000) else imm - 0x10000
        if op == 15 and ra == 0 and imm == 0xCC00:
            regs[rd] = a
        elif op == 36:  # stw
            if ra in regs and imm in (0x8000, 0x7FFC):
                hits.append((regs[ra], a, "stw@0x%x" % imm))
        elif op == 38:  # stb
            if ra in regs and imm == 0x8000:
                hits.append((regs[ra], a, "stb@0x8000"))
print("GX CP writes found: %d" % len(hits))
hits.sort()
clusters = []
for h in hits:
    if clusters and h[0] - clusters[-1][-1][0] < 0x400:
        clusters[-1].append(h)
    else:
        clusters.append([h])
for cl in clusters:
    print(
        "  cluster @0x%08x..0x%08x (%d writes) first: %s"
        % (cl[0][0], cl[-1][0], len(cl), cl[0])
    )
