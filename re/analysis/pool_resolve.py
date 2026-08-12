#!/usr/bin/env python3
"""pool_resolve.py — resolve u16 streams against candidate pools; determine y-scale."""
import struct
import re

PATH = "nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb"
ENTS = "nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBL1_Ents.ini"
d = open(PATH, "rb").read()
SECT = 0x594
sect = d[SECT:SECT + 0x34680]

def u32(o): return struct.unpack_from(">I", sect, o)[0]
def f32(o): return struct.unpack_from(">f", sect, o)[0]
def u16(o): return struct.unpack_from(">H", sect, o)[0]

hdrx = 0x20
sizes = []
for i in range(87):
    sizes.append(struct.unpack_from(">I", d, hdrx + i * 16)[0])
bases = []
acc = 0
for sz in sizes:
    bases.append(acc)
    acc += sz

# --- build cumulative pool: mesh order ---
pool = []          # list of (x, y_raw, z)
cum_start = []     # per-mesh start index in pool
for k in range(86):
    off = 0x3B08 + 0x34 * k
    fs = [f32(off + 4 * i) for i in range(4)]
    C, D, F = u32(off + 0x20), u32(off + 0x24), u32(off + 0x2C)
    xmin, xmax = min(fs[0], fs[1]), max(fs[0], fs[1])
    zmin, zmax = min(fs[2], fs[3]), max(fs[2], fs[3])
    body = sect[C + 3:C + 3 + F * 3]
    tris = [(body[i], body[i + 1], body[i + 2]) for i in range(0, len(body) - 2, 3)]
    cum_start.append(len(pool))
    amax = max((t[0] for t in tris), default=1) or 1
    cmax = max((t[2] for t in tris), default=1) or 1
    for (a, b, c) in tris:
        x = xmin + a * (xmax - xmin) / amax
        z = zmin + c * (zmax - zmin) / cmax
        pool.append((x, b, z))
total = len(pool)
print("pool size:", total)

# --- mesh 1 u16 stream ---
def u16_stream(mesh_k):
    A = u32(0x3B08 + 0x34 * mesh_k + 0x14)
    cb = bases[mesh_k + 1]
    cs = sizes[mesh_k + 1]
    n = min(A, cs) // 6
    recs = []
    for i in range(n):
        recs.append((u16(cb + 6 * i), u16(cb + 6 * i + 2), u16(cb + 6 * i + 4)))
    return recs

recs1 = u16_stream(1)
print("\nmesh1 u16 stream:", len(recs1), "records")
# resolve with cumulative pool
print("posIdx | world pos (pool idx)  | pair dist")
ok_inside = 0
for i, (p, u, n) in enumerate(recs1):
    if p < total:
        x, yb, z = pool[p]
        inside = (9.5 <= x <= 12.5) and (-0.5 <= z <= 9.5)
        if inside:
            ok_inside += 1
        tag = "IN" if inside else "OUT"
        if i % 2 == 0 and i + 1 < len(recs1):
            p2, _, _ = recs1[i + 1]
            x2, y2, z2 = pool[p2] if p2 < total else (0, 0, 0)
            dist = ((x - x2) ** 2 + (z - z2) ** 2) ** 0.5
            pd = "pair-dist %.2f" % dist
        else:
            pd = ""
        print("%6d | (%7.3f, %3d, %6.3f) %s %s" % (p, x, yb, z, tag, pd))
    else:
        print("%6d | OUT OF RANGE" % p)
print("inside-road count:", ok_inside, "/", len(recs1))

# --- entity y distribution ---
ys = []
for m in re.finditer(r"Position\s*=\s*\{\s*(-?[\d.]+)f?\s*,\s*(-?[\d.]+)f?\s*,\s*(-?[\d.]+)f?", open(ENTS).read()):
    ys.append(float(m.group(2)))
ys.sort()
print("\nentity y: count=%d min=%.3f max=%.3f" % (len(ys), min(ys), max(ys)))
import collections
hist = collections.Counter(round(y, 1) for y in ys)
print("entity y histogram (top 15):", hist.most_common(15))
near0 = sum(1 for y in ys if abs(y) < 0.5)
print("entities with |y|<0.5:", near0, "/", len(ys))

# --- per-mesh max slot-b ---
print("\nper-mesh max slot-b (top 20 by max):")
rows = []
for k in range(86):
    off = 0x3B08 + 0x34 * k
    C, F = u32(off + 0x20), u32(off + 0x2C)
    body = sect[C + 3:C + 3 + F * 3]
    tris = [(body[i], body[i + 1], body[i + 2]) for i in range(0, len(body) - 2, 3)]
    if not tris:
        rows.append((k, 0, 0))
        continue
    mb = max(t[1] for t in tris)
    rows.append((k, mb, len(set(t[1] for t in tris))))
rows.sort(key=lambda r: -r[1])
for k, mb, nv in rows[:20]:
    print("  mesh%2d max b=%3d distinct b=%d" % (k, mb, nv))
