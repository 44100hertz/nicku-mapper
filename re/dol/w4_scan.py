#!/usr/bin/env python3
"""w4: DOL analysis for GX vertex-format setup (Nicktoons Unite! GC)."""
import os, sys, re, struct, collections

EXTRACT = os.environ.get("NICK_EXTRACT", "/run/media/samp/787be337-88e4-4b95-92f9-45d37615cd02/games/console (other)/gcn+wii/extract")
sys.path.insert(0, os.path.join(EXTRACT, "tools"))
from dol import Dol
from capstone import Cs, CS_ARCH_PPC, CS_MODE_BIG_ENDIAN

DOL = os.path.join(EXTRACT, "nicku-ntsc", "P-GNOE", "sys", "main.dol")
dol = Dol.load(DOL)
data = dol.data
secs = dol.sections
md = Cs(CS_ARCH_PPC, CS_MODE_BIG_ENDIAN)

INS = []  # (addr, mnem, ops)
for s in secs:
    sd = s["data"]
    off = 0
    while off + 4 <= len(sd):
        r = list(md.disasm(sd[off:off + 4], s["ram"] + off))
        if r:
            INS.append((r[0].address, r[0].mnemonic, r[0].op_str))
        off += 4
IADDR = {a: (m, o) for a, m, o in INS}
print("total instructions:", len(INS))

def imm(ops):
    m = re.findall(r'-?0x[0-9a-fA-F]+|(?<![\w.])-?\d+', ops)
    if not m:
        return None
    try:
        return int(m[-1], 0)
    except ValueError:
        return None

def regs(ops, n):
    return re.findall(r'r(\d+)', ops)[:n]

def last_reg(ops):
    r = re.findall(r'r(\d+)', ops)
    return int(r[-1]) if r else None

# ---------- 1. strings of interest ----------
print("\n== strings ==")
targets = {}
for name in ["AWorldMeshHAL", "ANTWorldMesh", "ANTWorldMaterial", "ANTWorldShader",
             "ATerrainSection", "TTRB", "TModelCollision", "Collision", "Database",
             "SkeletonHeader", "GXSetArray", "GXSetVtxAttrFmt", "WorldMesh", "TTRBLoad"]:
    hits = dol.find_string(name)
    if hits:
        for addr, s in hits[:3]:
            print(f"  '{name}' @ 0x{addr:08x}: {s[:60]!r}")
            targets.setdefault(name, []).append(addr)

# ---------- 2. functions: windows between blr ----------
def func_windows():
    starts = []
    prev_end = None
    for addr, m, o in INS:
        if m == "blr":
            starts.append((prev_end, addr))
            prev_end = addr + 4
    return starts

FUNCS = func_windows()
print("\nfunctions (windows):", len(FUNCS))

def window_of(addr):
    for (a, b) in FUNCS:
        if a is not None and a <= addr < b:
            return (a, b)
    return None

# ---------- 3. GX FIFO-writer detection ----------
# GX immediate setters write via lis rX,0xCC00 / stw ...,0x8000(rX)
fifo_funcs = set()
for (a, b) in FUNCS:
    if a is None:
        continue
    liscc = {}
    stw = []
    for i in range(len(INS)):
        addr, m, o = INS[i]
        if addr >= b: break
        if addr < a: continue
        if m == "lis":
            r = last_reg(o)
            v = imm(o)
            if v is not None and (v & 0xFFFF0000) == 0xCC000000:
                liscc[r] = addr
        elif m in ("stw", "sth", "stb") and "0x8000" in o:
            stw.append((addr, o))
    if liscc and stw:
        fifo_funcs.add((a, b, sorted(liscc.items()), stw[:3]))
print("\nFIFO-writer (GX setter) functions:", len(fifo_funcs))

# map fifo func start -> (window, liscc)
FIFO_START = {a: (a, b, lc, st) for (a, b, lc, st) in fifo_funcs}

# find all bl targets that land inside fifo windows
gx_calls = collections.defaultdict(list)  # target_addr -> [site_addr]
for addr, m, o in INS:
    if m == "bl":
        t = imm(o)
        if t is not None and t in FIFO_START:
            gx_calls[t].append(addr)
print("call sites to FIFO-writers:", sum(len(v) for v in gx_calls.values()))

# ---------- 4. classify GX call sites by argument setup ----------
GX_VA = {0: "PNMTXIDX", 1: "TEX0MTXIDX", 2: "TEX1MTXIDX", 9: "POS", 10: "NRM",
         11: "CLR0", 12: "CLR1", 13: "TEX0", 14: "TEX1", 15: "TEX2"}

def setup_before(idx, n=12):
    """Scan instructions before INS[idx] (a bl) for li rX, imm; return reg->val latest set."""
    regs_val = {}
    lo = max(0, idx - n)
    for i in range(idx - 1, lo - 1, -1):
        addr, m, o = INS[i]
        if m in ("li", "lis"):
            r = last_reg(o)
            v = imm(o)
            if r is not None and v is not None and r not in regs_val:
                regs_val[r] = (v & 0xFFFF if m == "lis" else (v & 0xFFFF if m == "li" else v))
                if m == "lis":
                    regs_val[r] = v
                else:
                    regs_val[r] = v if v >= 0 else v & 0xFFFF
        if m in ("blr", "b"):
            break
    return regs_val

