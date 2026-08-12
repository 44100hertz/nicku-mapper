#!/usr/bin/env python3
"""w4c: find GX library + GXSetArray/GXSetVtxAttrFmt + callers."""
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

def last_reg(ops):
    r = re.findall(r'r(\d+)', ops)
    return int(r[-1]) if r else None

# 1. GX base loads: lis with low16 0xCC00 or 0xCC01
print("== lis loading 0xCC00xxxx / 0xCC01xxxx ==")
bases = {}
for a, m, o in INS:
    if m == "lis":
        v = imm(o)
        if v is not None and (v & 0xFFFF0000) in (0xCC000000, 0xCC010000):
            bases.setdefault(v & 0xFFFF0000, []).append((a, last_reg(o), v))
for k, v in sorted(bases.items()):
    print(f"  base 0x{k:08x}: {len(v)} sites, first: {[(hex(a), r) for a, r, _ in v[:6]]}")

# 2. FIFO write sites: stw .., -0x8000(rX) or +0x0(rX) after base load
fifo = []
for a, m, o in INS:
    if m == "stw" and ("-0x8000" in o or "-0x8000(" in o):
        fifo.append((a, o))
print("\nFIFO-ish stw count:", len(fifo), "range:", hex(min(a for a, _ in fifo)), hex(max(a for a, _ in fifo)))

# 3. window map: blr-based function windows over the whole binary
def func_windows():
    starts = []
    prev = None
    for a, m, o in INS:
        if m == "blr":
            starts.append((prev, a))
            prev = a + 4
    return [w for w in starts if w[0] is not None]

FUNCS = func_windows()
print("functions:", len(FUNCS))

def window_of(addr):
    lo, hi = 0, len(FUNCS)
    for (a, b) in FUNCS:
        if a <= addr < b:
            return (a, b)
    return None

# GX region = functions containing fifo stw
gx_funcs = {}
for (a, b) in FUNCS:
    has = False
    for addr, o in fifo:
        if a <= addr < b:
            has = True
            break
    if has:
        gx_funcs[a] = (a, b)
print("\nGX functions (contain fifo stw):", len(gx_funcs))
xs = sorted(gx_funcs)
if xs:
    print("  range:", hex(xs[0]), "-", hex(gx_funcs[xs[-1]][1]))

# 4. GXSetArray definition search: function that stw's to a global (not fifo) with r3=attr
#    Signature GXSetArray(attr, base, stride): typical body:
#      lis r4, ...; lwz r5, ... ; slwi r3, r3, 2 ; stw r4, 0(r5,r3)...
#    Look for short functions in GX region that take r3 small and store 3 words.
#    Instead: find all functions whose BODY references a lis 0xCC01 base (fifo writers) = GX setters.
#    Then find GXSetArray by signature: it does NOT write fifo but writes 2 words to a table.
#    Heuristic: functions with 'slwi rX, r3, 2' or 'slwi rX, r3, 3' and stw to (rY,rX).

print("\n== functions with slwi rX,r3,n + stw (GXSetArray-like) ==")
for (a, b) in gx_funcs.values():
    body = [(ad, m, o) for ad, m, o in INS if a <= ad < b]
    for ad, m, o in body:
        if m == "slwi" and "r3" in o and ", 2" in o:
            print(f"  0x{a:08x} ({b-a} bytes): slwi @0x{ad:08x}: {m} {o}")
            break

# 5. dump one fifo function fully to see the write pattern
def dump_range(lo, hi, title, limit=None):
    print(f"\n===== {title} 0x{lo:08x}-0x{hi:08x} =====")
    cnt = 0
    for a, m, o in INS:
        if lo <= a < hi:
            print(f"  0x{a:08x}: {m} {o}")
            cnt += 1
            if limit and cnt >= limit:
                break

if xs:
    dump_range(xs[0], gx_funcs[xs[0]][1], "first GX function", limit=90)
