#!/usr/bin/env python3
"""w4k: search for TFourCC constants (both endiannesses)."""
import os, sys, re

EXTRACT = os.environ.get("NICK_EXTRACT", "/run/media/samp/787be337-88e4-4b95-92f9-45d37615cd02/games/console (other)/gcn+wii/extract")
sys.path.insert(0, os.path.join(EXTRACT, "tools"))
from dol import Dol
from capstone import Cs, CS_ARCH_PPC, CS_MODE_BIG_ENDIAN

DOL = os.path.join(EXTRACT, "nicku-ntsc", "P-GNOE", "sys", "main.dol")
dol = Dol.load(DOL)
md = Cs(CS_ARCH_PPC, CS_MODE_BIG_ENDIAN)
INS = []
for s in dol.sections:
    sd = s["data"]
    off = 0
    while off + 4 <= len(sd):
        r = list(md.disasm(sd[off:off + 4], s["ram"] + off))
        if r:
            INS.append((r[0].address, r[0].mnemonic, r[0].op_str))
        off += 4

def fourcc(s):
    return (ord(s[0]) << 24) | (ord(s[1]) << 16) | (ord(s[2]) << 8) | ord(s[3])
def bswap(v):
    return ((v & 0xFF) << 24) | ((v & 0xFF00) << 8) | ((v >> 8) & 0xFF00) | ((v >> 24) & 0xFF)

tags = {}
for s in ("HEAD", "HDRX", "SECT", "RELC", "SYMB", "TRBF", "TSFB", "NTAS", "NTAF", "TTLF", "FORM", "LINK", "DATA"):
    v = fourcc(s)
    tags[v] = s
    tags[bswap(v)] = s + "~bswap"

def imm(ops):
    m = re.findall(r'-?0x[0-9a-fA-F]+|(?<![\w.])-?\d+', ops)
    if not m:
        return None
    try:
        return int(m[-1], 0)
    except ValueError:
        return None

hits = []
for i in range(len(INS)):
    a, m, o = INS[i]
    if m == "lis":
        v = imm(o)
        if v is None:
            continue
        vh = v & 0xFFFF
        for j in range(i + 1, min(i + 8, len(INS))):
            a2, m2, o2 = INS[j]
            if m2 in ("ori", "addi"):
                r = re.findall(r'r(\d+)', o)
                r2 = re.findall(r'r(\d+)', o2)
                if not r or not r2 or r[0] != r2[0]:
                    continue
                v2 = imm(o2)
                if v2 is None:
                    continue
                cand = ((vh << 16) | v2) if m2 == "ori" else ((vh << 16) + (v2 if v2 >= 0 else v2 + 0x10000))
                cand &= 0xFFFFFFFF
                if cand in tags:
                    hits.append((a, tags[cand], cand, m2, o2))
                    break
print("fourcc constant sites:", len(hits))
for a, name, cand, m2, o2 in hits:
    print(f"  0x{a:08x}: {name} (0x{cand:08x}) {m2} {o2}")

# also: cmpwi/cmplwi with small constants won't hold these; but 'lwz' from data tables might.
# scan raw file for 4-byte fourcc values in data
import struct
print("\nraw fourcc values in file:")
for s in ("HEAD", "HDRX", "SECT", "RELC", "SYMB", "TRBF"):
    for v, nm in ((fourcc(s), s), (bswap(fourcc(s)), s + "~bswap")):
        pat = struct.pack(">I", v)
        start = 0
        cnt = 0
        while True:
            i = dol.data.find(pat, start)
            if i < 0 or cnt > 8:
                break
            ram = dol.file_to_ram(i)
            print(f"  {nm} @ file 0x{i:x} ram {hex(ram) if ram else 'unmapped'}")
            cnt += 1
            start = i + 1
