#!/usr/bin/env python3
"""Parser + PowerPC big-endian disassembler for Nicktoons Unite! main.dol.

The DOL header of this game is non-standard (data-section fields are garbage;
code lives in text sections at indices 0,1,6,7,8,9). This loader maps only the
text sections, which is what we need.

Usage (needs capstone: `nix-shell -p python3Packages.capstone`):
    python3 ppcdis.py <main.dol> <start-addr-hex> [count]
"""
import struct
import sys

DOL_DEFAULT = "/PATH/TO/extract/nicku-ntsc/P-GNOE/sys/main.dol"


def load_sections(path):
    d = open(path, 'rb').read()
    toff = [struct.unpack_from('>I', d, 0x00 + 4*i)[0] for i in range(18)]
    taddr = [struct.unpack_from('>I', d, 0x48 + 4*i)[0] for i in range(18)]
    tsize = [struct.unpack_from('>I', d, 0x90 + 4*i)[0] for i in range(18)]
    secs = []
    for i in range(18):
        if tsize[i] and toff[i]:
            secs.append((taddr[i], toff[i], tsize[i]))
    return d, secs


def addr_to_off(d, secs, addr):
    for a, o, s in secs:
        if a <= addr < a + s:
            return o + (addr - a)
    return None


def off_to_addr(d, secs, off):
    for a, o, s in secs:
        if o <= off < o + s:
            return a + (off - o)
    return None


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DOL_DEFAULT
    start = int(sys.argv[2], 16)
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 40
    d, secs = load_sections(path)
    print(f"sections: {[(hex(a), hex(o), hex(s)) for a, o, s in secs]}")
    try:
        from capstone import Cs, CS_ARCH_PPC, CS_MODE_BIG_ENDIAN
    except ImportError:
        print("capstone missing; run via: nix-shell -p python3Packages.capstone")
        return
    o = addr_to_off(d, secs, start)
    if o is None:
        print(f"address 0x{start:x} not in any text section")
        return
    md = Cs(CS_ARCH_PPC, CS_MODE_BIG_ENDIAN)
    for ins in md.disasm(d[o:o + n*4], start):
        print(f"  0x{ins.address:x}: {ins.mnemonic} {ins.op_str}")


if __name__ == '__main__':
    main()
