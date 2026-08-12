#!/usr/bin/env python3
"""dis_ram.py — disassemble main.dol at a RAM address."""
import struct
import sys

sys.path.insert(0, "/home/cyan/code/nickmapper-lua/asset-extract/tools")
from re_dol import load_sections, addr_to_off
from capstone import Cs, CS_ARCH_PPC, CS_MODE_BIG_ENDIAN, CS_MODE_32

d, secs = load_sections()
md = Cs(CS_ARCH_PPC, CS_MODE_BIG_ENDIAN | CS_MODE_32)


def dis(addr, count=80):
    off = addr_to_off(d, secs, addr)
    if off is None:
        print("no section for", hex(addr))
        return
    code = d[off:off + count * 4]
    for ins in md.disasm(code, addr):
        print("0x%08x: %-26s %s" % (ins.address, ins.mnemonic, ins.op_str))


if __name__ == "__main__":
    addr = int(sys.argv[1], 16)
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 80
    dis(addr, n)
