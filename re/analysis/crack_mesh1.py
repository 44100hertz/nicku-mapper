#!/usr/bin/env python3
"""crack_mesh1.py — full byte-level autopsy of mesh 1 (the road) and its chunk 2 + C-block."""
import struct

PATH = "nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb"
d = open(PATH, "rb").read()
SECT = 0x594
sect = d[SECT:SECT + 0x34680]

def u32(o): return struct.unpack_from(">I", sect, o)[0]
def f32(o): return struct.unpack_from(">f", sect, o)[0]
def u16(o): return struct.unpack_from(">H", sect, o)[0]
def i16(o): return struct.unpack_from(">h", sect, o)[0]

hdrx = 0x20
sizes = []
for i in range(87):
    sizes.append(struct.unpack_from(">I", d, hdrx + i * 16)[0])
bases = []
acc = 0
for sz in sizes:
    bases.append(acc)
    acc += sz

# mesh 1 record
off = 0x3B08 + 0x34 * 1
print("mesh1 record @0x%x:" % off)
for i in range(13):
    v = u32(off + 4 * i)
    f = f32(off + 4 * i)
    print("  +0x%02x  u32=%08x  f32=%10.4f" % (4 * i, v, f))

A, B, C, D, F, G = u32(off + 0x14), u32(off + 0x18), u32(off + 0x20), u32(off + 0x24), u32(off + 0x2C), u32(off + 0x30)
print("A=%x B=%x C=%x D=%x F=%x G=%x" % (A, B, C, D, F, G))

# chunk 2 = mesh 1 chunk (k+1=2)
cb = bases[2]
cs = sizes[2]
print("\nchunk 2 @0x%x size 0x%x (%d bytes)" % (cb, cs, cs))
print("raw bytes (u16 BE):")
u16s = [u16(cb + i) for i in range(0, cs, 2)]
for i in range(0, len(u16s), 8):
    print("  %04x: %s" % (i * 2, " ".join("%04x" % v for v in u16s[i:i + 8])))

# C-block for mesh 1
print("\nC-block @0x%x size 0x%x:" % (C, D))
print("  head: %s" % sect[C:C + 16].hex())
print("  u16 at C+1: 0x%x (expect F=0x%x)" % (u16(C + 1), F))
n = F
print("  triples (a,b,c):")
trip = []
for i in range(n):
    t = (sect[C + 3 + 3 * i], sect[C + 4 + 3 * i], sect[C + 5 + 3 * i])
    trip.append(t)
# show first 30 and distribution
print("  first 30:", trip[:30])
import collections
slot_a = collections.Counter(t[0] for t in trip)
slot_b = collections.Counter(t[1] for t in trip)
slot_c = collections.Counter(t[2] for t in trip)
print("  slot a distinct:", len(slot_a), "range", min(slot_a), max(slot_a))
print("  slot b distinct:", len(slot_b), "range", min(slot_b), max(slot_b))
print("  slot c distinct:", len(slot_c), "range", min(slot_c), max(slot_c))

# bounds decode (hypothesis H)
x0, x1, z0, z1 = f32(off), f32(off + 4), f32(off + 8), f32(off + 12)
amax = max(slot_a) or 1
cmax = max(slot_c) or 1
print("\nbounds: x0=%.3f x1=%.3f z0=%.3f z1=%.3f amax=%d cmax=%d" % (x0, x1, z0, z1, amax, cmax))
print("decoded (x,y,z):")
for t in trip[:20]:
    a, b, c = t
    x = x0 + a * (x1 - x0) / amax
    z = z0 + c * (z1 - z0) / cmax
    print("   (%2d,%2d,%2d) -> (%.3f, %d, %.3f)" % (a, b, c, x, b, z))
