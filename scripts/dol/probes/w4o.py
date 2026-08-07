#!/usr/bin/env python3
"""w4o: find the Toshi NameHash function (mulli by 31 / slwi 5 - sub)."""
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

print("== mulli rX, rY, 31 ==")
for a, m, o in INS:
    if m == "mulli" and imm(o) == 31:
        print(f"  0x{a:08x}: {m} {o}")

print("\n== slwi rX, rY, 5 + nearby sub (x*32 - x) ==")
for i in range(len(INS)):
    a, m, o = INS[i]
    if m == "slwi" and imm(o) == 5:
        r = re.findall(r'r(\d+)', o)
        if not r:
            continue
        rd, rs = int(r[0]), int(r[1])
        for j in range(i + 1, min(i + 4, len(INS))):
            a2, m2, o2 = INS[j]
            r2 = re.findall(r'r(\d+)', o2)
            if m2 == "sub" and len(r2) == 3 and int(r2[0]) == rd and int(r2[2]) == rs:
                print(f"  0x{a:08x}: {m} {o}  + 0x{a2:08x}: {m2} {o2}")
                break

# also: lbz + mulli pattern typical of the hash loop: hash = (c + hash*31) & 0xFFFF
print("\n== candidate hash-loop bodies (lbz + arithmetic + bdnz) ==")
for i in range(len(INS)):
    a, m, o = INS[i]
    if m == "lbz" and "0(r" in o:
        for j in range(i + 1, min(i + 10, len(INS))):
            a2, m2, o2 = INS[j]
            if m2 == "bdnz":
                # collect body
                body = " ".join(f"{INS[k][1]}" for k in range(i, j))
                if "mulli" in body or ("slwi" in body and "sub" in body):
                    print(f"  loop 0x{a:08x}-0x{a2:08x}: {body}")
                break
