#!/usr/bin/env python3
"""w4j: find TRB container tag constants -> file parser/loader code."""
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

TAGS = {
    0x42465354: "TSFB", 0x54464252: "TRBF", 0x58444852: "HDRX",
    0x54434553: "SECT", 0x52454C43: "RELC", 0x534D4253: "SYMB",
    0x54544C46: "TTLF", 0x544E4146: "NTAF", 0x464E4946: "FINF",
    0x534C4F42: "BOLS", 0x54534C46: "FLST",
}
# also non-reversed (in case the code compares BE-loaded u32 against LE constant)
TAGS.update({((v >> 24) | ((v >> 8) & 0xFF00) | ((v & 0xFF00) << 8) | (v << 24)) & 0xFFFFFFFF: "rev:" + name for v, name in list(TAGS.items())})

def imm(ops):
    m = re.findall(r'-?0x[0-9a-fA-F]+|(?<![\w.])-?\d+', ops)
    if not m:
        return None
    try:
        return int(m[-1], 0)
    except ValueError:
        return None

found = {}
for i in range(len(INS)):
    a, m, o = INS[i]
    if m == "lis":
        v = imm(o)
        if v is None:
            continue
        vh = v & 0xFFFF
        for j in range(i + 1, min(i + 8, len(INS))):
            a2, m2, o2 = INS[j]
            if m2 in ("ori", "addi"):
                r = re.findall(r'r(\d+)', o)
                r2 = re.findall(r'r(\d+)', o2)
                if not r or not r2 or r[0] != r2[0]:
                    continue
                v2 = imm(o2)
                if v2 is None:
                    continue
                if m2 == "ori":
                    cand = (vh << 16) | v2
                else:
                    cand = (vh << 16) + (v2 if v2 >= 0 else v2 + 0x10000)
                cand &= 0xFFFFFFFF
                if cand in TAGS:
                    name = TAGS[cand]
                    found.setdefault(a, []).append((cand, name, a2))
                    break

print("tag constant sites:")
for a in sorted(found):
    for cand, name, a2 in found[a]:
        # find function window
        w = None
        for k in range(len(INS)):
            if INS[k][0] == a:
                lo = max(0, k - 12)
                print(f"  lis 0x{a:08x} -> {name} (0x{cand:08x}) [addi 0x{a2:08x}]")
                for q in range(lo, min(k + 2, len(INS))):
                    aa, mm, oo = INS[q]
                    print(f"     0x{aa:08x}: {mm} {oo}")
                break
