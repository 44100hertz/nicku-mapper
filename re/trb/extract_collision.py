#!/usr/bin/env python3
"""Extract collision meshes from a Nicktoons Unite TRB file.

⚠️⚠️⚠️  RETRACTED READING — see asset-extract/docs/collision-runtime.md  ⚠️⚠️⚠️
This script scans records with flag==0x06020202 at +0x10 and center at
+0x14, but the REAL record layout (verified against file bytes and the
runtime model) is: center@+0x00, flag@+0x30, C-block@+0x20/+0x24,
count@+0x2c. Reading at +0x10/+0x14 means the scan lands 0x20 bytes INTO
the 52-byte records: the "flag" is the real flag, but the "center" and
pools/strips come from the NEXT record. The mined "collision meshes" are
therefore the SAME W0C0M display records (mesh k's output = visual mesh
k+1's data), not a separate collision format. The runtime collision model
(pool + u16 triangle table + quantized AABB tree + per-group layer flags)
is built from these same display records by vmtext code; the DOL's OpCODE
library is dead code (strings only).

Original (incorrect) claim below, kept for history:

Format decoded from the game's own byte-consumer (decomp of the TTRB chunk
loader FUN_7f297178 + the RELC relocator, verified LIVE against the emulator
via breakpoints on the parser and the relocation store):

  File layout (big-endian u32s; 4CCs stored as BE of the loader's LE constant,
  i.e. the bytes are the reversed ASCII tag):
    [0x00] "TSFB" magic + u32 size (file size - 8)
    [0x08] "TRBF" marker (u32 0x46425254)
    then sections: [tag u32][size u32][payload], tags (u32 values):
      HDRX 0x58524448 : chunk descriptors
        payload = [u32 0x00010001][u32 count][records x 0x10]
        record  = [align u32][size u32][0 u32][extra u32]
        chunk i data = SECC payload + sum(sizes[0..i-1])
        size: chunk 0 uses [size]; chunks 1+ use [extra] * 0x10
        (verified: chunk0=0x754+0x27fe0 -> chunk1=0x28734, chunk1=+0x28*0x10
         -> 0x289b4 = the pos pool; the RELC targets exactly these bases)
      SECC 0x43434553 : the chunk data blob
      RELC 0x434c4552 : relocations
        payload = [u32 count][entries x 8: h1 u16, h2 u16, off u32]
        relocation: *(chunk[h2].data + off) += chunk[h1].data
        (caught live at 0x7f297594: 0x70 + 0x809af820 = 0x809af890)
      SYMB 0x424d5953 : symbols
        payload = [u32 count][entries x 12]
        entry = [chunk u16][name-off u16][hash u16][offset u32]
        name = the NUL-terminated string at the symbol blob + name-off
        the "Collision" symbol: data @ chunk[chunk].base + offset

  Collision mesh record (52 bytes, at the Collision symbol):
    [0x00] aux/sub-record offset   (RELC h2=chunk0)
    [0x04] pool offset             (into the pool region)
    [0x08] tdata offset            (RELC h2=chunk0; strip near here)
    [0x0c] u32 count
    [0x10] flags (0x06020202)
    [0x14] center x,y,z + radius (4 x f32)
    [0x24] pool off 0  (RELC h2=pool-chunk; == 0)
    [0x28] pool off 1  (RELC h2=pool-chunk; stride, e.g. 0xA0)
    [0x2c] pool off 2  (RELC h2=pool-chunk)
    [0x30] u32 (0)

  Pools = s16 blocks. pos pool at pool-chunk base + [0x24]; nrm/tex at
  +[0x28]/+[0x2c]. World scale = s16/64 happens only in the query code;
  the loader copies the s16s byte-for-byte (identity transform, verified
  against the s02 savestate RAM: file 0x289b4 == runtime 0x812CB7E0).

  Strip = [0x98][u16 count][(pos,nrm,tex) u8 x count] (the "0x98 form"),
  byte-identical to the runtime.

Usage: python3 extract_collision.py <file.trb> <out.json>
"""
import struct, sys, json

def u16(d, o): return struct.unpack_from(">H", d, o)[0]
def u32(d, o): return struct.unpack_from(">I", d, o)[0]
def f32(d, o): return struct.unpack_from(">f", d, o)[0]

FLAG = 0x06020202

# ---------------------------------------------------------------------
# TTRB section parse
# ---------------------------------------------------------------------
def parse_sections(d):
    """Return list of (tag, size, payload_off)."""
    assert d[:4] == b"TSFB", "not a TSFB file"
    sections = []
    o = 0xc  # [0x08] is the bare "TRBF" marker (no size)
    eof = len(d)
    while o + 8 <= eof:
        tag, size = u32(d, o), u32(d, o + 4)
        if tag not in (0x58524448, 0x54434553, 0x434c4552, 0x424d5953,
                       0x44414548, 0x4d524f46, 0x54534642, 0x43434553):
            break
        sections.append((tag, size, o + 8))
        o = o + 8 + size
    return sections

