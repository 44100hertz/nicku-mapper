#!/usr/bin/env python3
"""w4h: find symbol-name string block + xrefs (hi/hi+1) -> TTRB loader code."""
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

def dump_strings_around(addr, span=256):
    s = dol.ram_to_section(addr)
    if not s:
        return
    off = addr - s["ram"]
    chunk = s["data"][off - span // 2: off + span // 2]
    print(f"\n-- strings around 0x{addr:08x} --")
    for m in re.finditer(rb"[\x20-\x7e]{3,}", chunk):
        a = addr - span // 2 + m.start()
        print(f"  0x{a:08x}: {m.group().decode('ascii','replace')!r}")

dump_strings_around(0x8004c1d8, 200)
dump_strings_around(0x800af028, 200)

def load_sites(addr):
    hi = (addr >> 16) & 0xFFFF
    lo = addr & 0xFFFF
    out = []
    for i in range(len(INS)):
        a, m, o = INS[i]
        if m == "lis":
            v = imm(o)
            if v is None:
                continue
            vh = v & 0xFFFF
            if vh not in (hi, (hi + 1) & 0xFFFF):
                continue
            r = re.findall(r'r(\d+)', o)
            if not r:
                continue
            r = int(r[0])
            for j in range(i + 1, min(i + 7, len(INS))):
                a2, m2, o2 = INS[j]
                r2 = re.findall(r'r(\d+)', o2)
                if not r2 or int(r2[0]) != r:
                    continue
                v2 = imm(o2)
                if v2 is None:
                    continue
                cand = (vh << 16) + (v2 & 0xFFFF) if m2 == "ori" else ((vh << 16) + (v2 if v2 >= 0 else v2 + 0x10000))
                if cand & 0xFFFFFFFF == addr:
                    out.append((a, a2))
                    break
    return out

for target in (0x8004c1d8, 0x800af028):
    sites = load_sites(target)
    print(f"\n== xrefs to 0x{target:08x}: {len(sites)} ==")
    for (la, la2) in sites[:8]:
        print(f"  lis @0x{la:08x} addi @0x{la2:08x}")
