#!/usr/bin/env python3
"""Extract collision-block byte signatures from a Detail TRB (for RAM scanning)."""
import struct, sys

TRB = sys.argv[1] if len(sys.argv) > 1 else \
    "/run/media/samp/787be337-88e4-4b95-92f9-45d37615cd02/games/console (other)/gcn+wii/extract/nicku-ntsc/P-GNOE/files/Data/dannyphantomlevel1/DPWorld_Level04_01_Detail.trb"

d = open(TRB, "rb").read()
assert d[:4] == b"TSFB", d[:4]
hdrx = struct.unpack_from(">I", d, 0x10)[0]
n = struct.unpack_from(">I", d, 0x18)[0]
sizes = [struct.unpack_from(">I", d, 0x20 + 16 * i)[0] for i in range(n)]
sect = hdrx + 20 + 8
print(f"TSFB size_field=0x{struct.unpack_from('>I', d, 4)[0]:X} sections={n}")
print(f"sizes: {[hex(s) for s in sizes]}")

# find mesh records: section 0, 0x34-byte records with c14/c18 at +0x14/+0x18
sec0 = d[sect:sect + sizes[0]]
blocks = []
for off in range(0, len(sec0) - 0x34, 4):
    c10 = struct.unpack_from(">I", sec0, off + 0x10)[0]
    c14 = struct.unpack_from(">I", sec0, off + 0x14)[0]
    c18 = struct.unpack_from(">I", sec0, off + 0x18)[0]
    if not (0 < c14 < c18 and c18 - c14 <= 1 << 20):
        continue
    if not (1 <= c10 < n):
        continue
    cbase = sect + sum(sizes[:c10]) + c14
    clen = c18 - c14
    seg = d[cbase:cbase + clen]
    seg = seg[:len(seg) - len(seg) % 4]
    if len(seg) < 16:
        continue
    flags = set(seg[0::4])
    ys = set(seg[2::4])
    xs = set(seg[1::4])
    zs = set(seg[3::4])
    if not all(f in (0, 1, 2, 255) for f in flags):
        continue
    if len(xs) < 5 or len(zs) < 5:
        continue
    if max(xs) - min(xs) <= 30 or max(zs) - min(zs) <= 30:
        continue
    blocks.append((off, c10, c14, c18, cbase, clen, len(seg)))

print(f"mesh-records with plausible collision blocks: {len(blocks)}")
# dedupe identical segs
seen = {}
for off, c10, c14, c18, cbase, clen, seglen in blocks:
    seg = d[cbase:cbase + seglen]
    h = hash(seg)
    seen.setdefault(h, (off, c10, c14, c18, cbase, seglen, seg))
print(f"unique blocks: {len(seen)}")

# save signatures: longest unique blocks
items = sorted(seen.values(), key=lambda t: -t[5])
with open("/tmp/coll_sigs.txt", "w") as f:
    for off, c10, c14, c18, cbase, seglen, seg in items[:200]:
        f.write(f"rec@0x{off:X} chunk={c10} c14=0x{c14:X} c18=0x{c18:X} "
                f"filebase=0x{cbase:X} len={seglen} first8={seg[:8].hex()}\n")
for t in items[:10]:
    off, c10, c14, c18, cbase, seglen, seg = t
    print(f"  rec@0x{off:X} chunk={c10} c14=0x{c14:X} c18=0x{c18:X} "
          f"filebase=0x{cbase:X} len={seglen} first8={seg[:8].hex()}")