def get_section(sections, tag):
    for t, sz, off in sections:
        if t == tag:
            return sz, off
    return None

def chunk_bases(d, sections):
    """Chunk data bases (file offsets) from the HDRX descriptors."""
    h = get_section(sections, 0x58524448)
    if not h:
        return None
    _, hdrx = h
    count = u32(d, hdrx + 4)
    secc = get_section(sections, 0x54434553)
    if not secc:
        return None
    _, secc_payload = secc
    bases = []
    acc = secc_payload
    for i in range(count):
        rec = hdrx + 8 + 0x10 * i
        size = u32(d, rec + 4)
        if size == 0:
            size = u32(d, rec + 0xc) * 0x10
        bases.append(acc)
        acc += size
    return bases

def parse_relc(d, sections):
    r = get_section(sections, 0x434c4552)
    if not r:
        return []
    _, off = r
    cnt = u32(d, off)
    out = []
    for i in range(cnt):
        e = off + 4 + 8 * i
        out.append((u16(d, e), u16(d, e + 2), u32(d, e + 4)))
    return out

def find_collision(d, sections, bases):
    """Locate the Collision symbol's data (file offset)."""
    s = get_section(sections, 0x424d5953)
    if not s:
        return None
    _, symb = s
    # the symbol blob: names live right after the entry table
    cnt = u32(d, symb)
    blob_start = symb + 4 + 12 * cnt
    for i in range(cnt):
        e = symb + 4 + 12 * i
        chunk_idx = u16(d, e)
        noff = u16(d, e + 2)
        off = u32(d, e + 8)
        name = d[blob_start + noff:].split(b"\x00", 1)[0]
        if name == b"Collision":
            return bases[chunk_idx] + off
    return None

