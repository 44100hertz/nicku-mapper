#!/usr/bin/env python3
"""smooth_test.py — test if u16 streams index concatenated smooth-mesh s16 arrays; check mesh13 triples."""
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

# smooth meshes and their s16 arrays
smooth = [5, 6, 7, 8, 9, 13, 38, 45, 69]
pool = []   # (mesh_k, array)
for k in smooth:
    off = 0x3B08 + 0x34 * k
    B = u32(off + 0x18)
    cb = bases[k + 1]
    n = B // 6
    arr = []
    for i in range(n):
        arr.append((i16(cb + 6 * i), i16(cb + 6 * i + 2), i16(cb + 6 * i + 4)))
    pool.append((k, arr))
    print("mesh%2d s16 array: %d verts (B=0x%x), first3=%s, last3=%s" %
          (k, n, B, arr[:3], arr[-3:]))
tot = sum(len(a) for _, a in pool)
print("total s16 verts:", tot)

# mesh1 u16 stream indices
A = u32(0x3B08 + 0x34 + 0x14)
cb = bases[2]
n = A // 6
indices = [u16(cb + 6 * i) for i in range(n)]
print("\nmesh1 indices:", indices)

# resolve against concatenated s16 pool at 1/32
print("\nresolve at 1/32 (x/32, y/32, z/32):")
flat = [v for _, arr in pool for v in arr]
for idx in indices:
    if idx < len(flat):
        x, y, z = flat[idx]
        print("  idx %4d -> (%7.2f, %6.2f, %7.2f)" % (idx, x / 32, y / 32, z / 32))
    else:
        print("  idx %4d OUT" % idx)

# mesh13 C-block triples: slot-a max?
print("\nmesh13 C-block triple slot stats:")
off = 0x3B08 + 0x34 * 13
C, D, F = u32(off + 0x20), u32(off + 0x24), u32(off + 0x2C)
body = sect[C + 3:C + 3 + F * 3]
tris = [(body[i], body[i + 1], body[i + 2]) for i in range(0, F * 3, 3)]
print("  F=%d; slot-a max=%d, slot-b max=%d, slot-c max=%d" %
      (F, max(t[0] for t in tris), max(t[1] for t in tris), max(t[2] for t in tris)))
print("  first 10 triples:", tris[:10])
# what follows the F triples? (extra stream)
extra_off = C + 3 + F * 3
extra = sect[extra_off:C + D]
print("  extra bytes: %d, first 32: %s" % (len(extra), extra[:32].hex()))
# extra as u16 triples
e16 = [(u16(extra_off + 6 * i), u16(extra_off + 6 * i + 2), u16(extra_off + 6 * i + 4)) for i in range(len(extra) // 6)]
print("  extra u16-triple max per slot:", max(t[0] for t in e16), max(t[1] for t in e16), max(t[2] for t in e16))
print("  first 8:", e16[:8])
