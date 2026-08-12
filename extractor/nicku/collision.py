"""Collision decoder: AssetsAuto.nta -> the collision world (1:1 with runtime).

Two formats exist across the 15 levels (see docs/collision-status.md):

  Format A — nta pool/idx resource (9 levels: DP1/3, JNLab, JN1_01, SB1/2/3,
  TT1/2). The nta holds `{poolcnt, data_len, idxcnt, layercnt}` + layer
  records; pool = f32 triples (x64-scaled), idx = u16 triples directly after.
  Proven byte-exact against the s02 RAM dump.

  Format B — nta main-resource world (6 levels: DP2/4, JN4, SB4, TT4,
  TestWorld). The MAIN resource holds a nested TSFB whose object table
  `{1, p0, p1, -1, pool_off, nverts, idx_off, nidx, layercnt, layrecs}`
  locates the pool/idx; layer names are read from the file.

`decode_level` tries Format A first (it is the primary resource form) and
falls back to Format B — this reproduces the verified 9/6 split (SpongeBob2
matches both structural scans, but its real collision data is Format A).
"""
import struct

LAYER_FLAGS = ("0x27", "0x26", "0x7")
LAYER_NAMES = ("default", "collision_nopathfind", "collision_noocclude")

# Levels are detected structurally (A-first), not from this list; it is kept
# as the verified reference only.
FORMAT_A_LEVELS = ("dannyphantomlevel1", "dannyphantomlevel3",
                   "JimmyNeutronLab", "JimmyNeutronLevel1_01",
                   "SpongeBobLevel1", "SpongeBobLevel2", "SpongeBobLevel3",
                   "TimmyTurnerLevel1", "TimmyTurnerLevel2")
FORMAT_B_LEVELS = ("dannyphantomlevel2", "dannyphantomlevel4",
                   "JimmyNeutronLevel4", "SpongeBobLevel4",
                   "TimmyTurnerLevel4", "TestWorld")


# ----------------------------------------------------------------------
# Format A — nta pool/idx resource
# ----------------------------------------------------------------------
def parse_nta(d):
    """Format A: parse every collision resource in the nta and merge them.

    Multi-resource ntas hold one resource per sub-level (JN1, SB1, SB3), so
    the merged result is the WHOLE level. Returns a world dict or None when
    the nta is not a Format-A container.
    """
    def try_header(off):
        poolcnt, x, idxcnt, layercnt = struct.unpack_from(">4I", d, off)
        if layercnt < 1 or layercnt > 8 or poolcnt <= 0 or idxcnt <= 0:
            return None
        if poolcnt > 500000 or idxcnt > 500000:
            return None
        counts = []
        for i in range(layercnt):
            c = struct.unpack_from(">I", d, off + 0x10 + i * 0x18 + 0x10)[0]
            if c <= 0 or c > 1000000:
                return None
            counts.append(c)
        if sum(counts) * 3 != idxcnt:
            return None
        pool_off = off + 0x10 + layercnt * 0x18 + 4
        idx_off = pool_off + poolcnt * 12
        if idx_off + idxcnt * 2 > len(d):
            return None
        x0, y0, z0 = struct.unpack_from(">fff", d, pool_off)
        if not (-1e6 < x0 < 1e6 and -1e6 < y0 < 1e6 and -1e6 < z0 < 1e6):
            return None
        i0 = struct.unpack_from(">6H", d, idx_off)
        if max(i0) >= poolcnt:
            return None
        return (off, poolcnt, x, idxcnt, layercnt, pool_off, idx_off, counts)

    headers = []
    for off in range(len(d) - 0x60):
        h = try_header(off)
        if h:
            headers.append(h)
    if not headers:
        return None
    pool, idx, counts = [], [], []
    for off, poolcnt, x, idxcnt, layercnt, pool_off, idx_off, c in headers:
        base = len(pool)
        pool.extend(struct.unpack_from(">fff", d, pool_off + i * 12) for i in range(poolcnt))
        idx.extend(base + v for v in struct.unpack_from(">%dH" % idxcnt, d, idx_off))
        for k, cc in enumerate(c):
            if k >= len(counts):
                counts.append(0)
            counts[k] += cc
    return dict(poolcnt=len(pool), idxcnt=len(idx), pool=pool, idx=idx,
                counts=counts)


