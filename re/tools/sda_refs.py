#!/usr/bin/env python3
"""sda_refs.py — find r13/r2 (SDA) based references in main.dol."""
import struct
import sys
from collections import Counter

sys.path.insert(0, "/home/cyan/code/nickmapper-lua/asset-extract/tools")
from re_dol import load_sections

d, secs = load_sections()
R13 = 0x8019D620
R2 = 0x801AD620


def main():
    targets = Counter()
    sample = {}
    for a, o, s in secs:
        blob = d[o:o + s]
        for i in range(0, len(blob) - 4, 4):
            ins = struct.unpack_from(">I", blob, i)[0]
            op = ins >> 26
            ra = (ins >> 16) & 0x1F
            imm = ins & 0xFFFF
            if ra == 13 and op in (14, 15, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43):
                if op == 15:
                    tgt = (R13 + imm) & 0xFFFFFFFF
                else:
                    tgt = (R13 + imm - 0x10000 * (imm >> 15)) & 0xFFFFFFFF
                targets[("r13", op, tgt)] += 1
                sample.setdefault(("r13", op, tgt), a + i)
            elif ra == 2 and op in (14, 32, 33, 34, 35, 40, 41):
                tgt = (R2 + imm - 0x10000 * (imm >> 15)) & 0xFFFFFFFF
                targets[("r2", op, tgt)] += 1
                sample.setdefault(("r2", op, tgt), a + i)

    print("distinct r13/r2 targets:", len(targets))
    for (reg, op, tgt), n in targets.most_common(80):
        print("%s op%-2d -> 0x%08x x%-3d code@0x%08x" % (reg, op, tgt, n, sample[(reg, op, tgt)]))


if __name__ == "__main__":
    main()
