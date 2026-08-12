#!/usr/bin/env python3
"""trb_unpack.py — clean TSFB/TRB container unpacker for Nicktoons Unite! (GC).

Walks the Toshi TSFB container of a level .trb file and writes:
  <out>/<file>/chunkNN.bin     every HDRX section (chunk) extracted raw
  <out>/<file>/manifest.txt    human-readable inventory: container header,
                               chunk table, RELC pointers, SYMB names, and a
                               decoded dump of the per-mesh 52-byte records
                               plus C-block summaries and material records.

Usage:
    python3 trb_unpack.py <file.trb> [outdir]

Verified structure (see docs/trb-format-notes.md):
  TSFB -> HDRX (chunk table; sizes tile SECT exactly) -> SECT -> RELC -> SYMB
  - HDRX entry: u32 size + 12 zero bytes
  - RELC entry: (u32 offset, u32 section); loader does *ptr += base(section)
  - SYMB entry: u16 hdrx, u16 nameOff, u16 pad, i16 nameHash, u32 dataOff
  - Level SECT: header, material records, object table, 86x 52-byte mesh
    records (W0C0M0..85), C-blocks ([0x98][u16 F][F x u8 triples])
"""
import os
import struct
import sys

MAGIC = "TSFB"


def u16(b, o):
    return struct.unpack_from(">H", b, o)[0]


def u32(b, o):
    return struct.unpack_from(">I", b, o)[0]


def f32(b, o):
    return struct.unpack_from(">f", b, o)[0]


