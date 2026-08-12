"""TSFB container (TRB/TTL) walker for Nicktoons Unite! (GameCube).

Prints the container header, HDRX chunk table, SECT region bounds, RELC
entries and the SYMB name table. See docs/trb-format-notes.md for the
format write-up.

Usage: python3 -m nicku.ttrb <file.trb>
"""
import struct
import sys


def u16(b, o):
    return struct.unpack_from('>H', b, o)[0]


def u32(b, o):
    return struct.unpack_from('>I', b, o)[0]


def s16(b, o):
    return struct.unpack_from('>h', b, o)[0]


def main(path):
    d = open(path, 'rb').read()
    print(f"file: {path}  size={len(d)} (0x{len(d):x})")
    assert d[0:4] == b'TSFB', f"not a TSFB container: {d[0:4]!r}"
    size_field = u32(d, 4)
    print(f"magic TSFB  size_field=0x{size_field:x} (+8 = 0x{size_field+8:x})")
    assert d[8:12] == b'FBRT', d[8:12]
    assert d[12:16] == b'XRDH', d[12:16]
    hdrx_size = u32(d, 16)
    flags = u32(d, 20)
    count = u32(d, 24)
    print(f"HDRX size=0x{hdrx_size:x} flags=0x{flags:x} count={count}")
    sizes = [u32(d, 32 + i * 16) for i in range(count)]
    print("chunk sizes:", [hex(s) for s in sizes])
    print(f"sum of chunk sizes: 0x{sum(sizes):x}")
    sect_off = hdrx_size + 20
    assert d[sect_off:sect_off + 4] == b'TCES', d[sect_off:sect_off + 4]
    sect_size = u32(d, sect_off + 4)
    sect = d[sect_off + 8: sect_off + 8 + sect_size]
    print(f"SECT @0x{sect_off+8:x} size=0x{sect_size:x}")

    relc_off = sect_off + 8 + sect_size
    if d[relc_off:relc_off + 4] == b'CLER':
        relc_size = u32(d, relc_off + 4)
        print(f"RELC @0x{relc_off:x} size=0x{relc_size:x}")
        relc = d[relc_off + 8: relc_off + 8 + relc_size]
        n = min(10, len(relc) // 8)
        print("  RELC first entries (offset, 0):",
              [hex(u32(relc, i * 8)) for i in range(n)])
        symb_off = relc_off + 8 + relc_size
    else:
        symb_off = relc_off
    assert d[symb_off:symb_off + 4] == b'BMYS', d[symb_off:symb_off + 4]
    symb_size = u32(d, symb_off + 4)
    nnames = u32(d, symb_off + 8)
    print(f"SYMB @0x{symb_off:x} size=0x{symb_size:x} names={nnames}")
    names_base = symb_off + 12 + nnames * 12
    for i in range(nnames):
        e = symb_off + 12 + i * 12
        ident = s16(d, e)
        name_off = s16(d, e + 2)
        x = u32(d, e + 4)
        y = u32(d, e + 8)
        nb = names_base + name_off
        name = d[nb: d.find(b'\x00', nb)].decode('ascii', 'replace')
        print(f"  [{i:3d}] ID={ident} nameOff={name_off:5d} X=0x{x:06x} Y=0x{y:06x}  {name}")

    print("\nSECT head (128 bytes):")
    for o in range(0, min(128, len(sect)), 16):
        row = sect[o:o + 16]
        print(f"  {o:06x}: {row.hex(' ')}")


if __name__ == '__main__':
    main(sys.argv[1])
