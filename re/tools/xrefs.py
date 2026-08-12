#!/usr/bin/env python3
"""xrefs.py — find lis+addi/ori/lwz references to string addresses in main.dol."""
import struct
import sys

sys.path.insert(0, "/home/cyan/code/nickmapper-lua/asset-extract/tools")
from re_dol import load_sections, addr_to_off

d, secs = load_sections()


def refs_to(ta, window=500, tol=0x20):
    hi = (ta >> 16) & 0xFFFF
    lo = ta & 0xFFFF
    out = []
    for a, o, s in secs:
        blob = d[o:o + s]
        for i in range(0, len(blob) - 4, 4):
            ins = struct.unpack_from(">I", blob, i)[0]
            if ins >> 26 != 15 or (ins & 0xFFFF) != hi:
                continue
            rt = (ins >> 21) & 0x1F
            for j in range(1, window):
                if i + 4 * j + 4 > len(blob):
                    break
                nxt = struct.unpack_from(">I", blob, i + 4 * j)[0]
                op = nxt >> 26
                rd = (nxt >> 21) & 0x1F
                ra = (nxt >> 16) & 0x1F
                if op == 14 and ra == rt and abs((nxt & 0xFFFF) - lo) <= tol:
                    out.append((a + i, j, "addi r%d,r%d,0x%x" % (rd, rt, nxt & 0xFFFF)))
                    break
                if op == 24 and rd == rt and ra == rt and abs((nxt & 0xFFFF) - lo) <= tol:
                    out.append((a + i, j, "ori r%d,r%d,0x%x" % (rd, rt, nxt & 0xFFFF)))
                    break
                if op == 32 and ra == rt and abs((nxt & 0xFFFF) - lo) <= tol:
                    out.append((a + i, j, "lwz r%d,0x%x(r%d)" % (rd, nxt & 0xFFFF, rt)))
                    break
    return out


if __name__ == "__main__":
    targets = [
        (0x80045D8C, "data/worldmodel.trb"),
        (0x80045D7C, "data/worldmodel"),
        (0x8004A244, ".trb"),
        (0x800479BC, "%s.trb"),
        (0x800506C0, "NickToonWorld_DannyL1"),
        (0x80050098, "LOADINGSTATE_Collision"),
        (0x800AF044, "Collision"),
        (0x800AF028, "SkeletonHeader"),
        (0x8004C1D8, "Database"),
        (0x8004C2C4, "ATerrainSection"),
        (0x8004D708, "AWorldMesh"),
        (0x8004E624, "ANTWorldMesh"),
    ]
    for ta, name in targets:
        hits = refs_to(ta)
        print("%s @0x%08x: %d refs" % (name, ta, len(hits)))
        for h in hits[:6]:
            print("   0x%08x (+%d): %s" % h)
