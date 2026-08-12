#!/usr/bin/env python3
"""pool_scan.py — fingerprint scan for the shared position pool.
Fingerprint: mesh1's 24 u16 posIdx values must resolve to y==0, x in [9.5,12.5], z in [-0.5,9.5].
Candidates: (a) s16x3 arrays at any offset in chunk 0; (b) s16x3 at chunk heads; (c) u16x3; (d) f32x3.
"""
import struct

PATH = "nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb"
d = open(PATH, "rb").read()
SECT = 0x594
sect = d[SECT:SECT + 0x34680]

def u32(o): return struct.unpack_from(">I", sect, o)[0]
def i16(o): return struct.unpack_from(">h", sect, o)[0]
def u16(o): return struct.unpack_from(">H", sect, o)[0]
def f32(o): return struct.unpack_from(">f", sect, o)[0]

hdrx = 0x20
sizes = []
for i in range(87):
    sizes.append(struct.unpack_from(">I", d, hdrx + i * 16)[0])
bases = []
acc = 0
for sz in sizes:
    bases.append(acc)
    acc += sz

# mesh1 u16 stream indices
A = u32(0x3B08 + 0x34 + 0x14)
cb = bases[2]
n = A // 6
indices = [u16(cb + 6 * i) for i in range(n)]
print("mesh1 indices:", indices)

# candidate ranges: chunk 0 entirely + each mesh chunk (skipping chunk0)
cands = [(0, sizes[0])]
for k in range(1, 87):
    cands.append((bases[k], sizes[k]))

def test(off, fmt, scale, stride, tol_y):
    """fmt: 'h','H','f'. Returns (score, hits)."""
    hits = 0
    miss = []
    for idx in indices:
        p = off + idx * stride
        if fmt == 'h':
            x = i16(p) * scale
            y = i16(p + 2) * scale
            z = i16(p + 4) * scale
        elif fmt == 'H':
            x = u16(p) * scale
            y = u16(p + 2) * scale
            z = u16(p + 4) * scale
        else:
            x = f32(p)
            y = f32(p + 4)
            z = f32(p + 8)
        if abs(y) <= tol_y and 9.5 <= x <= 12.5 and -0.5 <= z <= 9.5:
            hits += 1
        else:
            miss.append((idx, round(x, 2), round(y, 2), round(z, 2)))
    return hits, miss

best = []
for (bo, bs) in cands:
    for fmt, stride, scale in (('h', 6, 1.0), ('h', 6, 0.03125), ('H', 6, 1.0), ('f', 12, 1.0)):
        tol = 1.0 if fmt == 'h' else (2.0 if fmt == 'f' else 1.0)
        end = bo + bs - stride * max(indices)
        if end <= bo:
            continue
        step = 2 if fmt != 'f' else 4
        for off in range(bo, end, step):
            hits, miss = test(off, fmt, scale, stride, tol)
            if hits >= 20:
                best.append((hits, off, fmt, scale, miss[:4], bo, bs))

best.sort(key=lambda r: -r[0])
print("\ntop candidates (hits>=20):")
for hits, off, fmt, scale, miss, bo, bs in best[:15]:
    print("  hits=%d off=0x%x (chunk0? %s, base=0x%x size=0x%x) fmt=%s scale=%s miss=%s" %
          (hits, off, off < sizes[0], bo, bs, fmt, scale, miss))

# also test the cumulative C-block pool again but checking ONLY y==0 (b==0) consistency
print("\nC-block pool: y(b) values for mesh1 indices (should be all 0 if pool right):")
pool = []
cum = []
for k in range(86):
    off = 0x3B08 + 0x34 * k
    C, F = u32(off + 0x20), u32(off + 0x2C)
    body = sect[C + 3:C + 3 + F * 3]
    tris = [(body[i], body[i + 1], body[i + 2]) for i in range(0, len(body) - 2, 3)]
    cum.append(len(pool))
    pool.extend(tris)
for idx in indices:
    if idx < len(pool):
        print("  idx %4d -> triple %s" % (idx, pool[idx]))
    else:
        print("  idx %4d OUT" % idx)
