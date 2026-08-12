#!/usr/bin/env python3
"""Render mesh geometry hypotheses from NTU GC level TRB to OBJ.

Hypothesis under test: the u16 triplet streams in chunks 1..86 are
(posIdx, uvIdx, nrmIdx); posIdx indexes (signed: negative = from pool end)
into the concatenated C-block pool of u8 triples, each triple decoded with
its own mesh's record bounds (x = xmin + a*(xmax-xmin)/amax, z likewise,
y = b * yscale).
"""
import struct
import sys

P = "/PATH/TO/extract/nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb"
YSCALE = 0.125


def load(path=P):
    d = open(path, "rb").read()
    hdrx_size = struct.unpack_from(">I", d, 16)[0]
    sect_start = hdrx_size + 20
    sect_size = struct.unpack_from(">I", d, sect_start + 4)[0]
    sect = d[sect_start + 8 : sect_start + 8 + sect_size]
    sizes = [struct.unpack_from(">I", d, 32 + i * 16)[0] for i in range(87)]
    return sect, sizes


def u32(sect, o):
    return struct.unpack_from(">I", sect, o)[0]


def f32(sect, o):
    return struct.unpack_from(">f", sect, o)[0]


def build_pool(sect):
    pool = []  # (mesh_k, a, b, c)
    for k in range(86):
        rec = 0x3B08 + 0x34 * k
        C = u32(sect, rec + 0x20)
        F = u32(sect, rec + 0x2C)
        body = sect[C + 3 : C + 3 + F * 3]
        for i in range(0, F * 3, 3):
            pool.append((k, body[i], body[i + 1], body[i + 2]))
    return pool


def decode(sect, k, a, b, c):
    rec = 0x3B08 + 0x34 * k
    fs = [f32(sect, rec + 4 * i) for i in range(4)]
    xmin, xmax = min(fs[0], fs[1]), max(fs[0], fs[1])
    zmin, zmax = min(fs[2], fs[3]), max(fs[2], fs[3])
    x = xmin + a * (xmax - xmin) / 255.0
    z = zmin + c * (zmax - zmin) / 255.0
    y = b * YSCALE
    return x, y, z


def main():
    sect, sizes = load()
    pool = build_pool(sect)
    print("pool entries:", len(pool))
    verts = []
    mesh_info = []
    for k in range(86):
        rec = 0x3B08 + 0x34 * k
        A = u32(sect, rec + 0x14)
        chunk = sect[sum(sizes[: k + 1]) : sum(sizes[: k + 1]) + sizes[k + 1]]
        nrec = min(A, len(chunk)) // 6
        base = len(verts)
        cnt = 0
        for i in range(nrec):
            p, u, n = struct.unpack_from(">HHH", chunk, i * 6)
            if p == 0 and u == 0 and n == 0:
                continue
            idx = p
            if p >= 0x8000:
                idx = len(pool) + (p - 0x10000)  # signed: from end
            if idx < 0 or idx >= len(pool):
                continue
            mk, a, b, c = pool[idx]
            x, y, z = decode(sect, mk, a, b, c)
            verts.append((x, y, z, k))
            cnt += 1
        mesh_info.append((k, base, cnt))
    # write OBJ with per-mesh colors via vn groups (use v with color in comment)
    with open("/tmp/mesh_points.obj", "w") as f:
        for x, y, z, k in verts:
            f.write("v %.4f %.4f %.4f\n" % (x, y, z))
        for k, base, cnt in mesh_info:
            if cnt:
                f.write("g mesh%d\n" % k)
                f.write("p")
                for j in range(base, base + cnt):
                    f.write(" %d" % (j + 1))
                f.write("\n")
    print("verts:", len(verts))
    # stats
    from collections import Counter
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    print("x range: %.2f..%.2f" % (min(xs), max(xs)))
    print("y range: %.2f..%.2f" % (min(ys), max(ys)))
    print("z range: %.2f..%.2f" % (min(zs), max(zs)))
    print("y histogram (buckets of 1):", Counter(int(y) for y in ys).most_common(10))
    nz = sum(1 for v in verts if abs(v[1]) > 0.01)
    print("non-flat y points:", nz, "of", len(verts))


if __name__ == "__main__":
    main()
