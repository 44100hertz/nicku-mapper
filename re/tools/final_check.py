#!/usr/bin/env python3
"""final_check.py — verify H_A quantization vs entities; export OBJ of best meshes."""
import struct
import math

D = "/home/cyan/code/nickmapper-lua/asset-extract/nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb"
d = open(D, "rb").read()
sect = d[0x594:0x594 + 0x34680]

OUT = "/home/cyan/code/nickmapper-lua/asset-extract/analysis/"

# entities: parse SBL1_Ents.ini positions (only the play-space ones near origin)
ents = []
import re
for line in open("/home/cyan/code/nickmapper-lua/asset-extract/nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBL1_Ents.ini"):
    m = re.search(r"Position = \{ ([-\d.]+)f, ([-\d.]+)f, ([-\d.]+)f", line)
    if m:
        x, y, z = float(m.group(1)), float(m.group(2)), float(m.group(3))
        if -20 < x < 50 and -30 < y < 30 and -10 < z < 45:
            ents.append((x, y, z))
print("play-space entities:", len(ents))


def cblock(k):
    off = 0x3B08 + 0x34 * k
    u = struct.unpack_from(">13I", sect, off)
    fl = struct.unpack_from(">4f", sect, off)
    C, D, F = u[8], u[9], u[11]
    body = sect[C + 3:C + 3 + F * 3]
    tris = [(body[i], body[i + 1], body[i + 2]) for i in range(0, F * 3, 3)]
    return fl, u, tris


def decode_H(fl, tris):
    """H: (a,b,c)=(x,y,z); floats=(x0,x1,z0,z1) via min/max; y = b (raw)."""
    x0, x1 = min(fl[0], fl[1]), max(fl[0], fl[1])
    z0, z1 = min(fl[2], fl[3]), max(fl[2], fl[3])
    Amax = max(t[0] for t in tris)
    Cmax = max(t[2] for t in tris)
    pts = []
    for (a, b, c) in tris:
        x = x0 + a * (x1 - x0) / (Amax or 1)
        z = z0 + c * (z1 - z0) / (Cmax or 1)
        pts.append((x, b, z))  # y = raw u8 slotB
    return pts


# 1) floor coverage check: for each entity at y~0, find meshes whose (x,z) span covers it
print("floor mesh coverage for player-ish entities:")
for ex, ey, ez in ents[:6]:
    covers = []
    for k in range(86):
        fl, u, tris = cblock(k)
        x0, x1 = min(fl[0], fl[1]), max(fl[0], fl[1])
        z0, z1 = min(fl[2], fl[3]), max(fl[2], fl[3])
        if x0 - 0.5 <= ex <= x1 + 0.5 and z0 - 0.5 <= ez <= z1 + 0.5:
            covers.append(k)
    print("  ent(%.2f, %.2f, %.2f) covered by meshes %s" % (ex, ey, ez, covers))

# 2) export OBJ for meshes 1 (road), 0, 2, 35, 55 under H
with open(OUT + "cblock_hypothesis.obj", "w") as f:
    f.write("# NTU GC SBWorld_Detail_Level01_01 C-block u8-triple decode (HYPOTHESIS)\n")
    f.write("# (x,y,z) = (x0 + a*(x1-x0)/Amax, b_raw, z0 + c*(z1-z0)/Cmax)\n")
    voff = 1
    for k in (1, 0, 2, 35, 55, 63, 24):
        fl, u, tris = cblock(k)
        pts = decode_H(fl, tris)
        f.write("o mesh_%d_F%d\n" % (k, u[11]))
        for (x, y, z) in pts:
            f.write("v %.3f %.3f %.3f\n" % (x, y, z))
        for i in range(0, len(pts) - 2):
            f.write("f %d %d %d\n" % (voff + i, voff + i + 1, voff + i + 2))
        voff += len(pts)
print("OBJ written:", OUT + "cblock_hypothesis.obj")
