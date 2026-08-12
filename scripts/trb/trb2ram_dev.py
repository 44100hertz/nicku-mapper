#!/usr/bin/env python3
"""Strict chained block walker, v2 (fixed scoping).

Model under test:
- The runtime world pool = per-object tri-verts appended in object order.
- A file mesh record = a vertex pool (s16 triples in the section its +0x10
  points to) + a 0x98 strip block ([0x98][u16 cnt][cnt records]).
- posIdx reading: recw=4, pos at payload byte 1 -> walk (0,1,2,0,3,0,...).
- The runtime's per-quad tri-verts (a,b,c,c,d,a) come from the file's
  restart-marker walk (a,b,c,a,d,e): position 3 (the restart = the quad's
  first index) is rewritten to the 3rd index.
- Dedup candidates for appending tri-verts to the global pool:
    R1: append every position (no dedup).
    R2: dedup by value against the current global pool.
  The walker accepts the rule whose pool+idx matches the runtime ground truth.
"""
import sys, struct, glob, os
sys.path.insert(0, "/home/cyan/code/nicku-mapper/asset-extract/tools")
import trb_mesh

LEV = "/home/cyan/code/nicku-mapper/asset-extract/nicku-ntsc/P-GNOE/files/Data/dannyphantomlevel1"
RT_POOL = "/tmp/rt_pool.bin"
RT_IDX = "/tmp/rt_idx.bin"

def load_meshes():
    meshes = []  # (name, pool[(x,y,z)], walk[posIdx list])
    for fp in sorted(glob.glob(os.path.join(LEV, "*.trb"))):
        base = os.path.basename(fp)
        try:
            d, sect, sizes = trb_mesh.parse_tsfb(fp)
        except Exception:
            continue
        recs = trb_mesh.mesh_records_symb(fp, d, sect, sizes)
        for k in sorted(recs):
            rec = recs[k]
            sec = rec.get("chunk", k + 1)
            if not (1 <= sec < len(sizes)):
                continue
            chunk = d[sect + sum(sizes[:sec]) : sect + sum(sizes[:sec]) + sizes[sec]]
            A = struct.unpack_from(">I", d, sect + rec["offset"] + 0x14)[0]
            if A < 6 or A > len(chunk):
                continue
            pool = []
            for i in range(0, A - 5, 6):
                pool.append(struct.unpack_from(">hhh", chunk, i))
            boff = struct.unpack_from(">I", d, sect + rec["offset"] + 0x20)[0]
            bsz = struct.unpack_from(">I", d, sect + rec["offset"] + 0x24)[0]
            if bsz < 8:
                continue
            seg = d[sect + boff : sect + boff + bsz]
            if seg[:1] != b"\x98":
                continue
            cnt = struct.unpack_from(">H", seg, 1)[0]
            if 3 + cnt * 4 > len(seg):
                continue
            walk = [seg[3 + i * 4 + 1] for i in range(cnt)]
            if max(walk, default=0) >= len(pool):
                continue
            meshes.append((f"{base}:W0C0M{k}", pool, walk))
    return meshes

def expand(walk):
    """restart-marker rewrite: a quad walk (a,b,c,a,d,e) -> tri-verts
    (a,b,c,c,d,a). All-degenerate trailing records are dropped."""
    out = []
    i = 0
    n = len(walk)
    while i + 5 < n and walk[i + 3] == walk[i]:
        # quad: a,b,c,a,d,e  ->  a,b,c,c,d,a
        out += [walk[i], walk[i + 1], walk[i + 2], walk[i + 2], walk[i + 4], walk[i + 5]]
        i += 6
    if i + 2 <= n and tuple(walk[i:i + 3]) != (0, 0, 0):
        out += [walk[i], walk[i + 1], walk[i + 2]]
    return out

