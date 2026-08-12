#!/usr/bin/env python3
"""Find GX library functions in main.dol and their callers.

GXSetArray(attr, base, stride):  stb 0x40|attr<<4 @0xCC008000; stw addr; stb stride; stb 0
GXBegin(prim, fmt, n):           stb 0x80 @0xCC008000; stb prim; stb fmt; stw/sth count
"""
import struct
from dol import Dol
from capstone import Cs, CS_ARCH_PPC, CS_MODE_BIG_ENDIAN, CS_MODE_32

md = Cs(CS_ARCH_PPC, CS_MODE_BIG_ENDIAN | CS_MODE_32)
md.detail = True
dol = Dol.load()


def disasm(addr, n):
    b = dol.read(addr, n)
    return list(md.disasm(b, addr))


def find_gxsetarray():
    """Pattern: sequence of stb/stw to 0xCC008000 within ~40 bytes."""
    cands = []
    for s in dol.sections:
        data = s["data"]
        base = s["ram"]
        for i in range(0, len(data) - 4, 4):
            # start: stb rX, 0x8000(rY) where rY holds 0xCC00
            insn = struct.unpack(">I", data[i : i + 4])[0]
            op = insn >> 26
            rd = (insn >> 21) & 31
            ra = (insn >> 16) & 31
            imm = insn & 0xFFFF
            if op == 38 and imm == 0x8000 and ra != 0:
                a = base + i
                # count following stb/stw to 0x8000(rra) within 0x30 bytes
                cnt = 0
                for j in range(i + 4, min(i + 0x40, len(data) - 3), 4):
                    insn2 = struct.unpack(">I", data[j : j + 4])[0]
                    op2 = insn2 >> 26
                    rd2 = (insn2 >> 21) & 31
                    ra2 = (insn2 >> 16) & 31
                    imm2 = insn2 & 0xFFFF
                    if op2 in (36, 38) and imm2 == 0x8000 and ra2 == ra:
                        cnt += 1
                    if op2 not in (36, 38) and op2 != 0x20:  # not memop
                        break
                if cnt >= 3:
                    cands.append((a, cnt))
    return cands


def find_callers(target):
    callers = []
    for s in dol.sections:
        data = s["data"]
        base = s["ram"]
        for i in range(0, len(data) - 4, 4):
            insn = struct.unpack(">I", data[i : i + 4])[0]
            op = insn >> 26
            if op == 18:  # bl/b
                li = (insn >> 2) & 0x3FFFFFF
                if li & 0x2000000:
                    li -= 0x4000000
                tgt = (base + i + li) & 0xFFFFFFFF
                if tgt == target:
                    callers.append(base + i)
    return callers


if __name__ == "__main__":
    cands = find_gxsetarray()
    print("GXSetArray candidates:", len(cands))
    for a, cnt in cands[:40]:
        print("  0x%08x writes=%d" % (a, cnt))
