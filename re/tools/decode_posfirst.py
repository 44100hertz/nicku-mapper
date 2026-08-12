#!/usr/bin/env python3
"""DEFINITIVE analytic decode test.

Structure (verified this session + notes):
  * the 0x98 index block: [0x98][u16 count][count x recw-byte records]
  * each record's FIRST field is the position index (pos-first; po=0)
  * pos width: u8 iff pos pool <= 256, else u16   (GX_INDEX8/16; PROVEN 100%)
  * the pos pool = the chunk's first max(posIdx)+1 triples (record's own
    delimiter), validated >= 50% inside the record's bounding sphere
  * recw: try 3..12, keep the cleanest manifold decode (pos-first only —
    no misaligned reads, which were gate-passing false positives)

For each mesh we report the winning recw and whether the pool-width rule
holds. The per-flag recw distribution should be constant if recw is a
property of the format/flag, not of the data.
"""
import collections, glob, os, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trb_mesh as tm

DATA_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "..", "nicku-ntsc", "P-GNOE", "files", "Data")


def s16(v):
    return v if v < 0x8000 else v - 0x10000


def decode(d, sect, sizes, recs, k):
    rec = recs[k]
    boff = struct.unpack_from(">I", d, sect + rec["offset"] + 0x20)[0]
    bsz = struct.unpack_from(">I", d, sect + rec["offset"] + 0x24)[0]
    seg = d[sect + boff:sect + boff + bsz]
    if len(seg) < 5 or seg[0] != 0x98:
        return None
    cnt = struct.unpack_from(">H", seg, 1)[0]
    if not (2 <= cnt <= 100000):
        return None
    chunk = tm.chunk_of(d, sect, sizes, k + 1)
    radius_raw = rec["radius"] * 64 * 2.2
    cx, cz, cy = rec["center"]
    rr = rec["radius"] * 1.25

    results = []
    for recw in range(3, 13):
        if 3 + cnt * recw > len(seg):
            continue
        for is_u8 in (True, False):
            if is_u8:
                pos = [seg[3 + i * recw] for i in range(cnt)]
            else:
                pos = [struct.unpack_from(">H", seg, 3 + i * recw)[0]
                       for i in range(cnt)]
            mx = max(pos)
            if (mx + 1) * 6 > len(chunk):
                continue
            # pool = first mx+1 triples (the record's own delimiter)
            pool = []
            ok = True
            for j in range(mx + 1):
                x, z, y = struct.unpack_from(">HHH", chunk, j * 6)
                t = (s16(x), s16(z), s16(y))
                if max(map(abs, t)) > 12000:
                    ok = False
                    break
                pool.append(t)
            if not ok:
                continue
            insphere = sum(1 for p in pool if
                           ((p[0] / 64 - cx) ** 2 + (p[1] / 64 - cz) ** 2 +
                            (p[2] / 64 - cy) ** 2) ** 0.5 < rr)
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
                m = max(tm._dist(va, vb), tm._dist(vb, vc), tm._dist(vc, va))
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
            results.append((key, recw, is_u8, pos, pool))
            if over == 0 and big == 0 and coverage >= 0.999:
                return recw, is_u8, pos, pool
    if not results:
        return None
    results.sort(key=lambda r: r[0])
    key, recw, is_u8, pos, pool = results[0]
    over, big = key[0], key[1]
    nreal = key[3] + key[1]
    nedges = key[4]
    if over > max(2, 0.02 * nedges) or big > max(2, 0.02 * nreal) or \
            (nreal and -key[2] < 0.6):
        return None
    return recw, is_u8, pos, pool


def main():
    files = []
    for level_dir in sorted(glob.glob(os.path.join(DATA_ROOT, "*"))):
        if not os.path.isdir(level_dir):
            continue
        for f in sorted(glob.glob(os.path.join(level_dir, "*.trb"))):
            if tm.w0c0m_count(f) >= 2:
                files.append(f)
    flag_recw = collections.Counter()
    flag_fail = collections.Counter()
    rule_viol = 0
    n = 0
    for f in files:
        d, sect, sizes = tm.parse_tsfb(f)
        recs = tm.mesh_records_symb(f, d, sect, sizes)
        for k in sorted(recs):
            if k + 1 >= len(sizes):
                continue
            rec = recs[k]
            if not (0.01 <= rec["radius"] < 200):
                continue
            n += 1
            flag = struct.unpack_from(">I", d, sect + rec["offset"] + 0x30)[0]
            r = decode(d, sect, sizes, recs, k)
            if r is None:
                flag_fail[flag] += 1
                continue
            recw, is_u8, pos, pool = r
            flag_recv = flag_recw[(flag, recw, 1 if is_u8 else 2)]
            flag_recw[(flag, recw, 1 if is_u8 else 2)] += 1
            if (is_u8 == (len(pool) > 256)):
                rule_viol += 1
    print("meshes: %d, decoded: %d (%.1f%%), undecoded: %d" %
          (n, sum(flag_recw.values()),
           100.0 * sum(flag_recw.values()) / n, n - sum(flag_recw.values())))
    print("pool-width-rule violations: %d" % rule_viol)
    print()
    print("per-flag (recw, posw) -> count:")
    for (fl, recw, pw), c in sorted(flag_recw.items()):
        print("   0x%08X  recw=%2d posw=%d  x%d" % (fl, recw, pw, c))
    print()
    print("undecoded per flag:")
    for fl, c in sorted(flag_fail.items()):
        print("   0x%08X  x%d" % (fl, c))


if __name__ == "__main__":
    main()
