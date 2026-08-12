#!/usr/bin/env python3
"""Block arithmetic: D vs F*3+4+pad, D vs A/B; find end of C..E region; scan for global vertex array."""
import struct

PATH = "nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb"
d = open(PATH, "rb").read()
SECT = 0x594
sect = d[SECT:SECT + 0x34680]

def u32(o): return struct.unpack_from(">I", sect, o)[0]

hdrx = 0x20
sizes = []
for i in range(87):
    sizes.append(struct.unpack_from(">I", d, hdrx + i * 16)[0])

print("=== D vs (4 + F*3) vs A, B — meshes 0..85 ===")
bad_af = []
for k in range(86):
    off = 0x3B08 + 0x34 * k
    A, B, C, D, F = u32(off+20), u32(off+24), u32(off+32), u32(off+36), u32(off+44)
    minface = 4 + F * 3
    pad = D - minface
    flag = "OK" if 0 <= pad <= 0x40 else ("PAD=%d" % pad if pad > 0 else "UNDERFLOW")
    ab = ""
    if D == A: ab = " D==A"
    if D == A + B: ab = " D==A+B"
    if D == B: ab = " D==B"
    print("m%2d A=0x%x B=0x%x D=0x%x F=0x%x 4+3F=0x%x pad=%s%s" % (k, A, B, C + D - C if False else D, F, minface, flag, ab))
    if not (0 <= pad <= 0x40):
        bad_af.append(k)
print("meshes where D != 4+3F+pad(<=0x40):", bad_af)

# where do blocks end?
last = 0x3B08 + 0x34 * 85
C85, D85 = u32(last + 32), u32(last + 36)
print("mesh85 block end: 0x%x" % (C85 + D85))

# region after blocks to chunk0 end
end = C85 + D85
print("region after blocks: 0x%x..0x1f7e0 = 0x%x bytes" % (end, 0x1F7E0 - end))
