#!/usr/bin/env python3
"""w4e: callers of GX functions from game code + argument setup."""
import os, sys, re, collections

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

GX_LO, GX_HI = 0x800374d8, 0x8003f160

def imm(ops):
    m = re.findall(r'-?0x[0-9a-fA-F]+|(?<![\w.])-?\d+', ops)
    if not m:
        return None
    try:
        return int(m[-1], 0)
    except ValueError:
        return None

def func_windows():
    starts = []
    prev = None
    for a, m, o in INS:
        if m == "blr":
            starts.append((prev, a))
            prev = a + 4
    return [w for w in starts if w[0] is not None]

FUNCS = func_windows()
def window_of(addr):
    for (a, b) in FUNCS:
        if a <= addr < b:
            return (a, b)
    return None

def setup_before(idx, n=14):
    rv = {}
    lo = max(0, idx - n)
    for i in range(idx - 1, lo - 1, -1):
        a, m, o = INS[i]
        if m in ("li", "lis"):
            r = re.findall(r'r(\d+)', o)
            v = imm(o)
            if r and v is not None and int(r[-1]) not in rv:
                rv[int(r[-1])] = v & 0xFFFF
        if m == "blr":
            break
    return rv

# all bl to GX region from game code
calls = []  # (site, target, caller_func, rv)
for i in range(len(INS)):
    a, m, o = INS[i]
    if m == "bl":
        t = imm(o)
        if t is not None and GX_LO <= t < GX_HI:
            w = window_of(a)
            if w and not (GX_LO <= w[0] < GX_HI):  # caller outside GX
                calls.append((a, t, w, setup_before(i)))

print("GX calls from game code:", len(calls))
by_func = collections.defaultdict(list)
for a, t, w, rv in calls:
    by_func[w[0]].append((a, t, rv))

GX_VA = {0:"PNMTXIDX",1:"TEX0MTXIDX",2:"TEX1MTXIDX",3:"TEX2MTXIDX",9:"POS",10:"NRM",11:"CLR0",12:"CLR1",13:"TEX0",14:"TEX1",15:"TEX2",16:"TEX3",17:"TEX4",18:"TEX5",19:"TEX6",20:"TEX7"}

# print caller functions sorted by number of GX calls
for f, lst in sorted(by_func.items(), key=lambda kv: -len(kv[1])):
    w = window_of(f)
    size = w[1] - w[0] if w else 0
    print(f"\n### caller func 0x{f:08x} (size {size}) - {len(lst)} GX calls")
    for a, t, rv in lst[:14]:
        r3 = GX_VA.get(rv.get(3), rv.get(3))
        print(f"   bl 0x{a:08x} -> GX 0x{t:08x}  r3={r3} r4={rv.get(4)} r5={rv.get(5)} r6={rv.get(6)} r7={rv.get(7)}")
