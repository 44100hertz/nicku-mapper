#!/usr/bin/env python3
"""w4q: all callers of GXSetVtxAttrFmt(0x80039764)/GXSetVtxDesc(0x80038ea4)/
getters 0x80038e94/0x80038e9c/0x80038954."""
import os, sys, re, collections

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

starts = []
prev = None
for a, m, o in INS:
    if m == "blr":
        starts.append((prev, a))
        prev = a + 4

def window_of(addr):
    for (a, b) in starts:
        if a is not None and a <= addr < b:
            return (a, b)
    return None

for target, name in ((0x80039764, "GXSetVtxAttrFmt"), (0x80038ea4, "GXSetVtxDesc"),
                     (0x80038e94, "getter -0x5b00"), (0x80038e9c, "getter -0x5afc"),
                     (0x80038954, "store2 (base,stride)")):
    print(f"\n== callers of 0x{target:08x} ({name}) ==")
    cnt = 0
    for i in range(len(INS)):
        a, m, o = INS[i]
        if m == "bl" and imm(o) == target:
            w = window_of(a)
            # arg setup
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
            r3 = rv.get(3)
            extra = ""
            if target == 0x80039764:
                extra = f"r4={rv.get(4)} r5={rv.get(5)} r6={rv.get(6)} r7={rv.get(7)}"
            elif target in (0x80038ea4,):
                extra = f"r4={rv.get(4)}"
            elif target == 0x80038954:
                extra = f"r4={rv.get(4)} r5={rv.get(5)}"
            print(f"  0x{a:08x} in func [0x{(w[0] if w else 0):08x},0x{(w[1] if w else 0):08x}]  r3={r3} {extra}")
            cnt += 1
            if cnt > 25:
                print("  ...")
                break
