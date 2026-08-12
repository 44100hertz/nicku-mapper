"""Display-mesh extractor for Nicktoons Unite! (GC) level files.

Decodes the `*_Detail_Level*.trb` TSFB containers into the mesh-v2 JSON the
viewer renders. See docs/trb-format-notes.md and the header comment history
in re/tools/trb_mesh.py for the full format write-up.

Each mesh's vertex array is a run of 6-byte records:

    u16 x (s16, world x = value / 64)   [1/64 fixed point, 6.10]
    u16 z (s16, world z = value / 64)
    u16 y (s16, height  = -value / 64)  [file y is +y DOWN, game-native]

The 52-byte mesh records at the W0C0M symbol offsets begin with 4 floats
(x_center, z_center, y_center, radius) used to delimit the run. The record's
u32[+0x20]/u32[+0x24] point at a 0x98-prefixed index block — the mesh's
GX-style indexed triangle strip — whose posIdx stream yields the real faces.
"""
import argparse
import glob
import json
import math
import os
import struct
import sys

DIV = 64.0          # fixed-point scale (2^6)
SLACK = 1.25        # bounding-sphere slack for vertex-run delimiting


def parse_tsfb(path):
    d = open(path, "rb").read()
    assert d[0:4] == b"TSFB" or d[0:4] == b"BFST", d[0:4]
    hdrx_size = struct.unpack_from(">I", d, 0x10)[0]
    n = struct.unpack_from(">I", d, 0x18)[0]
    sizes = [struct.unpack_from(">I", d, 0x20 + 16 * i)[0] for i in range(n)]
    sect = hdrx_size + 20 + 8
    return d, sect, sizes


def symb_lookup(d, sect, sizes, name):
    """Return the DataOffset for a named SYMB, or None."""
    p = sect + sum(sizes)
    while p + 8 <= len(d):
        if d[p:p + 4] == b"BMYS":
            sz = struct.unpack_from(">I", d, p + 4)[0]
            s = d[p + 8:p + 8 + sz]
            cnt = struct.unpack_from(">I", s, 0)[0]
            names = s[4 + cnt * 12:]
            for i in range(cnt):
                e = s[4 + i * 12:4 + i * 12 + 12]
                no = struct.unpack_from(">H", e, 2)[0]
                if no >= len(names):
                    continue
                nm = names[no:].split(b"\x00")[0].decode("latin1")
                if nm == name:
                    return struct.unpack_from(">I", e, 8)[0]
            break
        p += 4
    return None


