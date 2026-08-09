#!/usr/bin/env python3
"""Find all branches to a target in main.dol, decoding bl/b immediates directly.
Correct mapping: text[1] file 0x4A0 -> RAM 0x800034A0 (size 0x3EFE0)."""
import os, sys

EXTRACT = os.environ.get("NICK_EXTRACT", "/run/media/samp/787be337-88e4-4b95-92f9-45d37615cd02/games/console (other)/gcn+wii/extract")
d = open(os.path.join(EXTRACT, "nicku-ntsc", "P-GNOE", "sys", "main.dol"), "rb").read()

SECTS = [(0x100, 0x80003100, 0x3A0), (0x4A0, 0x800034A0, 0x3EFE0),
         (0x3F480, 0x80042480, 0x74AC0), (0xB3F40, 0x800B6F40, 0x315C0),
         (0xE5500, 0x80195620, 0x1520), (0xE6A20, 0x80197C40, 0x1DE0)]

def ram_to_file(ram):
    for fo, ra, sz in SECTS:
        if ra <= ram < ra + sz:
            return fo + (ram - ra)
    return None

def file_to_ram(off):
    for fo, ra, sz in SECTS:
        if fo <= off < fo + sz:
            return ra + (off - fo)
    return None

target = int(sys.argv[1], 16)
hits = []
for fo, ra, sz in SECTS:
    if sz == 0:
        continue
    code = d[fo:fo + sz]
    n = (len(code) // 4) * 4
    for off in range(0, n, 4):
        w = int.from_bytes(code[off:off + 4], "big")
        if (w & 0xFC000000) != 0x48000000:
            continue
        imm = (w & 0x03FFFFFC)
        if imm & 0x02000000:
            imm -= 0x04000000
        tgt = ra + off + imm
        if tgt == target:
            hits.append(ra + off)

print(f"branches to 0x{target:08X}: {len(hits)}")
for h in hits:
    print(f"  0x{h:08X} (file 0x{ram_to_file(h):X})")