class Builder:
    def __init__(self, rt, idx, nvert):
        self.rt = rt
        self.idx = idx
        self.nvert = nvert
        self.pool = []   # list of (x,y,z) runtime values already built
        self.gidx = []   # built runtime idx list

    def try_object(self, mesh, O, P):
        """Place mesh at offset O; the object's first tri-vert must land at
        runtime pool position P. Verify against rt pool and rt idx.
        Returns (ok, rule, appended_count)."""
        name, mpool, walk = mesh
        tv = expand(walk)
        save_pool, save_gidx = list(self.pool), list(self.gidx)
        for rule in ("R1", "R2"):
            self.pool[:], self.gidx[:] = save_pool, save_gidx
            seen = {}
            log = []
            for fi in tv:
                v = (mpool[fi][0] + O[0], mpool[fi][1] + O[1], mpool[fi][2] + O[2])
                if rule == "R1":
                    ri = self._add(v)
                else:
                    if fi in seen:
                        ri = seen[fi]
                    else:
                        try:
                            ri = self.pool.index(v)
                        except ValueError:
                            ri = self._add(v)
                        seen[fi] = ri
                log.append(ri)
            self.gidx += log
            if self._verify(P, log):
                return True, rule
            self.pool[:], self.gidx[:] = save_pool, save_gidx
        self.pool[:], self.gidx[:] = save_pool, save_gidx
        return False, None

    def _add(self, v):
        self.pool.append(v)
        return len(self.pool) - 1

    def _verify(self, P, log):
        # pool: appended entries must equal rt[P .. P+len]
        app = len(self.pool) - P if P < len(self.pool) else 0
        for i in range(app):
            if self.pool[P + i] != self.rt[P + i]:
                return False
        # idx: the object's tri-verts must equal the runtime idx at the
        # object's idx position (ground truth)
        Q = len(self.gidx) - len(log)
        for i in range(len(log)):
            if self.idx[Q + i] != log[i]:
                return False
        return True

def main():
    meshes = load_meshes()
    print(f"loaded {len(meshes)} meshes")
    pb = open(RT_POOL, "rb").read()
    pf = struct.unpack(">%df" % (len(pb) // 4), pb)
    ib = open(RT_IDX, "rb").read()
    idx = struct.unpack(">%dH" % (len(ib) // 2), ib)
    nvert = len(pb) // 12
    ntri = len(ib) // 6
    rt = [(pf[i * 3] * 64, pf[i * 3 + 1] * 64, pf[i * 3 + 2] * 64) for i in range(nvert)]
    print(f"runtime: {nvert} verts, {ntri} tris")

    b = Builder(rt, idx, nvert)

    # seed: the first floor quad, file values (5632,12992),(5632,13248),(5376,13248),(5376,12992)
    seed_pool = [(5632, 12992, -384), (5632, 13248, -384), (5376, 13248, -384), (5376, 12992, -384)]
    seed = None
    for m in meshes:
        if m[1][:4] == seed_pool:
            seed = m
            break
    if not seed:
        print("seed mesh not found!"); return
    name, pool, walk = seed
    tv = expand(walk)
    O = (rt[0][0] - pool[tv[0]][0], rt[0][1] - pool[tv[0]][1], rt[0][2] - pool[tv[0]][2])
    ok, rule = b.try_object(seed, O, 0)
    if not ok:
        print(f"seed {name} failed"); return
    print(f"seed {name}: walk={walk} tv={tv} O={O} rule={rule} pool→{len(b.pool)}")

    steps = 1
    stalls = 0
    while len(b.pool) < nvert and steps < 40000:
        P = len(b.pool)
        target0 = b.rt[P]
        found = False
        for m in meshes:
            mn, mp, mw = m
            tvm = expand(mw)
            if not tvm or any(mp[fi] == (0, 0, 0) for fi in tvm):
                continue
            O2 = (target0[0] - mp[tvm[0]][0], target0[1] - mp[tvm[0]][1], target0[2] - mp[tvm[0]][2])
            ok, rule = b.try_object(m, O2, P)
            if ok:
                found = True
                break
        if not found:
            stalls += 1
            print(f"STALL at pool pos {P} rt[P]={target0} after {steps} objects (pool {len(b.pool)}/{nvert})")
            break
        steps += 1
        if steps % 100 == 0 or steps < 12:
            print(f"obj {steps}: {found and m[0]} rule={rule} pool→{len(b.pool)} idx→{len(b.gidx)}")
    print(f"\nDONE: {steps} objects, pool {len(b.pool)}/{nvert} ({100.0*len(b.pool)/nvert:.1f}%), "
          f"idx {len(b.gidx)}/{len(idx)} ({100.0*len(b.gidx)/len(idx):.1f}%)")

if __name__ == "__main__":
    main()
