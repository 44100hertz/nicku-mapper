"""main.dol loader — proper section mapping for Nicktoons Unite! (GC).

The DOL header's data-section fields are garbage; the real text sections are
0, 1, 7, 8, 9, 10 with this fixed mapping (from docs/trb-format-notes.md):

    file 0x100   -> 0x80003100  (size 0x3a0)
    file 0x4a0   -> 0x800034a0  (size 0x3efe0)
    file 0x3f480 -> 0x80042480  (size 0x74ac0)
    file 0xb3f40 -> 0x800b6f40  (size 0x315c0)
    file 0xe5500 -> 0x80195620  (size 0x1520)
    file 0xe6a20 -> 0x80197c40  (size 0x1de0)

SDA bases (set in __start): r13 = 0x8019D620, r2 = 0x801AD620.
"""
import re
import struct

SECTIONS = [
    # (file_offset, ram_addr, size)
    (0x100, 0x80003100, 0x3a0),
    (0x4a0, 0x800034a0, 0x3efe0),
    (0x3f480, 0x80042480, 0x74ac0),
    (0xb3f40, 0x800b6f40, 0x315c0),
    (0xe5500, 0x80195620, 0x1520),
    (0xe6a20, 0x80197c40, 0x1de0),
]
R13_BASE = 0x8019D620
R2_BASE = 0x801AD620


class Dol:
    def __init__(self, data, path=None):
        self.data = data
        self.path = path
        self.sections = []
        for fo, ram, sz in SECTIONS:
            self.sections.append({
                "file": fo, "ram": ram, "size": sz,
                "data": data[fo:fo + sz],
            })
        self.sections.sort(key=lambda s: s["ram"])
        self._by_ram = {s["ram"]: s for s in self.sections}

    @classmethod
    def load(cls, path):
        return cls(open(path, "rb").read(), path)

    def file_to_ram(self, off):
        for fo, ram, sz in SECTIONS:
            if fo <= off < fo + sz:
                return ram + (off - fo)
        return None

    def ram_to_file(self, addr):
        for fo, ram, sz in SECTIONS:
            if ram <= addr < ram + sz:
                return fo + (addr - ram)
        return None

    def ram_to_section(self, addr):
        for s in self.sections:
            if s["ram"] <= addr < s["ram"] + s["size"]:
                return s
        return None

    def read(self, addr, n):
        s = self.ram_to_section(addr)
        if s is None:
            return None
        off = addr - s["ram"]
        return s["data"][off:off + n]

    def u32(self, addr):
        b = self.read(addr, 4)
        if b is None or len(b) < 4:
            return None
        return struct.unpack(">I", b)[0]

    def strings(self, min_len=4):
        """Yield (ram_addr, string) for printable ASCII runs in all sections."""
        for s in self.sections:
            base = s["ram"]
            for m in re.finditer(rb"[\x20-\x7e]{%d,}" % min_len, s["data"]):
                yield base + m.start(), m.group().decode("ascii", "replace")

    def find_string(self, needle):
        return [(addr, s) for addr, s in self.strings() if needle in s]

    def cstring(self, addr):
        b = self.read(addr, 256)
        if b is None:
            return None
        end = b.find(b"\0")
        if end < 0:
            end = len(b)
        return b[:end].decode("latin1", "replace")
