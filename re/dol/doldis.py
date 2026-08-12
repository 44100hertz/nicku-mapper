import os, sys

EXTRACT = os.environ.get("NICK_EXTRACT", "")
from capstone import *
d = open(os.path.join(EXTRACT, "nicku-ntsc", "P-GNOE", "sys", "main.dol"), "rb").read()
# text sections per parent notes: file offsets -> RAM
sects = [(0x100,0x80003100),(0x4A0,0x800034A0),(0x3F480,0x80042480),(0xB3F40,0x800B6F40),(0xE5500,0x80195620),(0xE6A20,0x80197C40)]
def ram_to_file(ram):
    for fo, ra in sects:
        if ram >= ra and ram < ra + 0x100000:
            return fo + (ram - ra)
    return None
def disasm_file(off, count):
    md = Cs(CS_ARCH_PPC, CS_MODE_BIG_ENDIAN + CS_MODE_32)
    code = d[off:off+count*4]
    ram = None
    for fo, ra in sects:
        if fo <= off < fo + 0x40000:
            ram = ra + (off - fo)
    for i in md.disasm(code, ram or off):
        print(f"  0x{i.address:08X}: {i.mnemonic:8s} {i.op_str}")
target = int(sys.argv[1], 16)
count = int(sys.argv[2])
disasm_file(target, count)
