#!/usr/bin/env python3
"""Exhaustively search for the position pool that u16 field1 indices reference.

For a candidate pool (base offset, entry stride), map each mesh's u16 field1
indices to pool entries and decode positions; score by fraction of points
inside the mesh's record bounds.
"""
import struct
import sys

P = "/PATH/TO/extract/nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb"
d = open(P, "rb").read()
hdrx_size = struct.unpack_from(">I", d, 16)[0]
sect_start = hdrx_size + 20
sect_size = struct.unpack_from(">I", d, sect_start + 4)[0]
sect = d[sect_start + 8 : sect_start + 8 + sect_size]
sizes = [struct.unpack_from(">I", d, 32 + i * 16)[0] for i in range(87)]


def u32(o):
    return struct.unpack_from(">I", sect, o)[0]


def f32(o):
    return struct.unpack_from(">f", sect, o)[0]


# mesh streams: field1 indices
streams = {}
for k in range(86):
    rec = 0x3B08 + 0x34 * k
    A = u32(rec + 0x14)
    chunk = sect[sum(sizes[: k + 1]) : sum(sizes[: k + 1]) + sizes[k + 1]]
    idxs = []
    for i in range(0, min(A, len(chunk)) - 5, 6):
        p, u, n = struct.unpack_from(">HHH", chunk, i)
        if p == 0 and u == 0 and n == 0:
            continue
        if p >= 0x8000:
            continue  # skip signed markers for now
        idxs.append(p)
    streams[k] = idxs

mesh_bounds = {}
for k in range(86):
    rec = 0x3B08 + 0x34 * k
    fs = [f32(rec + 4 * i) for i in range(4)]
    mesh_bounds[k] = (
        min(fs[0], fs[1]),
        max(fs[0], fs[1]),
        min(fs[2], fs[3]),
        max(fs[2], fs[3]),
    )


def decode_u8(entry, bounds, norm):
    a, b, c = entry
    xmin, xmax, zmin, zmax = bounds
    if norm == "255":
        x = xmin + a * (xmax - xmin) / 255.0
        z = zmin + c * (zmax - zmin) / 255.0
    else:
        x = xmin + a * (xmax - xmin) / 255.0
        z = zmin + c * (zmax - zmin) / 255.0
    y = b * 0.125
    return x, y, z


def score_pool(base, stride, mode, norm):
    """mode: 'u8' = entries are triples of bytes; 'u16' = triples of u16s"""
    total_hits = 0
    total_pts = 0
    for k in range(86):
        idxs = streams[k]
        if not idxs:
            continue
        bounds = mesh_bounds[k]
        inb = 0
        for idx in idxs:
            off = base + idx * stride
            if off + stride > len(sect):
                continue
            if mode == "u8":
                a, b, c = sect[off], sect[off + 1], sect[off + 2]
            else:
                a, b, c = struct.unpack_from(">HHH", sect, off)
            xmin, xmax, zmin, zmax = bounds
            if mode == "u8":
                x = xmin + a * (xmax - xmin) / 255.0
                z = zmin + c * (zmax - zmin) / 255.0
                y = b * 0.125
            else:
                x = xmin + (a / 1024.0) * (xmax - xmin)
                z = zmin + (c / 1024.0) * (zmax - zmin)
                y = b / 512.0
            if xmin - 0.3 <= x <= xmax + 0.3 and zmin - 0.3 <= z <= zmax + 0.3:
                inb += 1
            total_pts += 1
        total_hits += inb
    return total_hits, total_pts


print("searching for best pool base (u8 triples, per-mesh bounds /255)...")
best = []
for base in range(0, len(sect) - 1000, 1):
    hits, pts = score_pool(base, 3, "u8", "255")
    best.append((hits, pts, base))
best.sort(reverse=True)
for hits, pts, base in best[:10]:
    print("  base=0x%05x hits=%d/%d (%.2f)" % (base, hits, pts, hits / max(1, pts)))

print("\nu16 triples (u16 values as fixed point):")
best = []
for base in range(0, len(sect) - 1000, 2):
    hits, pts = score_pool(base, 6, "u16", None)
    best.append((hits, pts, base))
best.sort(reverse=True)
for hits, pts, base in best[:10]:
    print("  base=0x%05x hits=%d/%d (%.2f)" % (base, hits, pts, hits / max(1, pts)))
