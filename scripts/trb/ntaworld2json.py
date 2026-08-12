#!/usr/bin/env python3
"""Release decoder for the "no-collision-resource" levels (DP2/4, JN4, SB4,
TT4, TestWorld): the world mesh lives in the nta's MAIN resource (a nested
TSFB), not in a separate pool/idx resource like the nta2json levels.

Found structurally (see docs/collision-status.md "The DP2 format" section,
RESOLVED 2025-xx):
  - The main resource TSFB's SECT header: {1, bound, 0x0c, meshcnt, 0, 2, 0,
    4xf32 bounds, 1, 0x34, objtab_off, 0, 0, object name}.
  - Object table @ SECT+objtab_off (10 u32s):
        {1, p0, p1, -1, pool_off, nverts, idx_off, nidx, layercnt, layrecs}
    where pool_off + nverts*12 == idx_off (f32 pool directly followed by the
    u16 idx), layrecs = layer-record array.
  - Layer records (0x18 stride): {meshrec_ptr, name_ptr, 0, ?, tricnt, ?}.
  - Layer names: "default" / "collision_nopathfind" / "collision_noocclude"
    (same as the nta2json levels; counts verified by idx split).

Verified (DP2): pool 13082 f32 verts (bbox x[-69.2,59.7] y[-2.5,168.8]
z[-3.87,18]) + idx 21768 u16 (7256 tris, max 13081) + 3 layers
6929/36/291 = the runtime layer names. The other 5 levels decode with the
same routine (1-2 layers).

Usage: nta2json-style --json OUT; also emits all levels when given --all.
"""
import json
import struct
import sys

LAYER_FLAGS = ("0x27", "0x26", "0x7")
LAYER_NAMES = ("default", "collision_nopathfind", "collision_noocclude")


def find_tsfb_sect(nta, hit):
    """Backward-scan from the object-table hit for the owning TSFB; return
    (tsfb_off, sect_off, objtab_rel) or None."""
    for t in range(hit - 0x40, hit - 0x40000, -1):
        if nta[t:t + 4] != b"TSFB":
            continue
        cnt = struct.unpack_from(">I", nta, t + 0x18)[0]
        if cnt < 1 or cnt > 0x400:
            continue
        sizes = [struct.unpack_from(">I", nta, t + 0x20 + i * 16)[0]
                 for i in range(cnt)]
        # "TCES" tag overlaps the last chunk-table entry's padding; the
        # SECT size field sits at table end, SECT data right after it.
        sect = t + 0x20 + cnt * 16 + 4
        if any(s > 0x400000 for s in sizes) or sum(sizes) != \
                struct.unpack_from(">I", nta, t + 0x20 + cnt * 16)[0]:
            continue
        objtab = struct.unpack_from(">I", nta, sect + 0x34)[0]
        # the world object table can sit past the TSFB's chunked sections
        # (the nta resource = TSFB + volume records + pool/idx); the SECT
        # header's own object-table offset is the authoritative check.
        if 0 < objtab < 0x100000 and sect + objtab == hit:
            return t, sect, objtab
    return None, None, None


def parse_world(nta, hit=None):
    """Find the world object table and decode pool/idx/layers."""
    if hit is None:
        best = None
        for off in range(0, len(nta) - 0x30, 4):
            a, b, c, d, e, f, g, h, i, j = struct.unpack_from(">10I", nta, off)
            if a == 1 and d == 0xffffffff and 1 <= i <= 8:
                if 100 < f < 500000 and 100 < h < 1000000:
                    if e + f * 12 == g and e + f * 12 + h * 2 < len(nta):
                        t, sect, objtab = find_tsfb_sect(nta, off)
                        if t is not None:
                            best = (off, f, g, h, i, j, e, sect)
                            break
        if best is None:
            raise SystemExit("world object table not found in nta")
        hit, nverts, idxrel, nidx, layercnt, layrecs, poolrel, sect = best
    else:
        nverts = struct.unpack_from(">I", nta, hit + 0x14)[0]
        idxrel = struct.unpack_from(">I", nta, hit + 0x18)[0]
        nidx = struct.unpack_from(">I", nta, hit + 0x1c)[0]
        layercnt = struct.unpack_from(">I", nta, hit + 0x20)[0]
        layrecs = struct.unpack_from(">I", nta, hit + 0x24)[0]
        poolrel = struct.unpack_from(">I", nta, hit + 0x10)[0]
        _, sect, _ = find_tsfb_sect(nta, hit)
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
    if sum(counts) * 3 != nidx:
        print(f"WARNING: layer counts {counts} *3 != nidx {nidx}")
    return dict(nverts=nverts, nidx=nidx, pool=pool, idx=idx,
                counts=counts, names=names, hit=hit,
                sect=sect, idx_off=idx_off)


def to_viewer_json(world, level="dpl2_c1"):
    poolcnt = world["nverts"]
    verts = [round(v * 64) for p in world["pool"] for v in p]
    xs = [p[0] * 64 for p in world["pool"]]
    ys = [p[1] * 64 for p in world["pool"]]
    zs = [p[2] * 64 for p in world["pool"]]
    bounds = [min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)]
    meshes = []
    start = 0
    for k, tric in enumerate(world["counts"]):
        name = world["names"][k] if k < len(world["names"]) else LAYER_NAMES[k]
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
        "collFormat": "nta main-resource world (nested TSFB)",
        "facesMode": "triples",
        "parts": [{
            "file": "AssetsAuto.nta",
            "meshCount": len(meshes),
            "levelBounds": bounds,
            "meshes": meshes,
        }],
    }


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--nta", default=None, help="AssetsAuto.nta path")
    ap.add_argument("--json", metavar="OUT", help="emit viewer JSON")
    ap.add_argument("--all", action="store_true",
                    help="decode all no-resource levels and write their JSONs")
    args = ap.parse_args()

    if args.all:
        import glob
        import os
        base = (args.nta or
                "/home/cyan/code/nicku-mapper/asset-extract/nicku-ntsc/"
                "P-GNOE/files/Data")
        levels = ["dannyphantomlevel2", "dannyphantomlevel4",
                  "JimmyNeutronLevel4", "SpongeBobLevel4",
                  "TimmyTurnerLevel4", "TestWorld"]
        for lvl in levels:
            p = os.path.join(base, lvl, "AssetsAuto.nta")
            try:
                w = parse_world(open(p, "rb").read())
            except SystemExit as e:
                print(f"{lvl}: {e}")
                continue
            out = f"/home/cyan/code/nicku-mapper/web/collision/{lvl}-coll.json"
            json.dump(to_viewer_json(w, lvl), open(out, "w"),
                      separators=(",", ":"))
            print(f"{lvl}: {w['nverts']} verts {w['nidx']} idx "
                  f"layers={w['counts']} names={w['names']} -> {out}")
        return

    nta = open(args.nta or
               "/home/cyan/code/nicku-mapper/asset-extract/nicku-ntsc/"
               "P-GNOE/files/Data/dannyphantomlevel2/AssetsAuto.nta",
               "rb").read()
    w = parse_world(nta)
    print(f"hit @ {w['hit']:#x} sect @ {w['sect']:#x} idx_off {w['idx_off']:#x}")
    print(f"nverts={w['nverts']} nidx={w['nidx']} "
          f"layers={w['counts']} names={w['names']}")
    if args.json:
        json.dump(to_viewer_json(w), open(args.json, "w"),
                  separators=(",", ":"))
        print(f"wrote {args.json}")


if __name__ == "__main__":
    main()
