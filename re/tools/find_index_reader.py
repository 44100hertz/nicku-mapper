#!/usr/bin/env python3
"""find_index_reader.py — find code reading u16 triplets at +0/+2/+4 (index stream parser)."""
import struct
import sys

sys.path.insert(0, "/home/cyan/code/nickmapper-lua/asset-extract/tools")
from re_dol import load_sections
from capstone import Cs, CS_ARCH_PPC, CS_MODE_BIG_ENDIAN, CS_MODE_32

d, secs = load_sections()
md = Cs(CS_ARCH_PPC, CS_MODE_BIG_ENDIAN | CS_MODE_32)


def main():
    # scan for lhz rX, imm(rY) with imm in (0,2,4) on same rY within 8 insns
    hits = []
    for a, o, s in secs:
        blob = d[o:o + s]
        for i in range(0, len(blob) - 4, 4):
            ins = struct.unpack_from(">I", blob, i)[0]
            if ins >> 26 != 40:  # lhz
                continue
            imm = ins & 0xFFFF
            if imm > 0x20:
                continue
            # collect lhz on same base within next 12 insns with imm 0,2,4
            bases = {}
            for j in range(0, 12):
                if i + 4 * j + 4 > len(blob):
                    break
                nxt = struct.unpack_from(">I", blob, i + 4 * j)[0]
                if nxt >> 26 == 40:
                    r = (nxt >> 16) & 0x1F
                    im2 = nxt & 0xFFFF
                    bases.setdefault(r, set()).add(im2)
            for r, imms in bases.items():
                if {0, 2, 4}.issubset(imms):
                    hits.append(a + i)
                    break
    print("lhz +0/+2/+4 candidates:", len(hits))
    for h in hits[:30]:
        print("  0x%08x" % h)
        for ins in md.disasm(d[__import__("re_dol").addr_to_off(d, secs, h):][: 16 * 4], h):
            print("    %-26s %s" % (ins.mnemonic, ins.op_str))


if __name__ == "__main__":
    main()
