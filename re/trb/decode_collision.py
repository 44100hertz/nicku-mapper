#!/usr/bin/env python3
"""Decode the 'Collision' symbol of a Nicktoons Unite level TRB using the
OpenBarnyard TTMDBase layout + TTRB relocations. Tests the hypothesis that
the game uses the exact Barnyard collision format.

Run:  python3 decode_collision.py <file.trb>
"""
import struct, sys

def u16(d, o): return struct.unpack_from(">H", d, o)[0]
def u32(d, o): return struct.unpack_from(">I", d, o)[0]
def i32(d, o): return struct.unpack_from(">i", d, o)[0]

def main():
    path = sys.argv[1]
    d = open(path, "rb").read()

    # ---- chunks ----
    n_chunks = u32(d, 0x18)
    sizes = [u32(d, 0x20 + 16 * i) for i in range(n_chunks)]
    bases = []
    acc = 0x594
    for s in sizes:
        bases.append(acc)
        acc += s
    print(f"chunks: {n_chunks} data 0x594..{hex(acc)}  sizes[0]={sizes[0]}")

    # ---- SYMB (validated layout from dump_symbols.py) ----
    eof = len(d)
    while eof > 0 and d[eof - 1] == 0:
        eof -= 1
    # locate name blob + symb base by re-running the validated search
    best = None
    for blob_start in range(0x34000, eof):
        for count in range(1, 400):
            base = blob_start - 4 - 12 * count
            if base < 0 or u32(d, base) != count:
                continue
            ok = 0
            for i in range(count):
                e = base + 4 + 12 * i
                hdrx, noff, pad, nhash, doff = u16(d, e), u16(d, e + 2), u16(d, e + 4), struct.unpack_from(">h", d, e + 6)[0], u32(d, e + 8)
                if hdrx < n_chunks and 0 <= noff < eof - blob_start and doff < sizes[hdrx]:
                    nb = d[blob_start + noff:eof].split(b"\x00", 1)[0]
                    if nb and all(32 <= c < 127 for c in nb):
                        h = 0
                        for ch in nb:
                            h = ((h * 0x1f) + ch) & 0xFFFF
                        if h == (nhash & 0xFFFF):
                            ok += 1
            if ok > 0 and (best is None or ok > best[0]):
                best = (ok, blob_start, count, base)
    if best is None:
        print("!! SYMB not found"); return
    _, blob_start, count, symb_base = best
    print(f"SYMB base 0x{symb_base:x} count={count} names@0x{blob_start:x}")

    # ---- RELC: scan for "CLER" ----
    relc_at = d.find(b"CLER")
    if relc_at < 0:
        print("!! RELC not found"); return
    reloc_count = u32(d, relc_at + 8)
    relocs = []
    for i in range(reloc_count):
        o = relc_at + 12 + 8 * i
        h1, h2, off = u16(d, o), u16(d, o + 2), u32(d, o + 4)
        relocs.append((h1, h2, off))
    print(f"RELC @0x{relc_at:x} count={reloc_count}  first: {relocs[:6]}")

    def sym_addr(name):
        for i in range(count):
            e = symb_base + 4 + 12 * i
            noff = u16(d, e + 2)
            nb = d[blob_start + noff:eof].split(b"\x00", 1)[0]
            if nb == name.encode():
                return u16(d, e), u32(d, e + 8)  # hdrx, data offset
        return None

    # ---- decode a symbol with relocations ----
    def sym(name):
        r = sym_addr(name)
        if not r: return None
        hdrx, doff = r
        base = bases[hdrx]
        reloc_set = {off for (_, _, off) in relocs if off >= doff}
        return base, doff, reloc_set

    # ---- Collision ----
    r = sym_addr("Collision")
    print("\n=== Collision symbol: chunk %d +0x%x (file 0x%x) ===" % (r[0], r[1], bases[r[0]] + r[1]))
    cb = bases[r[0]]  # section base (chunk 0)
    off = r[1]
    data_start = cb + off
    reloc_set = {x[2] for x in relocs if x[0] == 0 and x[1] == 0}

    def rd(rel_off, label=""):
        """read u32 at chunk-relative rel_off; show relocation"""
        v = u32(d, cb + rel_off)
        rel = "PTR->0x%x" % v if rel_off in reloc_set else ""
        print(f"   +0x{rel_off:04x} (file 0x{cb+rel_off:04x}): {v:#010x} {rel} {label}")
        return v

    print("\n-- raw Collision data --")
    for i in range(0, 16, 4):
        rd(off + i)
    print("\n-- as Barnyard CollisionHeader { i32 m_iNumMeshes; CollisionMesh* m_pMeshes } --")
    n_meshes = i32(d, data_start)
    p_meshes_raw = u32(d, data_start + 4)
    print("   m_iNumMeshes =", n_meshes, " m_pMeshes raw =", hex(p_meshes_raw))
    if p_meshes_raw in reloc_set:
        p_meshes = p_meshes_raw
        print(f"   m_pMeshes is RELOCATED -> section0 + 0x{p_meshes:x} (file 0x{cb+p_meshes:x})")
    else:
        p_meshes = p_meshes_raw
        print("   m_pMeshes NOT relocated (raw value used)")

    # try to walk meshes
    def mesh_at(rel):
        print(f"\n-- CollisionMesh @ +0x{rel:x} (file 0x{cb+rel:x}) --")
        bone = i32(d, cb + rel + 0)
        pv = u32(d, cb + rel + 4)
        nv = u32(d, cb + rel + 8)
        pi = u32(d, cb + rel + 12)
        ni = u32(d, cb + rel + 16)
        nct = u32(d, cb + rel + 20)
        pcg = u32(d, cb + rel + 24)
        rels = [pv, pi, pcg]
        print(f"   m_iBoneID={bone}")
        for nm, v in [("m_pVertices", pv), ("m_uiNumVertices", nv), ("m_pIndices", pi), ("m_uiNumIndices", ni), ("m_uiNumCollTypes", nct), ("m_pCollGroups", pcg)]:
            print(f"   {nm}: {v:#x}{' [RELOC]' if v in reloc_set else ''}")
        return dict(bone=bone, pv=pv, nv=nv, pi=pi, ni=ni, nct=nct, pcg=pcg)

    if 0 < n_meshes < 100 and p_meshes + 28 * n_meshes < sizes[0]:
        for m in range(n_meshes):
            mesh_at(p_meshes + 28 * m)
    else:
        # try alternative interpretations
        print("\n-- alternative: u32 pairs in collision data --")
        for i in range(0, 40, 4):
            rd(off + i)

    # ---- mesh records at relocated slots ----
    print("\n=== mesh record pointer slots (RELC 0x374c..0x38ac) ===")
    slot_offsets = sorted(o for o in reloc_set if 0x3700 <= o <= 0x3c00)
    print("slots:", len(slot_offsets), [hex(o) for o in slot_offsets[:12]], "...")
    for s in slot_offsets[:6]:
        v = u32(d, cb + s)
        print(f"   slot +0x{s:x}: -> +0x{v:x} (file 0x{cb+v:x})")

if __name__ == "__main__":
    main()
