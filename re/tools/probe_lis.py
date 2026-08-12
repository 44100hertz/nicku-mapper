#!/usr/bin/env python3
"""probe_lis.py — for a given lis page, show what each lis feeds into."""
import struct
import sys

sys.path.insert(0, "/home/cyan/code/nickmapper-lua/asset-extract/tools")
from re_dol import load_sections

d, secs = load_sections()


def main(page=0x8004, window=200):
    for a, o, s in secs:
        blob = d[o:o + s]
        for i in range(0, len(blob) - 4, 4):
            ins = struct.unpack_from(">I", blob, i)[0]
            if ins >> 26 == 15 and (ins & 0xFFFF) == page:
                rt = (ins >> 21) & 0x1F
                found = None
                for j in range(1, window):
                    nxt = struct.unpack_from(">I", blob, i + 4 * j)[0]
                    op = nxt >> 26
                    rd = (nxt >> 21) & 0x1F
                    ra = (nxt >> 16) & 0x1F
                    if op == 14 and (ra == rt or rd == rt):
                        found = "addi r%d,r%d,0x%x @+%d" % (rd, ra, nxt & 0xFFFF, j)
                        break
                    if op == 24 and rd == rt and ra == rt:
                        found = "ori r%d,r%d,0x%x @+%d" % (rd, rt, nxt & 0xFFFF, j)
                        break
                    if op == 32 and ra == rt:
                        found = "lwz r%d,0x%x(r%d) @+%d" % (rd, nxt & 0xFFFF, ra, j)
                        break
                print("0x%08x: lis r%d, 0x%x  %s" % (a + i, rt, page, found or "no use"))


if __name__ == "__main__":
    main(int(sys.argv[1], 16) if len(sys.argv) > 1 else 0x8004)