# ---------------------------------------------------------------------
# mesh extraction
# ---------------------------------------------------------------------
def main():
    path, out_path = sys.argv[1], sys.argv[2]
    d = open(path, "rb").read()
    sections = parse_sections(d)
    for tag, sz, off in sections:
        name = {0x58524448: "HDRX", 0x43434553: "SECC", 0x434c4552: "RELC",
                0x424d5953: "SYMB", 0x44414548: "HEAD", 0x4d524f46: "FORM"}.get(tag, hex(tag))
        print(f"section {name} @ 0x{off:x} size 0x{sz:x}")
    bases = chunk_bases(d, sections)
    if not bases:
        print("!! no HDRX/SECC"); return
    print(f"chunks: {len(bases)} data 0x{bases[0]:x}..0x{bases[-1]:x}")
    relc = parse_relc(d, sections)
    print(f"RELC entries: {len(relc)}")
    col = find_collision(d, sections, bases)
    if col is None:
        print("!! Collision symbol not found"); return
    print(f"Collision @ 0x{col:x}")

    # RELC lookup: off -> (h1, h2) for the coll chunk (h2=0 chunk0 pointers)
    relc_by_off = {}
    for h1, h2, off in relc:
        relc_by_off.setdefault(off, []).append((h1, h2))

    # ---- enumerate mesh records: 52-byte blocks with the flag signature ----
    region_end = min(len(d), col + 0x6000)
    recs = []
    p = col
    while p + 0x34 <= region_end:
        flags = u32(d, p + 0x10)
        cx, cy, cz, rad = (f32(d, p + 0x14), f32(d, p + 0x18),
                           f32(d, p + 0x1c), f32(d, p + 0x20))
        po0, po1, po2 = u32(d, p + 0x24), u32(d, p + 0x28), u32(d, p + 0x2c)
        sane = (flags == FLAG and abs(cx) < 5000 and abs(cy) < 5000 and
                abs(cz) < 5000 and 0 < rad < 5000 and
                po0 == 0 and 0 < po1 <= 0x8000 and 0 < po2 <= 0x8000)
        if sane:
            recs.append(dict(rec=p, ctr=(cx, cy, cz, rad),
                             pooloff=u32(d, p + 0x04), tdata=u32(d, p + 0x08),
                             cnt=u32(d, p + 0x0c), po=(po0, po1, po2)))
            p += 0x34
        else:
            p += 1
    print(f"mesh records found: {len(recs)}")

    # ---- pool chunk base: from the RELC entry for the record's [0x24] ----
    # The [0x24] field is relocated against the pool chunk: value += chunk[h2].base
    # h2 = index of the pool chunk in the HDRX table. We take the h2 seen for
    # the first record's +0x24 field.
    pool_chunk = None
    if recs:
        off = recs[0]["rec"] - bases[0] + 0x24
        for h1, h2 in relc_by_off.get(off, []):
            if h2 != 0 and h2 < len(bases):
                pool_chunk = h2
                break
    print(f"pool chunk: {pool_chunk} @ 0x{bases[pool_chunk]:x}" if pool_chunk is not None
          else "pool chunk: unknown")

    def pool_verts(off, size):
        out = []
        for i in range(0, size - 5, 6):
            if off + i + 6 > len(d):
                break
            x, y, z = struct.unpack_from(">hhh", d, off + i)
            out.append((x, y, z))
        return out

    def center_of(pool):
        nz = [r for r in pool if r != (0, 0, 0)]
        if not nz:
            return None
        xs = [r[0] for r in nz]; ys = [r[1] for r in nz]; zs = [r[2] for r in nz]
        return ((min(xs) + max(xs)) / 2 / 64, (min(ys) + max(ys)) / 2 / 64,
                (min(zs) + max(zs)) / 2 / 64)

    parts = []
    ok = reject = 0
    for m in recs:
        rec_off = m["rec"] - bases[0]
        # strip: scan for [0x98][u16 n] starting at the tdata pointer
        strip_off = bases[0] + m["tdata"]
        best_strip = None
        for cand in range(strip_off, min(strip_off + 0x1000, len(d) - 4)):
            if d[cand] == 0x98:
                n = u16(d, cand + 1)
                if 0 < n < 5000 and cand + 4 + n * 3 <= len(d):
                    best_strip = (cand, n)
                    break
        if not best_strip:
            print(f"  rec@{m['rec']:#x}: REJECT (strip not found)"); reject += 1
            continue
        cand, n = best_strip
        # this record's pool chunk: from the RELC entry for its [0x24] field
        h2 = None
        for h1, hh2 in relc_by_off.get(rec_off + 0x24, []):
            if hh2 != 0 and hh2 < len(bases):
                h2 = hh2
                break
        if h2 is None:
            print(f"  rec@{m['rec']:#x}: REJECT (no RELC pool chunk)"); reject += 1
            continue
        pbase = bases[h2]
        pos_off = pbase + m["po"][0]
        # pos pool size: stride to the next pool (the record's [0x28] field)
        psize = m["po"][1] if m["po"][1] else 0xA0
        pool = pool_verts(pos_off, psize)
        c = center_of(pool)
        cerr = (abs(c[0] - m["ctr"][0]) + abs(c[1] - m["ctr"][1]) +
                abs(c[2] - m["ctr"][2])) if c else 9
        if cerr > 0.05:
            print(f"  rec@{m['rec']:#x}: REJECT (center mismatch {cerr:.3f})"); reject += 1
            continue
        # strip form: u8 triples (posIdx, nrmIdx, texIdx) x3 for pools < 256
        # verts, or u16 pairs (posIdx, nrmIdx) x4 for pools >= 256 (the posIdx
        # is u16 then). Verified against the runtime alloc sizes (+0x28 =
        # 3 + n*stride rounded to 0x20): all 101 records, 0 conflicts.
        u16form = len(pool) >= 256
        # index range check: the strip's posIdx column indexes the pos pool
        if u16form:
            maxidx = max(struct.unpack_from(">H", d, cand + 3 + 4 * i)[0]
                         for i in range(n))
        else:
            maxidx = max(d[cand + 3 + 3 * i] for i in range(n))
        if maxidx >= len(pool):
            print(f"  rec@{m['rec']:#x}: REJECT (posIdx {maxidx} >= pool {len(pool)})"); reject += 1
            continue
        # faces: the posIdx column. Triangles are CONSECUTIVE triples (a real
        # strip, degenerate restarts); runtime-confirmed: the query's converted
        # table reads 3 u16s per triangle, and the memdump faces == posIdx
        # column (PrisColwall: 3,2,4,4,17,17,16,15,13,13,...).
        if u16form:
            faces = [struct.unpack_from(">H", d, cand + 3 + 4 * i)[0]
                     for i in range(n)]
        else:
            faces = [d[cand + 3 + 3 * i] for i in range(n)]
        verts = []
        for x, y, z in pool:
            verts += [x, y, z]  # viewer convention: (x, y, z) raw s16s — the
            # viewer maps pos=(v0, v2, -v1)/div so s16 z = world-up, s16 y =
            # world-depth. (MEM-COLL ground truth stores exactly (x, y, z).)
        parts.append({"file": f"COLL {m['rec']:#x}", "meshCount": 1, "meshes": [{
            "k": len(parts), "name": f"COLL-{len(parts)}", "flag": hex(FLAG),
            "center": [m['ctr'][0], m['ctr'][1], m['ctr'][2]], "radius": m['ctr'][3],
            "count": len(pool), "verts": verts, "faces": faces}]})
        ok += 1
        print(f"  rec@{m['rec']:#x}: OK ctr={[round(v,2) for v in m['ctr']]} strip={cand:#x} n={n} poolverts={len(pool)}")

    print(f"\n{ok} meshes OK, {reject} rejected")
    out = {"format": "mesh-v2", "level": "coll-extract", "entityFile": "",
           "div": 64, "yDown": True, "collFormat": "ttrb-identity", "parts": parts}
    json.dump(out, open(out_path, "w"))
    print(f"wrote {out_path}")

if __name__ == "__main__":
    main()
