#!/usr/bin/env python3
"""Find all callers of a RAM target in main.dol (scan text sections for 'bl target')."""
import os, sys

EXTRACT = os.environ.get("NICK_EXTRACT", "/run/media/samp/787be337-88e4-4b95-92f9-45d37615cd02/games/console (other)/gcn+wii/extract")
d = open(os.path.join(EXTRACT, "nicku-ntsc", "P-GNOE", "sys", "main.dol"), "rb").read()

# (file_off, ram) per doldis.py
sects = [(0x100,0x80003100),(0x4A0,0x800034A0),(0x3F480,0x80042480),(0xB3F40,0x800B6F40),(0xE5500,0x80195620),(0xE6A20,0x80197C40)]
SECT_LEN = 0x100000

def ram_to_file(ram):
    for fo, ra in sects:
        if ra <= ram < ra + SECT_LEN:
            return fo + (ram - ra)
    return None

def file_to_ram(off):
    for fo, ra in sects:
        if fo <= off < fo + SECT_LEN:
            return ra + (off - fo)
    return None

from capstone import *

target = int(sys.argv[1], 16)
# find all bl/bcl targets == target
md = Cs(CS_ARCH_PPC, CS_MODE_BIG_ENDIAN + CS_MODE_32)
md.detail = True

hits = []
for fo, ra in sects:
    code = d[fo:fo+SECT_LEN]
    for insn in md.disasm(code, ra):
        if insn.mnemonic in ("bl", "b") :
            # operand is absolute address
            try:
                op = insn.op_str
                if op.startswith("0x"):
                    tgt = int(op, 16)
                    if tgt == target:
                        hits.append(insn.address)
                elif op.startswith("-0x") or (op and op[0] in "+-"):
                    # relative: decode
                    imm = int(op, 16)
                    tgt = insn.address + imm
                    if tgt == target:
                        hits.append(insn.address)
            except Exception:
                pass

print(f"callers/branches to 0x{target:08X}: {len(hits)}")
for h in hits:
    print(f"  0x{h:08X}")
