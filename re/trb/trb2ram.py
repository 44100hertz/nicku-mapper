#!/usr/bin/env python3
"""trb2ram.py — Route A→B pipeline for the Nicktoons Unite! collision world.

Decode the DP1 TRB collision meshes into the runtime RAM model
(pool + idx + layers), then emit the viewer JSON (route B).

Ground-truth verification: compare the built pool/idx byte-exact against a
RAM dump of the in-level collision world (e.g. /tmp/rt_pool.bin + rt_idx.bin).

Status (documented honestly):
  - posIdx reading for the 0x98 strip: recw=4, pos at payload byte 1.
  - The first quad of each record expands (a,b,c,X,d,e) -> (a,b,c,c,d,a)
    (the 4th position is a restart marker, rewritten to the 3rd index).
  - Objects = mesh placements (mesh pool + per-object offset). The pool is
    appended in tri-verts order with a value-dedup rule (R1: none, R2: vs the
    current pool, R3: vs the pool at the object's start). The walker accepts
    the rule whose pool+idx matches the runtime ground truth.
  - OPEN: the multi-quad strip (records 6+ of an 11-record block) — the
    trailing records read (0,0,0,0,0) under the first-quad reading; the
    runtime's second-quad tri-verts (4,5,1,1,0,4) aren't derivable yet.
  - OPEN: the file-side instance list (the "Collision" resource: volume
    records + u16 W0C0M mesh-ref arrays) has not been located in the TRBs.

Usage:
  trb2ram.py [--verify] [--json out.json] [--level DIR]
"""
import argparse, glob, json, os, struct, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "asset-extract", "tools"))
import trb_mesh  # noqa: E402

DEFAULT_LEVEL = os.path.join(
    os.path.dirname(__file__), "..", "..", "asset-extract", "nicku-ntsc",
    "P-GNOE", "files", "Data", "dannyphantomlevel1")


def load_meshes(level):
    """Parse all *.trb in the level dir. Returns (name, pool, seg) tuples where
    seg = the raw 0x98 strip block."""
    meshes = []
    for fp in sorted(glob.glob(os.path.join(level, "*.trb"))):
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
            chunk = d[sect + sum(sizes[:sec]): sect + sum(sizes[:sec]) + sizes[sec]]
            A = struct.unpack_from(">I", d, sect + rec["offset"] + 0x14)[0]
            if A < 6 or A > len(chunk):
                continue
            pool = []
            poolf = []
            poolz5 = []
            for i in range(0, A - 5, 6):
                x, y, z = struct.unpack_from(">hhh", chunk, i)
                pool.append((x, y, z))
                poolz5.append((x, y, round(z / 5, 4)))
            for i in range(0, max(0, A - 11), 12):
                poolf.append(tuple(round(x * 64, 4) for x in struct.unpack_from(">fff", chunk, i)))
            if not pool and poolf:
                pool = poolf
            else:
                poolf = []
            boff = struct.unpack_from(">I", d, sect + rec["offset"] + 0x20)[0]
            bsz = struct.unpack_from(">I", d, sect + rec["offset"] + 0x24)[0]
            if bsz < 8:
                continue
            seg = d[sect + boff: sect + boff + bsz]
            if seg[:1] != b"\x98":
                continue
            meshes.append((f"{base}:W0C0M{k}", pool, poolf, poolz5, seg))
    return meshes


