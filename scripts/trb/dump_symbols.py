#!/usr/bin/env python3
"""Dump the TTRB symbol table for a Nicktoons Unite TRB.

Validates the OpenBarnyard TTRB layout against real GC data:
  SYMB data = [u32 count][TTRBSymbol x count][names]
  TTRBSymbol = { u16 HDRX, u16 NameOffset, u16 Padding, i16 NameHash, u32 DataOffset }
  GetSymbolAddress = section[HDRX].base + DataOffset
  GetSymbolName    = names_base + NameOffset

Usage: python3 dump_symbols.py <file.trb> [symbol_name]
"""
import struct, sys

def u16(d, o): return struct.unpack_from(">H", d, o)[0]
def u32(d, o): return struct.unpack_from(">I", d, o)[0]
def i16(d, o): return struct.unpack_from(">h", d, o)[0]

def hash_string(s):
    h = 0
    for ch in s.encode():
        h = ((h * 0x1f) + ch) & 0xFFFF
    return h

def main():
    path = sys.argv[1]
    want = sys.argv[2] if len(sys.argv) > 2 else None
    d = open(path, "rb").read()

    n_chunks = u32(d, 0x18)
    sizes = [u32(d, 0x20 + 16 * i) for i in range(n_chunks)]
    bases = []
    acc = 0x594
    for s in sizes:
        bases.append(acc)
        acc += s
    print(f"chunks: {n_chunks}  data 0x594..{hex(acc)}")

    # Find the packed name blob: [names separated by \0], ending near EOF.
    # Walk back from EOF over trailing NULs, then the last name.
    eof = len(d)
    while eof > 0 and d[eof - 1] == 0:
        eof -= 1
    # Search blob_start over a window; validate via entry hashes.
    best = None  # (score, blob_start, count, base, mode)
    for blob_start in range(0x34000, eof):
        for count in range(1, 400):
            base = blob_start - 4 - 12 * count
            if base < 0 or u32(d, base) != count:
                continue
            # quick scan of entries
            ok, bad = 0, 0
            for i in range(count):
                e = base + 4 + 12 * i
                hdrx, noff, pad, nhash, doff = u16(d, e), u16(d, e + 2), u16(d, e + 4), i16(d, e + 6), u32(d, e + 8)
                if hdrx < n_chunks and 0 <= noff < eof - blob_start and doff < sizes[hdrx]:
                    # name at blob_start+noff must be NUL-terminated printable, hash match
                    nb = d[blob_start + noff:eof].split(b"\x00", 1)[0]
                    if nb and all(32 <= c < 127 for c in nb) and hash_string(nb.decode()) == (nhash & 0xFFFF):
                        ok += 1
                        continue
                bad += 1
            if ok > 0 and (best is None or ok > best[0]):
                best = (ok, blob_start, count, base)
    if best is None:
        print("!! no valid SYMB layout found")
        return
    ok, blob_start, count, base = best
    print(f"SYMB base 0x{base:x} count={count} names@0x{blob_start:x} ({ok}/{count} entries validated)")

    def names():
        return d[blob_start:eof]

    def name_of(noff):
        nb = d[blob_start + noff:eof].split(b"\x00", 1)[0]
        return nb.decode(errors="replace")

    def sym(i):
        e = base + 4 + 12 * i
        hdrx, noff, pad, nhash, doff = u16(d, e), u16(d, e + 2), u16(d, e + 4), i16(d, e + 6), u32(d, e + 8)
        return hdrx, name_of(noff), doff

    if want:
        for i in range(count):
            hdrx, nm, doff = sym(i)
            if nm == want:
                print(f"\n{want}: chunk={hdrx} chunk_base=0x{bases[hdrx]:x} data_offset=0x{doff:x} -> file 0x{bases[hdrx]+doff:x}")
                return
        print("not found:", want)
    else:
        for i in range(count):
            hdrx, nm, doff = sym(i)
            print(f"  [{i:3d}] chunk {hdrx:2d} +0x{doff:6x}  {nm}")

if __name__ == "__main__":
    main()
