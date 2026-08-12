#!/usr/bin/env python3
"""dolscan.py — targeted pattern scans of main.dol text sections."""
import struct
import sys

sys.path.insert(0, "/home/cyan/code/nickmapper-lua/asset-extract/tools")
from re_dol import load_sections

d, secs = load_sections()

# opcodes (bits 26-31)
LIS = 15
ORI = 24
ADDI = 14
MULLI = 7
CMPWI = 11
LFS = 48
LWZ = 32
LHA = 42
LFSX = 50  # lfsx
STWU = 37
MFLR = 18  # actually 18 is bclr/bcr; mflr is opcode 31 XO=339

MULLI_XO = 0x0B  # for opcode 7, XO in bits 1-10... mulli is opcode 7 with XO 0x0B embedded


def scan():
    print("=== mulli 0x34 / 0x1F / 0x2C / 0x30 / 0x38 / 0x40 ===")
    for a, o, s in secs:
        blob = d[o:o + s]
        for i in range(0, len(blob) - 4, 4):
            ins = struct.unpack_from(">I", blob, i)[0]
            op = ins >> 26
            if op == MULLI:
                rd = (ins >> 21) & 0x1F
                ra = (ins >> 16) & 0x1F
                imm = ins & 0xFFFF
                if imm > 0x8000:
                    imm -= 0x10000
                if imm in (0x34, 0x1F, 0x2C, 0x30, 0x38, 0x40, 0x56, 0x60, 0x44):
                    print("  0x%08x: mulli r%d,r%d,0x%x" % (a + i, rd, ra, imm & 0xFFFF))

    print("=== TSFB-magic compares (cmpwi imm near 0x54534642 / 0x42465354 / 'TSFB' bytes) ===")
    magics = {0x54534642, 0x42465354, 0x53465442, 0x46545346}
    for a, o, s in secs:
        blob = d[o:o + s]
        for i in range(0, len(blob) - 4, 4):
            ins = struct.unpack_from(">I", blob, i)[0]
            op = ins >> 26
            if op == CMPWI:
                crf = (ins >> 23) & 0x1C
                imm = ins & 0xFFFF
                if imm > 0x8000:
                    imm -= 0x10000
                if imm in magics or imm in (0x5453, 0x5346, 0x4642, 0x4254, 0x4654, 0x5342):
                    r = (ins >> 16) & 0x1F
                    print("  0x%08x: cmpwi r%d, 0x%x" % (a + i, r, imm & 0xFFFF))

    print("=== r13-relative refs to 0x80198518 (TSFLTSFB) — imm -0x5108 ===")
    for a, o, s in secs:
        blob = d[o:o + s]
        for i in range(0, len(blob) - 4, 4):
            ins = struct.unpack_from(">I", blob, i)[0]
            op = ins >> 26
            ra = (ins >> 16) & 0x1F
            imm = ins & 0xFFFF
            if imm > 0x8000:
                imm -= 0x10000
            if ra == 13 and imm in (-0x5108, -0x510C):
                rd = (ins >> 21) & 0x1F
                name = {14: "addi", 32: "lwz", 33: "lwzu", 36: "stw", 37: "stwu"}.get(op)
                if name:
                    print("  0x%08x: %s r%d,r13,0x%x" % (a + i, name, rd, imm & 0xFFFF))

    print("=== lfs f?,off(rX) runs: 4+ lfs with offsets 0,4,8,12 on same base within 40 insns ===")
    for a, o, s in secs:
        blob = d[o:o + s]
        n = len(blob) // 4
        for i in range(n - 1):
            ins = struct.unpack_from(">I", blob, i * 4)[0]
            if ins >> 26 != LFS:
                continue
            base = (ins >> 16) & 0x1F
            off0 = ins & 0xFFFF
            if off0 > 0x8000:
                off0 -= 0x10000
            want = [off0 + 4, off0 + 8, off0 + 12]
            hits = 0
            for j in range(1, 40):
                if i + j >= n:
                    break
                nxt = struct.unpack_from(">I", blob, (i + j) * 4)[0]
                if nxt >> 26 == LFS and (nxt >> 16) & 0x1F == base:
                    off = nxt & 0xFFFF
                    if off > 0x8000:
                        off -= 0x10000
                    if off in want:
                        hits += 1
                        want.remove(off)
                        if hits == 3:
                            print("  0x%08x: lfs f?,r%d +0x%x +0x%x +0x%x +0x%x" %
                                  (a + i * 4, base, off0, off0 + 4, off0 + 8, off0 + 12))
                            break
            if hits == 3:
                pass

    print("=== cmpwi rX, 0x56 (86) loops ===")
    for a, o, s in secs:
        blob = d[o:o + s]
        for i in range(0, len(blob) - 4, 4):
            ins = struct.unpack_from(">I", blob, i)[0]
            if ins >> 26 == CMPWI and (ins & 0xFFFF) == 0x56:
                r = (ins >> 16) & 0x1F
                print("  0x%08x: cmpwi r%d, 86" % (a + i, r))

    print("=== addis with base register (ra != 0) targeting 0x800A / 0x8019 / 0x801A pages ===")
    for a, o, s in secs:
        blob = d[o:o + s]
        for i in range(0, len(blob) - 4, 4):
            ins = struct.unpack_from(">I", blob, i)[0]
            op = ins >> 26
            if op == LIS:
                ra = (ins >> 16) & 0x1F
                imm = ins & 0xFFFF
                if ra != 0 and imm in (0x800A, 0x8019, 0x801A, 0x800B):
                    rt = (ins >> 21) & 0x1F
                    print("  0x%08x: addis r%d,r%d,0x%x" % (a + i, rt, ra, imm))


if __name__ == "__main__":
    scan()
