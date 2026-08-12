#!/usr/bin/env python3
"""DOL -> ELF32 big-endian PowerPC converter (sections embedded, for Ghidra)."""
import struct, sys

def dol2elf(src, dst):
    d = open(src, "rb").read()
    offs = struct.unpack_from(">18I", d, 0)
    addrs = struct.unpack_from(">18I", d, 0x48)
    sizes = struct.unpack_from(">18I", d, 0x90)
    bss_addr, bss_size, entry = struct.unpack_from(">III", d, 0xD8)
    secs = []
    for i in range(18):
        if offs[i] and addrs[i] and sizes[i]:
            secs.append((offs[i], addrs[i], sizes[i], d[offs[i]:offs[i]+sizes[i]]))
    if bss_size:
        secs.append((0, bss_addr, bss_size, b""))  # bss (filesz 0)

    # pack payload after phdrs
    phoff = 0x34
    phentsize = 0x20
    payload = b""
    phdrs = b""
    for o, a, s, blob in secs:
        if o == 0:
            poff, filesz, flags = 0, 0, 6
        else:
            poff = len(payload) + phoff + phentsize * len(secs)
            payload += blob
            filesz = len(blob)
            flags = 6
            if 0x80003100 <= a < 0x80195000:
                flags = 5
        phdrs += struct.pack(">IIIIIIII", 1, poff, a, a, filesz, s, flags, 0x20)
    elf = struct.pack(">16sHHIIIIIHHHHHH",
        b"\x7fELF\x01\x02\x01\x00\x00\x00\x00\x00\x00\x00\x00",
        2, 20, 1, entry, phoff, 0, 0,
        0x34, phentsize, len(secs), 0, 0, 0)
    open(dst, "wb").write(elf + phdrs + payload)

if __name__ == "__main__":
    dol2elf(sys.argv[1], sys.argv[2])
    print("wrote", sys.argv[2])
