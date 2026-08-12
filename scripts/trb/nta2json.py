#!/usr/bin/env python3
"""Release decoder: AssetsAuto.nta -> the collision world (1:1 with the runtime).

Proven byte-exact (multipass, grilled-dolphin):
  - pool  = f32 triples @ header+0x5c,  count = header[0] (11379), x64-scaled
  - idx   = u16 triples @ pool_end,     count = header[2] (17973)
  - layers = 3 records @ header+0x10 (0x18 each): count @ +0x10
The runtime builds the world by concatenating these two streams directly
(no offsets, no dedup — the chained walker in trb2ram.py is superseded).

Verified: pool + idx byte-identical to the s02 RAM dump (/tmp/rt_pool.bin,
/tmp/rt_idx.bin), and the emitted viewer JSON == the runtime-dump JSON.
"""
import json
import struct
import sys

HEADER_MARK = 0x21aac0  # DPWorld_Level04_01_Detail (dpl1_c1); see notes below

LAYER_FLAGS = ("0x27", "0x26", "0x7")
LAYER_NAMES = ("default", "collision_nopathfind", "collision_noocclude")


def parse_nta(path):
    d = open(path, "rb").read()
    # Locate the collision resource header: {poolcnt, data_len, idxcnt, layercnt}
    # The pool follows at +0x5c and the idx at pool + poolcnt*12.
    best = None
    for off in range(len(d) - 0x60):
        poolcnt, x, idxcnt, layercnt = struct.unpack_from(">4I", d, off)
        if layercnt < 1 or layercnt > 8 or poolcnt <= 0 or idxcnt <= 0:
            continue
        if poolcnt > 500000 or idxcnt > 500000:
            continue
        # layer records: layercnt x 0x18 at off+0x10, tri count @ +0x10; the
        # pool follows the records (off + 0x10 + layercnt*0x18 + 4)
        counts = []
        ok = True
        for i in range(layercnt):
            c = struct.unpack_from(">I", d, off + 0x10 + i * 0x18 + 0x10)[0]
            if c <= 0 or c > 1000000:
                ok = False
                break
            counts.append(c)
        if not ok or sum(counts) * 3 != idxcnt:
            continue
        pool_off = off + 0x10 + layercnt * 0x18 + 4
        idx_off = pool_off + poolcnt * 12
        if idx_off + idxcnt * 2 > len(d):
            continue
        # sanity: pool[0] must look like a coordinate (small float)
        x0, y0, z0 = struct.unpack_from(">fff", d, pool_off)
        if not (-1e6 < x0 < 1e6 and -1e6 < y0 < 1e6 and -1e6 < z0 < 1e6):
            continue
        # sanity: idx[0..5] are valid pool indices
        i0 = struct.unpack_from(">6H", d, idx_off)
        if max(i0) >= poolcnt:
            continue
        best = (off, poolcnt, x, idxcnt, layercnt, pool_off, idx_off)
        break
    if best is None:
        raise SystemExit(f"collision resource header not found in {path}")
    off, poolcnt, x, idxcnt, layercnt, pool_off, idx_off = best
    print(f"header @ {off:#x}: poolcnt={poolcnt} data_len={x} idxcnt={idxcnt} layers={layercnt}")
    pool = [struct.unpack_from(">fff", d, pool_off + i * 12) for i in range(poolcnt)]
    idx = list(struct.unpack_from(">%dH" % idxcnt, d, idx_off))
    # layer tri counts from the layer records at header+0x10 (0x18 each, count@+0x10)
    counts = []
    for i in range(layercnt):
        rec = off + 0x10 + i * 0x18
        counts.append(struct.unpack_from(">I", d, rec + 0x10)[0])
    print(f"layer tri counts: {counts}")
    return dict(poolcnt=poolcnt, idxcnt=idxcnt, pool=pool, idx=idx,
                counts=counts, data_len=x)


def to_viewer_json(world, level="dpl1_c1"):
    poolcnt = world["poolcnt"]
    verts = [round(v * 64) for p in world["pool"] for v in p]
    # the runtime pool = the x64 f32 values; the viewer divides by div=64
    xs = [p[0] * 64 for p in world["pool"]]
    ys = [p[1] * 64 for p in world["pool"]]
    zs = [p[2] * 64 for p in world["pool"]]
    bounds = [min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)]
    meshes = []
    start = 0
    for k, (tric, flag, name) in enumerate(zip(world["counts"], LAYER_FLAGS, LAYER_NAMES)):
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
        "collFormat": "nta collision resource",
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
    ap.add_argument("--verify", nargs=2, metavar=("POOL_BIN", "IDX_BIN"),
                    help="byte-exact verify vs RAM dump")
    ap.add_argument("--diff", metavar="RT_JSON", help="diff vs runtime-dump JSON")
    args = ap.parse_args()
    nta = args.nta or "/home/cyan/code/nicku-mapper/asset-extract/nicku-ntsc/P-GNOE/files/Data/dannyphantomlevel1/AssetsAuto.nta"
    world = parse_nta(nta)
    if args.verify:
        rp = open(args.verify[0], "rb").read()
        ri = open(args.verify[1], "rb").read()
        p = b"".join(struct.pack(">fff", *v) for v in world["pool"])
        i = struct.pack(">%dH" % world["idxcnt"], *world["idx"])
        print("pool MATCH:", p == rp)
        print("idx  MATCH:", i == ri)
    if args.json:
        out = to_viewer_json(world)
        json.dump(out, open(args.json, "w"), separators=(",", ":"))
        print(f"wrote {args.json} ({len(out['parts'][0]['meshes'][0]['faces'])} faces L0)")
    if args.diff:
        rt = json.load(open(args.diff))
        ours = to_viewer_json(world)
        same = rt == ours
        print("JSON == runtime dump:", same)
        if not same:
            for p0, p1 in zip(rt["parts"][0]["meshes"], ours["parts"][0]["meshes"]):
                for key in ("name", "flag", "count"):
                    if p0.get(key) != p1.get(key):
                        print(f"  mesh k={p0['k']} {key}: rt={p0.get(key)!r} ours={p1.get(key)!r}")
                if p0["verts"] != p1["verts"]:
                    print(f"  mesh k={p0['k']} verts differ (len {len(p0['verts'])} vs {len(p1['verts'])})")
                if p0["faces"] != p1["faces"]:
                    print(f"  mesh k={p0['k']} faces differ (len {len(p0['faces'])} vs {len(p1['faces'])})")


if __name__ == "__main__":
    main()