report = []
for taddr, sites in sorted(gx_calls.items()):
    w = FIFO_START[taddr]
    for site in sites:
        idx = next(i for i, x in enumerate(INS) if x[0] == site)
        rv = setup_before(idx)
        r3 = rv.get(3); r4 = rv.get(4); r5 = rv.get(5); r6 = rv.get(6); r7 = rv.get(7)
        attr = GX_VA.get(r3, "attr?%s" % r3)
        report.append((site, taddr, r3, r4, r5, r6, r7, attr))

print("\n== GX setter call sites (site, target, r3=attr, r4, r5, r6, r7) ==")
for site, taddr, r3, r4, r5, r6, r7, attr in report:
    print(f"  bl 0x{site:08x} -> GX@0x{taddr:08x}  r3={r3}({attr}) r4={r4} r5={r5} r6={r6} r7={r7}")

# ---------- 5. string xrefs (lis+addi loading string addresses) ----------
def load_sites(addr):
    """find lis rX, hi + (addi/ori) rX, rX, lo == addr"""
    hi = (addr >> 16) & 0xFFFF
    lo = addr & 0xFFFF
    out = []
    for i in range(len(INS)):
        a, m, o = INS[i]
        if m == "lis":
            v = imm(o)
            if v is not None and (v & 0xFFFF) == hi:
                r = last_reg(o)
                for j in range(i + 1, min(i + 7, len(INS))):
                    a2, m2, o2 = INS[j]
                    r2 = last_reg(o2)
                    if r2 != r: continue
                    if m2 == "addi":
                        v2 = imm(o2)
                        if v2 is not None:
                            cand = (hi << 16) + (v2 if v2 >= 0 else v2 + 0x10000)
                            if cand == addr:
                                out.append((a, a2))
                                break
                    elif m2 == "ori":
                        v2 = imm(o2)
                        if v2 is not None and (hi << 16 | v2) == addr:
                            out.append((a, a2))
                            break
    return out

print("\n== string xrefs ==")
for name, addrs in targets.items():
    for addr in addrs:
        sites = load_sites(addr)
        if sites:
            for (la, la2) in sites[:4]:
                w = window_of(la)
                print(f"  '{name}' 0x{addr:08x} loaded @ 0x{la:08x} (addi 0x{la2:08x}) func=[0x{(w[0] if w else 0):08x},0x{(w[1] if w else 0):08x}]")

# ---------- 6. GXSetArray-like: bl with r3 attr small, r5 stride small, non-FIFO target ----------
print("\n== candidate GXSetArray / attr-setup calls (non-FIFO targets) ==")
strides = {3, 4, 6, 8, 12, 16, 24, 32, 48, 52, 64}
count = 0
for i in range(len(INS)):
    addr, m, o = INS[i]
    if m != "bl":
        continue
    t = imm(o)
    if t is None or t in FIFO_START:
        continue
    rv = setup_before(i)
    r3 = rv.get(3); r5 = rv.get(5)
    if r3 in GX_VA and r5 in strides and r5 is not None:
        w = window_of(addr)
        count += 1
        if count <= 60:
            print(f"  bl 0x{addr:08x} -> 0x{t:08x}  r3={r3}({GX_VA[r3]}) r4={rv.get(4)} r5={r5}(stride?) r6={rv.get(6)} func=[0x{(w[0] if w else 0):08x},0x{(w[1] if w else 0):08x}]")
print("total such sites:", count)

# ---------- 7. dump windows around the most promising sites ----------
def dump(addr, n=30, title=""):
    print(f"\n-- {title} @ 0x{addr:08x} --")
    for i in range(len(INS)):
        if INS[i][0] == addr:
            lo = max(0, i - n)
            hi = min(len(INS), i + n + 1)
            for j in range(lo, hi):
                a2, m2, o2 = INS[j]
                mark = ">>>" if j == i else "   "
                print(f"  {mark} 0x{a2:08x}: {m2} {o2}")
            break

print("\n== sample FIFO-writer functions ==")
for k, (a, b, lc, st) in enumerate(sorted(fifo_funcs)[:5]):
    print(f"  GX func 0x{a:08x}-0x{b:08x} liscc={lc} stw={st}")

# also: mulli rX, rY, 6  (strip record *6) and slwi by 2/3 near bl
print("\n== mulli/slwi stride constants near bl ==")
for i in range(len(INS)):
    addr, m, o = INS[i]
    if m == "bl":
        rv = setup_before(i, 14)
        for r, v in sorted(rv.items()):
            if v in (6, 12, 24, 48) and r in (5, 6, 7):
                w = window_of(addr)
                print(f"  bl 0x{addr:08x}: r{r}={v}  func=[0x{(w[0] if w else 0):08x},0x{(w[1] if w else 0):08x}]")
