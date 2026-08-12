#!/usr/bin/env python3
"""Find callers of a target function in the DOL."""
import struct
import sys
from dol import Dol

dol = Dol.load()


def find_callers(target, max_results=100):
    callers = []
    for s in dol.sections:
        data = s["data"]
        base = s["ram"]
        for i in range(0, len(data) - 4, 4):
            insn = struct.unpack(">I", data[i : i + 4])[0]
            op = insn >> 26
            if op == 18:  # bl/b
                li = (insn >> 2) & 0x3FFFFFF
                if li & 0x2000000:
                    li -= 0x4000000
                tgt = (base + i + li) & 0xFFFFFFFF
                if tgt == target:
                    callers.append(base + i)
    return callers


if __name__ == "__main__":
    target = int(sys.argv[1], 0)
    callers = find_callers(target)
    print("callers of 0x%08x: %d" % (target, len(callers)))
    for c in callers[:100]:
        print("  0x%08x" % c)
