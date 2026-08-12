#!/usr/bin/env python3
"""Scan for the global position pool referenced by u16 posIdx."""
import os, struct

EXTRACT = os.environ.get("NICK_EXTRACT", "")

PATH = os.path.join(EXTRACT, "nicku-ntsc", "P-GNOE", "files", "Data", "SpongeBobLevel1", "SBWorld_Detail_Level01_01.trb")
d = open(PATH, "rb").read()
SECT = 0x594
sect = d[SECT:SECT + 0x34680]

def u16(o): return struct.unpack_from(">H", sect, o)[0]
def i16(o): return struct.unpack_from(">h", sect, o)[0]
def u32(o): return struct.unpack_from(">I", sect, o)[0]
def f32(o): return struct.unpack_from(">f", sect, o)[0]

sizes = [struct.unpack_from(">I", d, 0x20 + 16 * i)[0] for i in range(87)]
bases = []
acc = 0
for s in sizes:
    bases.append(acc); acc += s

# mesh1 stream: 24 triples, first field = posIdx
mesh1 = [(0x128,0x252,5),(0x10e,0x24b,5),(0x104,0x233,5),(0x12d,0x239,5),(0x24a,0x26f,5),
         (0x245,0x288,5),(0x369,0x2a3,5),(0x364,0x2bc,5),(0xb1,0x32a,5),(0xbc,0x333,5),
         (0x6a,0x325,5),(0x82,0x22a,5),(0x95,0x217,5),(0x79,0x325,5),(0x3c5,0x3db,5),
         (0x3ca,0x2c3,5),(0x3d6,0x2ba,5),(0x3d2,0x3dc,5),(0x44b,0x2de,5),(0x400,0x3d1,5),
         (0x3f4,0x3cc,5),(0x443,0x2cc,5),(0x487,0x2e4,5),(0x48a,0x2ce,5)]
mesh1_pos = [t[0] for t in mesh1]

# mesh0 stream from chunk 1
cb0, cs0 = bases[1], sizes[1]
A0 = u32(0x3B08 + 0x14)
n0 = A0 // 6
mesh0 = [(u16(cb0 + 6 * i), u16(cb0 + 6 * i + 2), u16(cb0 + 6 * i + 4)) for i in range(n0)]
mesh0_pos = [t[0] for t in mesh0]
print("mesh0 stream: %d triples, posIdx min %d max %d" % (len(mesh0), min(mesh0_pos), max(mesh0_pos)))

# Road strip expected geometry for mesh1 (from verified facts)
# x in [9.92,11.91], z in [0.08,8.98], y ~ 0

def check_pool(O, stride, fmt, scale, comps):
    """fmt: 's16'/'u16'/'f32'. comps: which 3 of the components are (x,y,z). Returns (score, pts)."""
    def rd(off, fmt):
        if fmt == 's16': return i16(O + off)
        if fmt == 'u16': return u16(O + off)
        return f32(O + off)
    def comp(off, j):
        return rd(off + j * 4 if fmt == 'f32' else off + j * 2, fmt)
    pts = []
    ok = 0
    for idx in mesh1_pos:
        base = idx * stride
        c = [comp(base, j) for j in range(4)]
        x = c[comps[0]] * scale
        y = c[comps[1]] * scale
        z = c[comps[2]] * scale
        pts.append((x, y, z))
        if abs(y) < 0.5 and 9.0 <= x <= 12.9 and -0.5 <= z <= 10.0:
            ok += 1
    return ok, pts

results = []
# scan chunk 0 [0,0x4C80) plus whole sect for completeness (byte-aligned), stride 6,8,12
for fmt in ('s16', 'u16', 'f32'):
    strides = (6, 8, 12) if fmt != 'f32' else (12,)
    for stride in strides:
        for comps in ((0,1,2),(0,2,1)):
            scale = 1.0/32.0 if fmt != 'f32' else 1.0
            # scan whole SECT at stride alignment offsets
            for O in range(0, 0x34680 - 2600 * stride, 2):
                ok, pts = check_pool(O, stride, fmt, scale, comps)
                if ok >= 20:
                    results.append((ok, fmt, stride, comps, O, scale, pts))
results.sort(key=lambda r: -r[0])
for r in results[:30]:
    ok, fmt, stride, comps, O, scale, pts = r
    print("OK=%d fmt=%s stride=%d comps=%s O=0x%x (%.4f): " % (ok, fmt, stride, comps, O, scale))
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]; zs = [p[2] for p in pts]
    print("   x[%.3f..%.3f] y[%.3f..%.3f] z[%.3f..%.3f]" % (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))
