#!/usr/bin/env python3
"""Find accepted decodes whose triangles are GIANT (spanning tens of world
units) — the sliver sources — and dump their identity + decode details."""
import glob, os, struct, sys, math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trb_mesh as tm

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "..", "nicku-ntsc", "P-GNOE", "files", "Data")


def s16(v):
    return v if v < 0x8000 else v - 0x10000


def analyze(d, sect, sizes, recs, k):
    """Re-run the accepted decode; return (recw, posw, poolsize, maxedge_world,
    nreal, nbig, coverage) or None."""
    rec = recs[k]
    boff = struct.unpack_from(">I", d, sect + rec["offset"] + 0x20)[0]
    bsz = struct.unpack_from(">I", d, sect + rec["offset"] + 0x24)[0]
    seg = d[sect + boff:sect + boff + bsz]
    if len(seg) < 5 or seg[0] != 0x98:
        return None
    cnt = struct.unpack_from(">H", seg, 1)[0]
    if not (2 <= cnt <= 100000):
        return None
    chunk = tm.chunk_of(d, sect, sizes, rec.get("chunk", k + 1))
    radius_raw = rec["radius"] * 64 * 2.2
    cx, cz, cy = rec["center"]
    rr = rec["radius"] * 1.25
    best = None
    for recw in range(3, 13):
        for is_u8 in (True, False):
            if 3 + cnt * recw > len(seg):
                continue
            pos = [seg[3 + i * recw] for i in range(cnt)] if is_u8 else \
                  [struct.unpack_from(">H", seg, 3 + i * recw)[0] for i in range(cnt)]
            mx = max(pos)
            if (mx + 1) * 6 > len(chunk):
                continue
            pool = []
            for j in range(mx + 1):
                x, z, y = struct.unpack_from(">HHH", chunk, j * 6)
                pool.append((s16(x), s16(z), s16(y)))
            insphere = sum(1 for p in pool if math.sqrt((p[0]/64-cx)**2 + (p[1]/64-cz)**2 + (p[2]/64-cy)**2) < rr)
            if insphere < 0.5 * len(pool):
                continue
            small = big = deg = 0
            edge_share = {}
            used = set()
            maxedge = 0
            for i in range(cnt - 2):
                a, b, c = pos[i], pos[i + 1], pos[i + 2]
                if a == b or b == c or a == c:
                    deg += 1
                    continue
                used.update((a, b, c))
                va, vb, vc = pool[a], pool[b], pool[c]
                m = max(tm._dist(va, vb), tm._dist(vb, vc), tm._dist(vc, va))
                maxedge = max(maxedge, m)
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
                best = (key, recw, is_u8, pos, pool, maxedge, small, big, deg, len(edge_share), coverage)
    if best is None:
        return None
    key, recw, is_u8, pos, pool, maxedge, small, big, deg, nedges, cov = best
    nreal = small + big
    if key[0] > max(2, 0.02 * nedges) or key[1] > max(2, 0.02 * nreal) or \
            (nreal and -key[2] < 0.6):
        return None
    return (recw, 1 if is_u8 else 2, len(pool), maxedge / 64.0, nreal, big, cov)


def main():
    rows = []
    for level_dir in sorted(glob.glob(os.path.join(DATA, "*"))):
        if not os.path.isdir(level_dir):
            continue
        for f in sorted(glob.glob(os.path.join(level_dir, "*.trb"))):
            if tm.w0c0m_count(f) < 2:
                continue
            d, sect, sizes = tm.parse_tsfb(f)
            recs = tm.mesh_records_symb(f, d, sect, sizes)
            for k in sorted(recs):
                if k + 1 >= len(sizes):
                    continue
                rec = recs[k]
                if not (0.01 <= rec["radius"] < 200):
                    continue
                flag = struct.unpack_from(">I", d, sect + rec["offset"] + 0x30)[0]
                r = analyze(d, sect, sizes, recs, k)
                if r is None:
                    continue
                recw, posw, poolsz, maxedge, nreal, big, cov = r
                rows.append((maxedge, os.path.basename(f), k, flag, recw, posw,
                             poolsz, round(rec["radius"], 2), nreal, big,
                             round(cov, 3), maxedge / max(0.01, rec["radius"])))

    rows.sort(reverse=True)
    print("top 25 giant-triangle meshes (maxedge_world, file, k, flag, recw,"
          " posw, pool, radius, nreal, nbig, cov, edge/rad):")
    for r in rows[:25]:
        print("  %6.1f  %-38s k=%-4d %08X recw=%d posw=%d pool=%4d rad=%6.2f"
              " nreal=%4d big=%3d cov=%.2f edge/rad=%.1f"
              % (r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10], r[11]))
    print()
    print("meshes with maxedge > 25 world units: %d" %
          sum(1 for r in rows if r[0] > 25))
    print("meshes with maxedge > 10: %d" % sum(1 for r in rows if r[0] > 10))


if __name__ == "__main__":
    main()