def parse_container(path):
    d = open(path, "rb").read()
    if d[:4] != MAGIC.encode():
        raise ValueError("not a TSFB container: %r" % d[:4])
    hdrx_size = u32(d, 16)
    flags = u32(d, 20)
    count = u32(d, 24)
    sizes = [u32(d, 32 + i * 16) for i in range(count)]
    sect_start = hdrx_size + 20
    if d[sect_start : sect_start + 4] != b"TCES":
        raise ValueError("no SECT after HDRX")
    sect_size = u32(d, sect_start + 4)
    sect = d[sect_start + 8 : sect_start + 8 + sect_size]

    # RELC
    relc = []
    p = sect_start + 8 + sect_size
    if d[p : p + 4] == b"CLER":
        rs = u32(d, p + 4)
        rb = d[p + 8 : p + 8 + rs]
        for i in range(len(rb) // 8):
            relc.append(struct.unpack_from(">II", rb, i * 8)[0:2])
        p += 8 + rs

    # SYMB
    symbs = []
    if d[p : p + 4] == b"BMYS":
        ss = u32(d, p + 4)
        nn = u32(d, p + 8)
        names_base = p + 12 + nn * 12
        for i in range(nn):
            e = p + 12 + i * 12
            hdrx, nameoff = u16(d, e), u16(d, e + 2)
            nb = names_base + nameoff
            name = d[nb : d.find(b"\0", nb)].decode("latin1")
            symbs.append((hdrx, nameoff, u32(d, e + 4), u32(d, e + 8), name))
        p += 8 + ss
    return {
        "size": len(d),
        "hdrx_size": hdrx_size,
        "flags": flags,
        "count": count,
        "sizes": sizes,
        "sect": sect,
        "sect_start": sect_start + 8,
        "relc": relc,
        "symbs": symbs,
    }


def dump_mesh_records(sect, symbs, f):
    """Decode the 86 per-mesh 52-byte records + C-block summaries."""
    mesh_count = u32(sect, 0x0C)
    f.write("SECT header:\n")
    f.write("  +0x00 u32 %d\n" % u32(sect, 0x00))
    f.write("  +0x04 f32 %r\n" % f32(sect, 0x04))
    f.write("  +0x08 u32 %d\n" % u32(sect, 0x08))
    f.write("  +0x0C u32 %d   (mesh count)\n" % mesh_count)
    f.write("  +0x1C 4xf32 %r\n" % [f32(sect, 0x1C + 4 * i) for i in range(4)])
    f.write("  +0x2C u32 %d\n" % u32(sect, 0x2C))
    f.write("  +0x30 u32 %d   (record stride)\n" % u32(sect, 0x30))
    f.write("  +0x34 u32 0x%x\n" % u32(sect, 0x34))
    name = sect[0x40 : 0x4C].split(b"\0")[0]
    f.write("  name: %s\n" % name)

    # map symbs by data offset
    by_doff = {}
    for hdrx, no, hashv, doff, nm in symbs:
        by_doff.setdefault(doff, nm)

    f.write("\nper-mesh 52-byte records (W0C0Mk @ 0x3B08+0x34k):\n")
    f.write(
        "  %-3s %-10s %9s %9s %9s %9s %7s %7s %7s %7s %7s %6s %10s\n"
        % ("k", "name", "x0", "x1", "z0", "z1", "A", "B", "C", "D", "E", "F", "flag")
    )
    for k in range(min(mesh_count, 96)):
        rec = 0x3B08 + 0x34 * k
        fs = [f32(sect, rec + 4 * i) for i in range(4)]
        A, B = u32(sect, rec + 0x14), u32(sect, rec + 0x18)
        C, D, E = u32(sect, rec + 0x20), u32(sect, rec + 0x24), u32(sect, rec + 0x28)
        F, G = u32(sect, rec + 0x2C), u32(sect, rec + 0x30)
        nm = by_doff.get(rec, "W0C0M%d" % k)
        # C-block summary
        cb = ""
        if C + 3 + F * 3 <= len(sect):
            body = sect[C + 3 : C + 3 + F * 3]
            cb = " cb[amax=%d bmax=%d cmax=%d]" % (
                max(body[0::3]) if F else 0,
                max(body[1::3]) if F else 0,
                max(body[2::3]) if F else 0,
            )
        f.write(
            "  %-3d %-10s %9.3f %9.3f %9.3f %9.3f %7x %7x %7x %7x %7x %6x %10x%s\n"
            % (k, nm, fs[0], fs[1], fs[2], fs[3], A, B, C, D, E, F, G, cb)
        )


def dump_materials(sect, f):
    """Best-effort scan of chunk-0 material records (name + transforms)."""
    f.write("\nchunk-0 material records (len-prefixed names + 4x4 matrices):\n")
    off = 0x40
    shown = 0
    while off < 0x36C0 and shown < 24:
        ln = sect[off]
        if 1 <= ln <= 24:
            name = sect[off + 1 : off + 1 + ln]
            if all(32 <= b < 127 for b in name):
                f.write("  @0x%05x name(%d) %r\n" % (off, ln, name.decode()))
                shown += 1
                off += ln + 1 + 16
                continue
        off += 4
    if shown == 0:
        f.write("  (none found by heuristic)\n")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    path = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else "unpacked"
    c = parse_container(path)
    base = os.path.splitext(os.path.basename(path))[0]
    out = os.path.join(outdir, base)
    os.makedirs(out, exist_ok=True)

    # write chunks
    off = 0
    for i, sz in enumerate(c["sizes"]):
        with open(os.path.join(out, "chunk%02d.bin" % i), "wb") as fh:
            fh.write(c["sect"][off : off + sz])
        off += sz

    with open(os.path.join(out, "manifest.txt"), "w") as f:
        f.write("file: %s (%d bytes)\n" % (path, c["size"]))
        f.write("HDRX size 0x%x flags 0x%x count %d\n" % (c["hdrx_size"], c["flags"], c["count"]))
        f.write("chunk sizes: %s\n" % [hex(s) for s in c["sizes"]])
        f.write("sum: 0x%x (SECT size 0x%x)\n" % (sum(c["sizes"]), len(c["sect"])))
        f.write("\nRELC: %d entries (offset, section):\n" % len(c["relc"]))
        for i, (o, sec) in enumerate(c["relc"]):
            f.write("  %4d 0x%06x sec=%d\n" % (i, o, sec))
        f.write("\nSYMB: %d names:\n" % len(c["symbs"]))
        for hdrx, no, hashv, doff, nm in c["symbs"]:
            f.write("  %-16s hdrx=%d nameOff=%d hash=0x%04x dataOff=0x%06x\n"
                    % (nm, hdrx, no, hashv, doff))
        dump_mesh_records(c["sect"], c["symbs"], f)
        dump_materials(c["sect"], f)
    print("wrote %d chunks + manifest to %s" % (c["count"], out))


if __name__ == "__main__":
    main()
