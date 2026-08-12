#!/usr/bin/env python3
"""Render the u16 triplet streams as triangle strips under different hypotheses.

Hypothesis A: field1 -> concatenated C-block pool (per-owning-mesh bounds, /amax)
Hypothesis B: field1 -> concatenated C-block pool (per-owning-mesh bounds, /255)
Hypothesis C: field1 -> direct u16 x-coordinate quantized to mesh bounds
Writes OBJ + a PPM render (top-down view) for each.
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


# build C-block pool
pool = []  # (mesh_k, a, b, c)
for k in range(86):
    rec = 0x3B08 + 0x34 * k
    C = u32(rec + 0x20)
    F = u32(rec + 0x2C)
    body = sect[C + 3 : C + 3 + F * 3]
    for i in range(0, F * 3, 3):
        pool.append((k, body[i], body[i + 1], body[i + 2]))

amax = {}
cmax = {}
for k in range(86):
    rec = 0x3B08 + 0x34 * k
    C = u32(rec + 0x20)
    F = u32(rec + 0x2C)
    body = sect[C + 3 : C + 3 + F * 3]
    amax[k] = max(body[0::3]) if F else 0
    cmax[k] = max(body[2::3]) if F else 0


def pool_pos(idx, norm):
    if idx < 0 or idx >= len(pool):
        return None
    mk, a, b, c = pool[idx]
    rec = 0x3B08 + 0x34 * mk
    fs = [f32(rec + 4 * i) for i in range(4)]
    xmin, xmax = min(fs[0], fs[1]), max(fs[0], fs[1])
    zmin, zmax = min(fs[2], fs[3]), max(fs[2], fs[3])
    if norm == "amax":
        x = xmin + a * (xmax - xmin) / max(1, amax[mk])
        z = zmin + c * (zmax - zmin) / max(1, cmax[mk])
    else:
        x = xmin + a * (xmax - xmin) / 255.0
        z = zmin + c * (zmax - zmin) / 255.0
    return (x, b * 0.125, z)


def direct_pos(k, p):
    rec = 0x3B08 + 0x34 * k
    fs = [f32(rec + 4 * i) for i in range(4)]
    xmin, xmax = min(fs[0], fs[1]), max(fs[0], fs[1])
    zmin, zmax = min(fs[2], fs[3]), max(fs[2], fs[3])
    # treat p as u16 x-coordinate quantized across the LARGER of the two axes
    span = max(xmax - xmin, zmax - zmin)
    x = xmin + (p / 65535.0) * span
    return (x, 0.0, zmin)


def render(hyp, outname):
    verts = []
    tris = []
    for k in range(86):
        rec = 0x3B08 + 0x34 * k
        A = u32(rec + 0x14)
        chunk = sect[sum(sizes[: k + 1]) : sum(sizes[: k + 1]) + sizes[k + 1]]
        nrec = min(A, len(chunk)) // 6
        strip = []
        for i in range(nrec):
            p, u, n = struct.unpack_from(">HHH", chunk, i * 6)
            if p == 0 and u == 0 and n == 0:
                continue
            # restart on negative posIdx or -37 nrm
            if p >= 0x8000 or (n >= 0x8000 and n != 0xFFDB):
                strip = []
                continue
            idx = p
            pos = None
            if hyp == "A":
                pos = pool_pos(idx, "amax")
            elif hyp == "B":
                pos = pool_pos(idx, "255")
            elif hyp == "C":
                pos = direct_pos(k, p)
            elif hyp == "D":  # pool but no restart on -37 nrm; skip -37 dupes
                pos = pool_pos(idx, "amax")
            if pos is None:
                strip = []
                continue
            # skip exact duplicate consecutive verts (degenerates)
            if strip and strip[-1] == pos:
                continue
            if hyp == "D" and n == 0xFFDB:
                continue
            strip.append(pos)
        # make triangles from strip
        base = len(verts)
        for v in strip:
            verts.append(v)
        for i in range(len(strip) - 2):
            a, b, c = base + i, base + i + 1, base + i + 2
            tris.append((a, b, c))
    with open(outname + ".obj", "w") as f:
        for v in verts:
            f.write("v %.4f %.4f %.4f\n" % v)
        for t in tris:
            f.write("f %d %d %d\n" % (t[0] + 1, t[1] + 1, t[2] + 1))
    print("%s: %d verts %d tris" % (hyp, len(verts), len(tris)))
    return verts, tris


def render_ppm(verts, tris, outname, size=600):
    xs = [v[0] for v in verts]
    zs = [v[2] for v in verts]
    if not xs:
        return
    x0, x1 = min(xs), max(xs)
    z0, z1 = min(zs), max(zs)
    span = max(x1 - x0, z1 - z0, 1e-6)
    img = [[(20, 20, 30)] * size for _ in range(size)]

    def sx(x):
        return int((x - x0) / span * (size - 2)) + 1

    def sz(z):
        return int((z - z0) / span * (size - 2)) + 1

    import random

    rnd = random.Random(42)
    for t in tris:
        col = (rnd.randint(60, 255), rnd.randint(60, 255), rnd.randint(60, 255))
        pts = [(sx(verts[i][0]), sz(verts[i][2])) for i in t]
        # fill triangle (simple bbox scanline)
        for (x1p, y1p), (x2p, y2p), (x3p, y3p) in [pts]:
            xminp, xmaxp = min(x1p, x2p, x3p), max(x1p, x2p, x3p)
            yminp, ymaxp = min(y1p, y2p, y3p), max(y1p, y2p, y3p)
            for yy in range(max(0, yminp), min(size, ymaxp + 1)):
                for xx in range(max(0, xminp), min(size, xmaxp + 1)):
                    img[yy][xx] = col
    with open(outname + ".ppm", "w") as f:
        f.write("P3\n%d %d\n255\n" % (size, size))
        for row in img:
            for r, g, b in row:
                f.write("%d %d %d " % (r, g, b))
            f.write("\n")
    print("wrote", outname + ".ppm")


for hyp in ["A", "B", "C", "D"]:
    verts, tris = render(hyp, "/tmp/mesh_" + hyp)
    render_ppm(verts, tris, "/tmp/mesh_" + hyp)
