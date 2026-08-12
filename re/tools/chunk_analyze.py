#!/usr/bin/env python3
"""chunk_analyze.py — dissect chunk structure: u16 triples, UV pairs, tails."""
import struct

D = "/home/cyan/code/nickmapper-lua/asset-extract/nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb"
d = open(D, "rb").read()
sect = d[0x594:0x594 + 0x34680]

sizes = []
o = 0x20
for i in range(87):
    sizes.append(struct.unpack_from(">I", d, o)[0])
    o += 16
starts = []
acc = 0
for s in sizes:
    starts.append(acc)
    acc += s


def dump(off, n, label):
    print("--- %s @0x%x ---" % (label, off))
    b = sect[off:off + n]
    for i in range(0, len(b), 16):
        row = b[i:i + 16]
        print("  %06x: %s" % (off + i, " ".join("%02x" % x for x in row)))


# chunk1 = mesh0's chunk: find the u16-triple region length by scanning
c1 = sect[starts[1]:starts[1] + sizes[1]]
print("chunk1 size:", hex(sizes[1]))
i = 0
triples = []
while i + 6 <= len(c1):
    a, b, c = struct.unpack_from(">HHH", c1, i)
    if a < 4096 and b < 4096 and (c < 4096 or c == 0xFFDB):
        triples.append((a, b, c))
        i += 6
    else:
        break
print("u16 triples: %d, consumed %d bytes, next bytes: %s" % (
    len(triples), i, " ".join("%02x" % x for x in c1[i:i + 16])))
# stats
pa = [t[0] for t in triples]
pb = [t[1] for t in triples]
pc = [t[2] for t in triples]
print("pos min/max:", min(pa), max(pa), " uv min/max:", min(pb), max(pb), " nrm:", sorted(set(pc))[:20])

# after triples
rest = c1[i:]
print("rest length:", len(rest))
# find the UV-pair region (u16, u16) pairs
j = 0
uvs = []
while j + 4 <= len(rest):
    u, v = struct.unpack_from(">hh", rest, j)
    uvs.append((u, v))
    j += 4
print("first 8 of rest as s16 pairs:", uvs[:8])

# now correlate C-block of mesh0
C = 0x4C80
D = 0x3C0
F = 0x139
body = sect[C + 3:C + 3 + F * 3]
a = body[0::3]
b = body[1::3]
c = body[2::3]
print()
print("C-block mesh0: F=%d, slotA distinct=%d max=%d" % (F, len(set(a)), max(a)))
print("              slotB distinct=%d max=%d" % (len(set(b)), max(b)))
print("              slotC distinct=%d max=%d" % (len(set(c)), max(c)))

# chunk triples for mesh0: 62 records... does F relate?
print()
print("mesh0: F(cblock)=%d, chunk triples=%d" % (F, len(triples)))