def expand_seg(seg):
    """Decode a mixed-width 0x98 strip block into tri-verts (file indices).

    Layout (empirically verified against the runtime ground truth):
      [0x98][u16 cnt]
      quad 1: 6 records x 4 bytes, posIdx at byte 1 -> walk (a,b,c,X,d,e),
              restart-rewrite -> tri-verts (a,b,c,c,d,a)
      subsequent quads: 5 records x 3 bytes, posIdx at byte 0 -> walk
              (a',b',c',d',X') with the closing implicit -> tri-verts
              (b',c',a',a',d',b')
    All-degenerate trailing records are dropped."""
    cnt = struct.unpack_from(">H", seg, 1)[0]
    out = []
    i = 0
    pos = 3
    # quad 1: 6 records x 4 bytes, pos@byte1
    if i + 5 < cnt and pos + 24 <= len(seg):
        w = [seg[pos + 4 * j + 1] for j in range(6)]
        if w[3] == w[0]:
            out += [w[0], w[1], w[2], w[2], w[4], w[5]]
            i += 6
            pos += 24
    # subsequent quads: 5 records x 3 bytes, pos@byte0, rotated expansion
    while i + 4 < cnt and pos + 15 <= len(seg):
        w = [seg[pos + 3 * j] for j in range(5)]
        if tuple(w) == (0, 0, 0, 0, 0):
            break
        a, b, c, d, X = w
        out += [b, c, a, a, d, b]
        i += 5
        pos += 15
    if not out:
        # non-quad (triangle-strip) record: tri-verts = the recw-4-po-1 walk
        out = [seg[3 + 4 * j + 1] for j in range(min(cnt, (len(seg) - 3) // 4))]
        out = [x for x in out if x != 0] or out
    return out


class Builder:
    """Builds the world pool + idx from mesh placements, verifying against
    the runtime ground truth as it goes.

    The compiler's per-object append rule is not single-valued, so the walker
    tries several rules per object and accepts the one whose pool+idx match
    the runtime:
      R1: append every tri-vert (no dedup).
      R2: value-dedup against the current pool (reuse the first match).
      R3: append iff value not in P0 (pool at the object's start); the
          c-dupe / closing-a positions append only when P0 is empty.
    """

    def __init__(self, rt_pool, rt_idx):
        self.rt = rt_pool          # list of (x,y,z) tuples (f32*64)
        self.idx = rt_idx          # list of ints
        self.pool = []
        self.gidx = []

    def _place(self, part, mpool, O, rule):
        P0 = set(self.pool) if len(self.pool) > 0 else None
        log = []
        for i, fi in enumerate(part):
            v = (mpool[fi][0] + O[0], mpool[fi][1] + O[1], mpool[fi][2] + O[2])
            if rule == "R1":
                ri = self._add(v)
            elif rule == "R2":
                try:
                    ri = self.pool.index(v)
                except ValueError:
                    ri = self._add(v)
            elif rule == "R3":
                pos_in_quad = i % 6
                if pos_in_quad in (3, 5):
                    ri = self._add(v) if P0 is None else                         (log[i - 1] if pos_in_quad == 3 else log[i - 5])
                else:
                    if P0 is not None and v in P0:
                        ri = self.pool.index(v)
                    else:
                        ri = self._add(v)
            else:  # R4: append iff value not in P0 (all positions)
                if P0 is not None and v in P0:
                    ri = self.pool.index(v)
                else:
                    ri = self._add(v)
            log.append(ri)
        return log

    def _verify(self, P, log):
        app = len(self.pool) - P if P < len(self.pool) else 0
        for i in range(app):
            if self.pool[P + i] != self.rt[P + i]:
                return False
        Q = len(self.gidx)   # the log is NOT yet appended during a try
        for i in range(len(log)):
            if Q + i >= len(self.idx) or self.idx[Q + i] != log[i]:
                return False
        return True

    def try_object(self, mesh, O, P):
        """Place mesh at offset O with its first tri-vert at pool position P.
        Tries both pool encodings (s16 / f32), the full tri-verts and each
        quad split, under every dedup rule; returns the longest placement
        whose pool+idx match the runtime ground truth."""
        name, mpool_s16, mpool_f32, mpool_z5, seg = mesh
        tv = expand_seg(seg)
        for mpool in (mpool_s16, mpool_f32, mpool_z5):
            if not mpool or any(fi >= len(mpool) for fi in tv):
                continue
            splits = [tv] + [tv[:s] for s in range(6, len(tv), 6)] + \
                     [tv[s:] for s in range(6, len(tv), 6)]
            best = None
            for rule in ("R1", "R2", "R3", "R4"):
                for part in sorted(splits, key=len, reverse=True):
                    if not part:
                        continue
                    save_pool, save_gidx = list(self.pool), list(self.gidx)
                    log = self._place(part, mpool, O, rule)
                    ok = self._verify(P, log)
                    if ok and (best is None or len(part) > best[0]):
                        best = (len(part), list(self.pool), list(self.gidx), log)
                    self.pool[:], self.gidx[:] = save_pool, save_gidx
            if best is None:
                continue
            _, pool, gidx, log = best
            self.pool[:], self.gidx[:] = pool, gidx + log
            return True, "R0"
        return False, None

    def _add(self, v):
        self.pool.append(v)
        return len(self.pool) - 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", default=DEFAULT_LEVEL)
    ap.add_argument("--verify", action="store_true",
                    help="verify against /tmp/rt_pool.bin + /tmp/rt_idx.bin")
    ap.add_argument("--json", metavar="OUT", help="emit viewer JSON (route B; implies --verify)")
    args = ap.parse_args()

    meshes = load_meshes(args.level)
    print(f"loaded {len(meshes)} meshes from {args.level}")

    if args.verify or args.json:
        pb = open("/tmp/rt_pool.bin", "rb").read()
        pf = struct.unpack(">%df" % (len(pb) // 4), pb)
        ib = open("/tmp/rt_idx.bin", "rb").read()
        idx = list(struct.unpack(">%dH" % (len(ib) // 2), ib))
        nvert = len(pb) // 12
        rt = [(pf[i * 3] * 64, pf[i * 3 + 1] * 64, pf[i * 3 + 2] * 64) for i in range(nvert)]
    else:
        idx, rt, nvert = [], [], 0

    b = Builder(rt, idx)

    # seed: the first floor quad (W0C0M113 in DPWorld_Level01_04.trb)
    seed_pool = [(5632, 12992, -384), (5632, 13248, -384), (5376, 13248, -384), (5376, 12992, -384)]
    seed = next((m for m in meshes if m[1][:4] == seed_pool), None)
    if not seed:
        print("seed mesh not found!"); return 1
    name, pool, _, _, seg = seed
    tv = expand_seg(seg)
    O = (rt[0][0] - pool[tv[0]][0], rt[0][1] - pool[tv[0]][1], rt[0][2] - pool[tv[0]][2])
    ok, rule = b.try_object(seed, O, 0)
    if not ok:
        print(f"seed {name} failed (tv={tv})"); return 1
    print(f"seed {name}: tv={tv} O={O} rule={rule}")

    steps = 1
    while len(b.pool) < nvert and steps < 40000:
        P = len(b.pool)
        target0 = b.rt[P]
        best = None
        for m in meshes:
            tvm = expand_seg(m[4])
            mpool0 = m[1] if m[1] else m[2]
            if not tvm or any(fi >= len(mpool0) or mpool0[fi] == (0, 0, 0) for fi in tvm):
                continue
            O2 = (target0[0] - mpool0[tvm[0]][0], target0[1] - mpool0[tvm[0]][1],
                  target0[2] - mpool0[tvm[0]][2])
            ok, rule = b.try_object(m, O2, P)
            if ok and (best is None or len(tvm) > best[2]):
                best = (m, rule, len(tvm))
        if best is None:
            print(f"STALL at pool pos {P} rt[P]={target0} after {steps} objects "
                  f"(pool {len(b.pool)}/{nvert})")
            break
        m, rule, tvlen = best
        if len(b.pool) <= P:
            print(f"DEGENERATE at pool pos {P} (no growth) — stopping")
            break
        steps += 1
        if steps % 500 == 0 or steps < 12:
            print(f"obj {steps}: {m[0]} rule={rule} tvlen={tvlen} pool->{len(b.pool)}")
    pct_p = 100.0 * len(b.pool) / nvert if nvert else 0
    pct_i = 100.0 * len(b.gidx) / len(idx) if idx else 0
    print(f"\nDONE: {steps} objects, pool {len(b.pool)}/{nvert} ({pct_p:.1f}%), "
          f"idx {len(b.gidx)}/{len(idx)} ({pct_i:.1f}%)")

    if args.json:
        # route B: RAM model -> viewer JSON (verts are file coords = round(f32*64))
        out = {
            "generator": "trb2ram.py",
            "facesMode": "triples",
            "layers": [{"start": 0, "count": len(b.gidx) // 3, "flags": 0x27}],
            "pool": [[round(x), round(y), round(z)] for (x, y, z) in b.pool],
            "idx": b.gidx,
        }
        json.dump(out, open(args.json, "w"), separators=(",", ":"))
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
