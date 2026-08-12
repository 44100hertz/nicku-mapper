#!/usr/bin/env python3
"""render_pool.py — decode all C-block triples as points (hypothesis H), render SVG with entities."""
import struct
import re

PATH = "nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb"
ENTS = "nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBL1_Ents.ini"
d = open(PATH, "rb").read()
SECT = 0x594
sect = d[SECT:SECT + 0x34680]

def u32(o): return struct.unpack_from(">I", sect, o)[0]
def f32(o): return struct.unpack_from(">f", sect, o)[0]

# entities
ents = []
for m in re.finditer(r"Position\s*=\s*\{\s*(-?[\d.]+)f?\s*,\s*(-?[\d.]+)f?\s*,\s*(-?[\d.]+)f?", open(ENTS).read()):
    ents.append((float(m.group(1)), float(m.group(2)), float(m.group(3))))
print("entities:", len(ents))

# decode meshes
pts = []  # (x, y, z, k)
mesh_centers = []
for k in range(86):
    off = 0x3B08 + 0x34 * k
    fs = [f32(off + 4 * i) for i in range(4)]
    C, D, F = u32(off + 0x20), u32(off + 0x24), u32(off + 0x2C)
    body = sect[C + 3:C + 3 + F * 3]
    if len(body) < F * 3:
        continue
    xmin, xmax = min(fs[0], fs[1]), max(fs[0], fs[1])
    zmin, zmax = min(fs[2], fs[3]), max(fs[2], fs[3])
    tris = [(body[i], body[i + 1], body[i + 2]) for i in range(0, F * 3, 3)]
    if not tris:
        continue
    amax = max(t[0] for t in tris)
    cmax = max(t[2] for t in tris)
    for (a, b, c) in tris:
        x = xmin + a * (xmax - xmin) / amax if amax else xmin
        z = zmin + c * (zmax - zmin) / cmax if cmax else zmin
        pts.append((x, b, z, k))
    mesh_centers.append((k, xmin, xmax, zmin, zmax))

print("points:", len(pts))

# entity min/max
ex = [e[0] for e in ents]
ey = [e[1] for e in ents]
ez = [e[2] for e in ents]
print("entity extents x %.2f..%.2f y %.2f..%.2f z %.2f..%.2f" % (min(ex), max(ex), min(ey), max(ey), min(ez), max(ez)))

px = [p[0] for p in pts]
pz = [p[2] for p in pts]
py = [p[1] for p in pts]
print("mesh-point extents x %.2f..%.2f y %d..%d z %.2f..%.2f" % (min(px), max(px), min(py), max(py), min(pz), max(pz)))

# SVG render: top-down (x,z) and side (x,y)
W, H = 1200, 900
MARG = 40

def svg(view, fname):
    if view == "top":
        xs, ys = px, pz
        exs, eys = ex, ez
        xl, xh, yl, yh = min(xs), max(xs), min(ys), max(ys)
        label = "TOP (x,z)"
    else:
        xs, ys = px, py
        exs, eys = ex, ey
        xl, xh, yl, yh = min(xs), max(xs), min(ys), max(ys)
        label = "SIDE (x,y)"
    # include entities in extents
    xl = min(xl, min(exs)); xh = max(xh, max(exs))
    yl = min(yl, min(eys)); yh = max(yh, max(eys))
    sx = (W - 2 * MARG) / (xh - xl) if xh > xl else 1
    sy = (H - 2 * MARG) / (yh - yl) if yh > yl else 1
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d">' % (W, H)]
    out.append('<rect width="%d" height="%d" fill="#101418"/>' % (W, H))
    out.append('<text x="%d" y="%d" fill="#ddd" font-size="16">%s — mesh points (%d) + entities (%d) [k per 10]</text>' % (MARG, 24, label, len(pts), len(ents)))
    # mesh points colored by mesh index
    for (x, y, z, k) in pts:
        if view == "top":
            X, Y = x, z
        else:
            X, Y = x, y
        r = 1.6
        col = "#66ccff"
        out.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" opacity="0.7"/>' %
                   (MARG + (X - xl) * sx, MARG + (H - 2 * MARG) - (Y - yl) * sy, r, col))
    # entities
    for i, (x, y, z) in enumerate(ents):
        if view == "top":
            X, Y = x, z
        else:
            X, Y = x, y
        out.append('<circle cx="%.1f" cy="%.1f" r="5" fill="none" stroke="#ffcc00" stroke-width="2"/>' %
                   (MARG + (X - xl) * sx, MARG + (H - 2 * MARG) - (Y - yl) * sy))
    out.append('</svg>')
    open(fname, "w").write("\n".join(out))
    print("wrote", fname)

svg("top", "/tmp/level_top.svg")
svg("side", "/tmp/level_side.svg")
