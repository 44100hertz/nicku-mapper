#!/usr/bin/env python3
"""dolscan2.py — find mesh-record field readers & index/vertex loops in main.dol."""
import struct
import sys

sys.path.insert(0, "/home/cyan/code/nickmapper-lua/asset-extract/tools")
from re_dol import load_sections

d, secs = load_sections()

LWZ = 32
LFS = 48
LHA = 42
LHBX = 31  # lhax is opcode 31 XO=343
LHAX = 343
LHZ = 40
LHZX = 279
STW = 36
ADDI = 14
CMPWI = 11
CMPW = 31  # cmpw opcode31 XO=0
CMPLWI = 10
BC = 16


def s16(x):
    return x - 0x10000 if x > 0x8000 else x


def scan_record_reader():
    print("=== lwz reader: offsets 0x20+0x24+0x28+0x2C+0x30 same base within 60 insns ===")
    for a, o, s in secs:
        blob = d[o:o + s]
        n = len(blob) // 4
        for i in range(n - 1):
            ins = struct.unpack_from(">I", blob, i * 4)[0]
            if ins >> 26 != LWZ:
                continue
            base = (ins >> 16) & 0x1F
            off = s16(ins & 0xFFFF)
            if off not in (0x20, 0x24, 0x28):
                continue
            want = set()
            for o0 in (0x20, 0x24, 0x28, 0x2C, 0x30):
                for o1 in (0x20, 0x24, 0x28, 0x2C, 0x30):
                    if o1 != off:
                        want.add(o1)
            got = set()
            for j in range(1, 60):
                if i + j >= n:
                    break
                nxt = struct.unpack_from(">I", blob, (i + j) * 4)[0]
                if nxt >> 26 == LWZ and (nxt >> 16) & 0x1F == base:
                    o2 = s16(nxt & 0xFFFF)
                    if o2 in want:
                        got.add(o2)
                        if len(got) >= 3:
                            print("  0x%08x: lwz base r%d offs 0x%x then %s" %
                                  (a + i * 4, base, off, sorted(got)))
                            break


def scan_index_loops():
    print("=== lhz/lha in loops (u16/u16 index reads): lhz base +0 then +2 or +4 stride ===")
    for a, o, s in secs:
        blob = d[o:o + s]
        n = len(blob) // 4
        for i in range(n - 1):
            ins = struct.unpack_from(">I", blob, i * 4)[0]
            op = ins >> 26
            if op not in (LHZ, LHA, LWZ):
                continue
            base = (ins >> 16) & 0x1F
            off = s16(ins & 0xFFFF)
            # look for 3+ reads from same base with small positive offsets within 40 insns
            offs = [off]
            for j in range(1, 40):
                if i + j >= n:
                    break
                nxt = struct.unpack_from(">I", blob, (i + j) * 4)[0]
                if nxt >> 26 in (LHZ, LHA, LWZ) and (nxt >> 16) & 0x1F == base:
                    o2 = s16(nxt & 0xFFFF)
                    if o2 >= 0 and o2 < 0x80 and o2 not in offs:
                        offs.append(o2)
                        if len(offs) >= 4:
                            print("  0x%08x: reads from r%d: %s" % (a + i * 4, base, [hex(x) for x in sorted(offs)]))
                            break
            if len(offs) >= 4:
                pass


def scan_0x98_marker():
    print("=== cmpwi/li with 0x98 (152) — possible C-block marker check ===")
    for a, o, s in secs:
        blob = d[o:o + s]
        for i in range(0, len(blob) - 4, 4):
            ins = struct.unpack_from(">I", blob, i)[0]
            op = ins >> 26
            imm = ins & 0xFFFF
            if imm > 0x8000:
                imm -= 0x10000
            if op == CMPWI and imm == 0x98:
                r = (ins >> 16) & 0x1F
                print("  0x%08x: cmpwi r%d, 0x98" % (a + i, r))
            if op == ADDI and (ins >> 16) & 0x1F == 0 and imm == 0x98:
                rd = (ins >> 21) & 0x1F
                print("  0x%08x: li r%d, 0x98" % (a + i, rd))


if __name__ == "__main__":
    scan_record_reader()
    scan_index_loops()
    scan_0x98_marker()