# ----------------------------------------------------------------------
# Format B — nta main-resource nested TSFB
# ----------------------------------------------------------------------
def _find_tsfb_sect(nta, hit):
    for t in range(hit - 0x40, hit - 0x40000, -1):
        if nta[t:t + 4] != b"TSFB":
            continue
        cnt = struct.unpack_from(">I", nta, t + 0x18)[0]
        if cnt < 1 or cnt > 0x400:
            continue
        sizes = [struct.unpack_from(">I", nta, t + 0x20 + i * 16)[0]
                 for i in range(cnt)]
        sect = t + 0x20 + cnt * 16 + 4
        if any(s > 0x400000 for s in sizes) or sum(sizes) != \
                struct.unpack_from(">I", nta, t + 0x20 + cnt * 16)[0]:
            continue
        objtab = struct.unpack_from(">I", nta, sect + 0x34)[0]
        if 0 < objtab < 0x100000 and sect + objtab == hit:
            return t, sect, objtab
    return None, None, None


def parse_world(nta):
    """Format B: decode the nested-TSFB world object table. Returns a world
    dict or None when the nta is not a Format-B container."""
    best = None
    for off in range(0, len(nta) - 0x30, 4):
        a, b, c, d, e, f, g, h, i, j = struct.unpack_from(">10I", nta, off)
        if a == 1 and d == 0xffffffff and 1 <= i <= 8:
            if 100 < f < 500000 and 100 < h < 1000000:
                if e + f * 12 == g and e + f * 12 + h * 2 < len(nta):
                    t, sect, objtab = _find_tsfb_sect(nta, off)
                    if t is not None:
                        best = (off, f, g, h, i, j, e, sect)
                        break
    if best is None:
        return None
    hit, nverts, idxrel, nidx, layercnt, layrecs, poolrel, sect = best
    pool_off = sect + poolrel
    idx_off = sect + idxrel
    pool = [struct.unpack_from(">fff", nta, pool_off + i * 12)
            for i in range(nverts)]
    idx = list(struct.unpack_from(">%dH" % nidx, nta, idx_off))
    counts, names = [], []
    for k in range(layercnt):
        rec = sect + layrecs + k * 0x18
        counts.append(struct.unpack_from(">I", nta, rec + 0xc)[0])
        name_rel = struct.unpack_from(">I", nta, rec + 0)[0]
        s = nta[sect + name_rel:].split(b"\x00")[0].decode("latin1")
        names.append(s)
    return dict(nverts=nverts, nidx=nidx, pool=pool, idx=idx,
                counts=counts, names=names)


# ----------------------------------------------------------------------
# viewer JSON
# ----------------------------------------------------------------------
def to_viewer_json(world, level, coll_format, names=None):
    poolcnt = len(world["pool"])
    verts = [round(v * 64) for p in world["pool"] for v in p]
    xs = [p[0] * 64 for p in world["pool"]]
    ys = [p[1] * 64 for p in world["pool"]]
    zs = [p[2] * 64 for p in world["pool"]]
    bounds = [min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)]
    meshes = []
    start = 0
    for k, tric in enumerate(world["counts"]):
        name = (names[k] if names and k < len(names) else
                (LAYER_NAMES[k] if k < len(LAYER_NAMES) else "default"))
        flag = LAYER_FLAGS[k] if k < len(LAYER_FLAGS) else "0x7"
        n = tric * 3
        meshes.append({
            "k": k,
            "name": name,
            "flag": flag,
            "count": poolcnt,
            "verts": verts,
            "faces": world["idx"][start:start + n],
        })
        start += n
    return {
        "format": "mesh-v2",
        "level": level,
        "entityFile": "AssetsAuto.nta",
        "div": 64,
        "yDown": True,
        "collFormat": coll_format,
        "facesMode": "triples",
        "parts": [{
            "file": "AssetsAuto.nta",
            "meshCount": len(meshes),
            "levelBounds": bounds,
            "meshes": meshes,
        }],
    }


def decode_level(nta_path, level):
    """Decode one level's AssetsAuto.nta into a viewer JSON dict (or None).

    Tries Format A first, falls back to Format B (see module docstring).
    """
    d = open(nta_path, "rb").read()
    w = parse_nta(d)
    if w is not None:
        return to_viewer_json(w, level, "nta collision resource")
    w = parse_world(d)
    if w is not None:
        return to_viewer_json(w, level, "nta main-resource world (nested TSFB)",
                              names=w["names"])
    return None