def mesh_records_symb(path, d, sect, sizes):
    """Per-mesh record offsets from the SYMB table: W0C0Mk -> DataOffset."""
    p = sect + sum(sizes)
    meshes = {}
    while p + 8 <= len(d):
        if d[p:p + 4] == b"BMYS":
            sz = struct.unpack_from(">I", d, p + 4)[0]
            s = d[p + 8:p + 8 + sz]
            cnt = struct.unpack_from(">I", s, 0)[0]
            names = s[4 + cnt * 12:]
            for i in range(cnt):
                e = s[4 + i * 12:4 + i * 12 + 12]
                no = struct.unpack_from(">H", e, 2)[0]
                if no >= len(names):
                    continue
                nm = names[no:].split(b"\x00")[0].decode("latin1")
                if nm.startswith("W0C0M"):
                    try:
                        meshes[int(nm[5:])] = struct.unpack_from(">I", e, 8)[0]
                    except ValueError:
                        pass
            break
        p += 4
    recs = {}
    if meshes:
        for k, moff in meshes.items():
            rec = d[sect + moff:sect + moff + 0x34]
            cx, cz, cy, rad = struct.unpack(">4f", rec[0:16])
            recs[k] = {"center": (cx, cz, cy), "radius": rad, "offset": moff}
    else:
        # fallback: classic table
        n_meshes = min(len(sizes) - 1, 86)
        for k in range(n_meshes):
            rec = d[sect + 0x3B08 + 0x34 * k:sect + 0x3B08 + 0x34 * (k + 1)]
            cx, cz, cy, rad = struct.unpack(">4f", rec[0:16])
            recs[k] = {"center": (cx, cz, cy), "radius": rad,
                       "offset": 0x3B08 + 0x34 * k}
    # Each mesh's vertex pool lives in the section its +0x10 pointer relocates
    # to — NOT always k+1. The RELC (CLER) list maps each relocated field's
    # offset (within section 0) to its target section.
    p = sect + sum(sizes)
    relc = {}
    while p + 8 <= len(d):
        if d[p:p + 4] == b"CLER":
            sz = struct.unpack_from(">I", d, p + 4)[0]
            for i in range(sz // 8):
                relc[struct.unpack_from(">I", d, p + 8 + 8 * i)[0]] = \
                    struct.unpack_from(">I", d, p + 8 + 8 * i + 4)[0]
            break
        p += 4
    for k, rec in recs.items():
        t = relc.get(rec["offset"] + 0x10)
        rec["chunk"] = t if (t is not None and 1 <= t < len(sizes)) else k + 1
    return recs


def chunk_of(d, sect, sizes, i):
    off = sum(sizes[:i])
    return d[sect + off:sect + off + sizes[i]]


def vertex_run(chunk, center, radius):
    """Longest prefix of the chunk whose 6-byte records are vertices of the
    mesh (inside the bounding sphere). Falls back to a plausibility prefix."""
    cx, cz, cy = (c * DIV for c in center)
    r = radius * DIV * SLACK
    recs = []
    n = len(chunk) // 6
    for j in range(n):
        x, z, y = struct.unpack_from(">HHH", chunk, j * 6)
        x = x if x < 0x8000 else x - 0x10000
        z = z if z < 0x8000 else z - 0x10000
        y = y if y < 0x8000 else y - 0x10000
        dist = ((x - cx) ** 2 + (z - cz) ** 2 + (y - cy) ** 2) ** 0.5
        if dist <= r:
            recs.append((x, z, y))
        else:
            break
    if len(recs) >= 3:
        return recs
    recs = []
    for j in range(n):
        x, z, y = struct.unpack_from(">HHH", chunk, j * 6)
        x = x if x < 0x8000 else x - 0x10000
        z = z if z < 0x8000 else z - 0x10000
        y = y if y < 0x8000 else y - 0x10000
        if x == z == y == 0:
            break
        if max(abs(x), abs(z), abs(y)) > 10000:
            break
        recs.append((x, z, y))
    return recs


def strip_faces(verts):
    """Faces as one un-split triangle strip (GX_TRIANGLESTRIP)."""
    for i in range(len(verts) - 2):
        yield (i, i + 1, i + 2) if i % 2 == 0 else (i + 1, i, i + 2)


def _s16(v):
    return v if v < 0x8000 else v - 0x10000


def _dist(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


def indexed_faces(d, sect, sizes, recs, k):
    """Decode mesh k's 0x98 index block into an indexed triangle strip.

    Returns (posIdx list, pool, texIdx list) or None when the block is junk /
    uses a non-standard format. The record's first field is the position index
    (pos-first, verified); its width derives from the pool size. A decode is
    accepted only when it passes the manifoldness gate.
    """
    if k + 1 >= len(sizes):
        return None
    rec = recs[k]
    boff = struct.unpack_from(">I", d, sect + rec["offset"] + 0x20)[0]
    bsz = struct.unpack_from(">I", d, sect + rec["offset"] + 0x24)[0]
    seg = d[sect + boff:sect + boff + bsz]
    if len(seg) < 5 or seg[0] != 0x98:
        return None
    cnt = struct.unpack_from(">H", seg, 1)[0]
    if not (2 <= cnt <= 100000):
        return None
    chunk = chunk_of(d, sect, sizes, rec.get("chunk", k + 1))
    radius_raw = rec["radius"] * DIV * 2.2
    best = None
    cands = []
    for recw in range(3, 13):
        cands.append((recw, True))
        cands.append((recw, False))
    for recw, is_u8 in cands:
        if 3 + cnt * recw > len(seg):
            continue
        if is_u8:
            pos = [seg[3 + i * recw] for i in range(cnt)]
        else:
            pos = [struct.unpack_from(">H", seg, 3 + i * recw)[0] for i in range(cnt)]
        mx = max(pos)
        if (mx + 1) * 6 > len(chunk):
            continue
        pool = []
        for j in range(mx + 1):
            x, z, y = struct.unpack_from(">HHH", chunk, j * 6)
            pool.append((_s16(x), _s16(z), _s16(y)))
        cx, cz, cy = rec["center"]
        rr = rec["radius"] * 1.25
        insphere = sum(1 for p in pool
                       if math.sqrt((p[0] / DIV - cx) ** 2 + (p[1] / DIV - cz) ** 2 + (p[2] / DIV - cy) ** 2) < rr)
        if insphere < 0.5 * len(pool):
            continue
        small = big = deg = 0
        edge_share = {}
        used = set()
        for i in range(cnt - 2):
            a, b, c = pos[i], pos[i + 1], pos[i + 2]
            if a == b or b == c or a == c:
                deg += 1
                continue
            used.update((a, b, c))
            va, vb, vc = pool[a], pool[b], pool[c]
            m = max(_dist(va, vb), _dist(vb, vc), _dist(vc, va))
            if m > radius_raw:
                big += 1
            else:
                small += 1
            for e in ((a, b), (b, c), (a, c)):
                key = (min(e), max(e))
                edge_share[key] = edge_share.get(key, 0) + 1
        over = sum(1 for v in edge_share.values() if v > 2)
        coverage = len(used) / (mx + 1)
        key = (over, big, -coverage, -small, -deg)
        if best is None or key < best[0]:
            best = (key, pos, pool, over, big, small, deg, len(edge_share), recw, is_u8)
            if over == 0 and big == 0 and coverage >= 0.999:
                break
    if best is None:
        return None
    key, pos, pool, over, big, small, deg, nedges, recw, is_u8 = best
    nreal = small + big
    if over > max(2, 0.02 * nedges) or big > max(2, 0.02 * nreal) or \
            (nreal and -key[2] < 0.6):
        return None
    if is_u8 and recw >= 3:
        tex = [seg[3 + i * recw + 2] for i in range(cnt)]
    elif not is_u8 and recw >= 4:
        tex = [seg[3 + i * recw + 2] for i in range(cnt)]
    else:
        tex = None
    return pos, pool, tex


def strip_triangles(pos):
    """Resolve an indexed triangle strip into concrete vertex triples."""
    for i in range(len(pos) - 2):
        a, b, c = pos[i], pos[i + 1], pos[i + 2]
        if a == b or b == c or a == c:
            continue
        yield (a, b, c) if i % 2 == 0 else (b, a, c)


def world(v):
    return (v[0] / DIV, -v[2] / DIV, v[1] / DIV)


def mesh_verts(d, sect, sizes, recs, k):
    if k + 1 >= len(sizes):
        return None
    rec = recs[k]
    if not (0.01 <= rec["radius"] < 200):
        return None
    verts = vertex_run(chunk_of(d, sect, sizes, rec.get("chunk", k + 1)), rec["center"], rec["radius"])
    return verts if len(verts) >= 3 else None


def chunk_index_stream(d, sect, sizes, recs, k):
    """For G=0x06020202 meshes: the u16-triple index stream from the chunk."""
    rec = recs[k]
    flag = struct.unpack_from(">I", d, sect + rec["offset"] + 0x30)[0]
    if flag != 0x06020202:
        return None
    sec = rec.get("chunk", k + 1)
    if not (1 <= sec < len(sizes)):
        return None
    A = struct.unpack_from(">I", d, sect + rec["offset"] + 0x14)[0]
    if A < 6 or A % 6 != 0:
        return None
    soff = sum(sizes[:sec])
    chunk = d[sect + soff:sect + soff + sizes[sec]]
    if A > len(chunk):
        return None
    n = A // 6
    pos, uv, nrm = [], [], []
    for i in range(n):
        off = i * 6
        pos.append(struct.unpack_from(">H", chunk, off)[0])
        uv.append(struct.unpack_from(">H", chunk, off + 2)[0])
        nrm.append(struct.unpack_from(">H", chunk, off + 4)[0])
    return pos, uv, nrm


def mesh_collision(d, sect, sizes, recs, k):
    """The mesh's raw collision-block bytes (format UNKNOWN — see
    docs/collision-status.md). Returns a flat byte list or None."""
    rec = recs[k]
    sec = rec.get("chunk", k + 1)
    if not (1 <= sec < len(sizes)):
        return None
    c14 = struct.unpack_from(">I", d, sect + rec["offset"] + 0x14)[0]
    c18 = struct.unpack_from(">I", d, sect + rec["offset"] + 0x18)[0]
    if c18 <= c14 or c18 - c14 > 1 << 20:
        return None
    soff = sum(sizes[:sec])
    seg = d[sect + soff + c14:sect + soff + c18]
    return list(seg)


def web_collect(path):
    """One level part as a mesh-v2 JSON fragment."""
    d, sect, sizes = parse_tsfb(path)
    recs = mesh_records_symb(path, d, sect, sizes)
    meshes = []
    for k in sorted(recs):
        verts = mesh_verts(d, sect, sizes, recs, k)
        if verts is None:
            continue
        rec = recs[k]
        flag = struct.unpack_from(">I", d, sect + rec["offset"] + 0x30)[0]
        idx = indexed_faces(d, sect, sizes, recs, k)
        if idx is not None:
            faces, pool, texidx = idx
            verts = pool
        m = {
            "k": k,
            "name": "W0C0M%d" % k,
            "flag": "0x%08X" % flag,
            "center": list(rec["center"]),
            "radius": rec["radius"],
            "count": len(verts),
            "verts": [c for v in verts for c in v],
        }
        if idx is not None:
            m["faces"] = list(faces)
            if texidx is not None:
                m["texIdx"] = list(texidx)
        mat_name = ""
        moff = rec["offset"]
        C = struct.unpack_from(">I", d, sect + moff + 0x20)[0]
        D = struct.unpack_from(">I", d, sect + moff + 0x24)[0]
        gap_off = C + D
        chunk0 = d[sect:sect + sizes[0]]
        if gap_off + 0x20 <= len(chunk0):
            gap = chunk0[gap_off:gap_off + 0x20]
            mat_name = gap.split(b"\x00")[0].decode("latin1", errors="replace")
        coll = mesh_collision(d, sect, sizes, recs, k)
        if coll:
            m["coll"] = coll
        chunk_idx = chunk_index_stream(d, sect, sizes, recs, k)
        if chunk_idx is not None:
            pos, uv, nrm = chunk_idx
            m["chunkPosIdx"] = pos
            m["chunkUvIdx"] = uv
            m["chunkNrmIdx"] = nrm
            m["collUV"] = True
        meshes.append(m)
    try:
        bounds = list(struct.unpack_from(">4f", d, sect + 0x1C))
    except struct.error:
        bounds = []
    return {
        "file": os.path.basename(path),
        "meshCount": struct.unpack_from(">I", d, sect + 0x0C)[0],
        "levelBounds": bounds,
        "meshes": meshes,
    }


def find_entity_ini(level_dir):
    for pat in ("*Ents.ini", "*Entities.ini"):
        for m in glob.glob(os.path.join(level_dir, pat)):
            return os.path.basename(m)
    return None


def w0c0m_count(path):
    """Number of W0C0M mesh symbols in the file's SYMB table."""
    try:
        d = open(path, "rb").read()
        if d[0:4] not in (b"TSFB", b"BFST"):
            return 0
        hdrx = struct.unpack_from(">I", d, 0x10)[0]
        n = struct.unpack_from(">I", d, 0x18)[0]
        sect = hdrx + 20 + 8
        sizes = [struct.unpack_from(">I", d, 0x20 + 16 * i)[0] for i in range(n)]
        p = sect + sum(sizes)
        while p + 8 <= len(d):
            if d[p:p + 4] == b"BMYS":
                sz = struct.unpack_from(">I", d, p + 4)[0]
                s = d[p + 8:p + 8 + sz]
                cnt = struct.unpack_from(">I", s, 0)[0]
                names = s[4 + cnt * 12:]
                n_mesh = 0
                for i in range(cnt):
                    no = struct.unpack_from(">H", s, 4 + i * 12 + 2)[0]
                    if no < len(names) and names[no:].split(b"\x00")[0].startswith(b"W0C0M"):
                        n_mesh += 1
                return n_mesh
            p += 4
    except Exception:
        pass
    return 0


def level_mesh_files(data_root):
    """Every level-part .trb under data_root whose SYMB table lists >= 2
    W0C0M meshes. Name-agnostic: only dirs carrying an Entities file are
    scanned, so levelnfo/SkyData/etc. are excluded."""
    files = []
    ents_pat = ("*[Ee]nts.ini", "*[Ee]ntities.ini")
    for level_dir in sorted(glob.glob(os.path.join(data_root, "*"))):
        if not os.path.isdir(level_dir):
            continue
        if not any(glob.glob(os.path.join(level_dir, p)) for p in ents_pat):
            continue
        for f in sorted(glob.glob(os.path.join(level_dir, "*.trb"))):
            if w0c0m_count(f) >= 2:
                files.append(f)
    return files


def extract_meshes(data_root, web_dir):
    """Decode every level part under data_root into mesh-v2 JSON files.

    Writes <web_dir>/<Level>.json for each level plus <web_dir>/manifest.json
    (the sorted list of levels that have mesh data). Returns the level list.
    """
    files = level_mesh_files(data_root)
    os.makedirs(web_dir, exist_ok=True)
    by_level = {}
    for f in files:
        level = os.path.basename(os.path.dirname(f))
        by_level.setdefault(level, {"dir": os.path.dirname(f), "parts": []})
        by_level[level]["parts"].append(web_collect(f))
    for level, info in sorted(by_level.items()):
        parts = sorted(info["parts"], key=lambda p: p["file"])
        nv = sum(m["count"] for p in parts for m in p["meshes"])
        out = {
            "format": "mesh-v2",
            "level": level,
            "entityFile": find_entity_ini(info["dir"]),
            "div": DIV,
            "yDown": True,
            "collFormat": "unknown",
            "parts": parts,
        }
        outp = os.path.join(web_dir, level + ".json")
        with open(outp, "w") as fh:
            json.dump(out, fh, separators=(",", ":"))
        print("%-22s %2d part(s), %3d meshes, %7d verts -> %s"
              % (level, len(parts), sum(len(p["meshes"]) for p in parts), nv, outp))
    json.dump(sorted(by_level), open(os.path.join(web_dir, "manifest.json"), "w"),
              separators=(",", ":"))
    return sorted(by_level)
