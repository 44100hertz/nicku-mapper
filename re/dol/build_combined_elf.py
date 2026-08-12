#!/usr/bin/env python3
"""Combine the DOL text sections + the VM image (vmtext.bin @ 0x7f004000)
into one ELF32 PPC-BE program so Ghidra resolves cross-references both ways.

This is THE binary to decompile for Nicktoons Unite! (GCN, P-GNOE): the
engine (Toshi) code lives in vmtext (0x7f004000+, incl. the TTRB loader
FUN_7f297178 and the whole collision system around 0x7f25xxxx/0x7f2axxxx),
and the game/DOL code lives at 0x8000xxxx (GX at 0x80006xxx, OpCODE dead
strings at 0x800A9xxx, resource dispatcher ~0x8002xxxx). The prior Ghidra
project for the exact ELF produced by this script is cached by sha256 in
~/.pi/agent pi-ghidra cache (see scripts/dol/README.md).

Inputs (both byte-identical to what's on the ISO):
  main.dol   -> nicku-ntsc/P-GNOE/sys/main.dol   (the DOL, 18-section layout)
  vmtext.bin -> nicku-ntsc/P-GNOE/files/vmtext.bin (engine image @ 0x7f004000)

Resolved from NICK_EXTRACT (default: the mounted disc-extract root). The ISO
itself is nicktoonsunite.iso, a sibling of the extract dir under
  games/console (other)/gcn+wii/  (mount: /run/media/<user>/<uuid>/...)

Usage:  python3 build_combined_elf.py [--dol F] [--vmtext F] [-o OUT]
"""
import argparse
import os
import struct
import sys

EXTRACT = os.environ.get(
    "NICK_EXTRACT",
    "/run/media/samp/787be337-88e4-4b95-92f9-45d37615cd02/games/console (other)/gcn+wii/extract",
)


def u32(d, o):
    return int.from_bytes(d[o:o + 4], "big")


def build(dol_path, vm_path, out_path):
    dol = open(dol_path, "rb").read()
    vm = open(vm_path, "rb").read()

    # compact custom header layout (dol2elf.py): offs@0x00 addrs@0x48 sizes@0x90 bss/entry@0xD8
    offs = struct.unpack_from(">18I", dol, 0x00)
    addrs = struct.unpack_from(">18I", dol, 0x48)
    sizes = struct.unpack_from(">18I", dol, 0x90)
    bss_addr, bss_size, entry = struct.unpack_from(">III", dol, 0xD8)

    secs = []
    for i in range(18):
        if offs[i] and addrs[i] and sizes[i]:
            secs.append((addrs[i], sizes[i], dol[offs[i]:offs[i] + sizes[i]], 5))  # R E
    if bss_size:
        secs.append((bss_addr, bss_size, b"", 6))  # RW, filesz 0
    secs.append((0x7F004000, len(vm), vm, 5))      # VM image, R E

    phoff = 0x34
    phentsize = 0x20
    payload = b""
    phdrs = b""
    for a, s, blob, flags in secs:
        if not blob:
            poff, filesz = 0, 0
        else:
            poff = len(payload) + phoff + phentsize * len(secs)
            payload += blob
            filesz = len(blob)
        phdrs += struct.pack(">IIIIIIII", 1, poff, a, a, filesz, s, flags, 0x20)

    elf = struct.pack(
        ">16sHHIIIIIHHHHHH",
        b"\x7fELF\x01\x02\x01\x00\x00\x00\x00\x00\x00\x00\x00",
        2, 20, 1, entry, phoff, 0, 0,
        0x34, phentsize, len(secs), 0, 0, 0,
    )
    open(out_path, "wb").write(elf + phdrs + payload)
    print("wrote %s: %d segments, payload %#x bytes, vm @0x7f004000 size %#x"
          % (out_path, len(secs), len(payload), len(vm)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dol", default=os.path.join(EXTRACT, "nicku-ntsc", "P-GNOE", "sys", "main.dol"))
    ap.add_argument("--vmtext", default=os.path.join(EXTRACT, "nicku-ntsc", "P-GNOE", "files", "vmtext.bin"))
    ap.add_argument("-o", "--out", default="vmtext_combined.elf")
    args = ap.parse_args()
    if not os.path.exists(args.dol):
        sys.exit("main.dol not found at %s — is the drive mounted? set NICK_EXTRACT." % args.dol)
    if not os.path.exists(args.vmtext):
        sys.exit("vmtext.bin not found at %s — is the drive mounted? set NICK_EXTRACT." % args.vmtext)
    build(args.dol, args.vmtext, args.out)


if __name__ == "__main__":
    main()
