#!/usr/bin/env python3
"""Skeleton for extracting level meshes from Nicktoons Unite! (GC) level TRBs.

State: container + strip records decoded (see docs/trb-format-notes.md).
Missing piece: the shared vertex arrays (pos/uv/nrm) in SECT chunk 0 have not
been conclusively located/decoded yet, so this script currently:
  1. parses the container,
  2. dumps each mesh chunk's (pos, uv, nrm) strip records,
  3. writes a .obj with placeholder vertices (index / 100) so the *topology*
     can be eyeballed once arrays are found.

Once the vertex arrays are decoded, replace `placeholder_pos()` with real
positions and set `USE_PLACEHOLDER = False`.
"""
import struct
import sys
import os

def u32(b, o): return struct.unpack_from('>I', b, o)[0]
def s16(b, o): return struct.unpack_from('>h', b, o)[0]

USE_PLACEHOLDER = True  # set False once vertex arrays are decoded

class TrbLevel:
    def __init__(self, path):
        d = open(path, 'rb').read()
        self.data = d
        assert d[0:4] == b'TSFB'
        self.hdrx_size = u32(d, 16)
        self.chunk_count = u32(d, 24)
        self.chunk_sizes = [u32(d, 32 + i*16) for i in range(self.chunk_count)]
        self.sect_off = self.hdrx_size + 20          # -> 'TCES' tag
        assert d[self.sect_off:self.sect_off+4] == b'TCES'
        self.sect_size = u32(d, self.sect_off + 4)
        self.sect = d[self.sect_off+8: self.sect_off+8+self.sect_size]

    def chunk(self, i):
        """chunk i (0-based), per HDRX partition of the SECT blob."""
        o = sum(self.chunk_sizes[:i])
        return self.sect[o:o + self.chunk_sizes[i]]

    def parse_strip(self, chunk):
        """Parse 6-byte records (posIdx, uvIdx, nrmIdx) BE u16s."""
        recs = []
        n = (len(chunk) // 6) * 6
        for o in range(0, n, 6):
            p, t, m = struct.unpack_from('>HHH', chunk, o)
            recs.append((p, t, m))
        return recs

    def placeholder_pos(self, idx):
        """Temporary fake positions so topology is visible in a viewer."""
        x = (idx * 2654435761) % 4096 - 2048
        y = (idx * 40503) % 4096 - 2048
        z = (idx * 51749) % 4096 - 2048
        return x / 100.0, y / 100.0, z / 100.0

    def mesh_to_obj(self, i, fh):
        chunk = self.chunk(i + 1)          # chunk 0 is header/tables
        recs = self.parse_strip(chunk)
        if not recs:
            return
        fh.write(f"# mesh chunk {i+1}: {len(recs)} strip records\n")
        base = 0
        for p, t, m in recs:
            x, y, z = self.placeholder_pos(p)
            fh.write(f"v {x} {y} {z}\n")
            base += 1
        # triangle strip -> triangles (alternating winding)
        for k in range(len(recs) - 2):
            if k % 2 == 0:
                fh.write(f"f {base-len(recs)+k+1} {base-len(recs)+k+2} {base-len(recs)+k+3}\n")
            else:
                fh.write(f"f {base-len(recs)+k+1} {base-len(recs)+k+3} {base-len(recs)+k+2}\n")


def main(path):
    lvl = TrbLevel(path)
    print(f"chunks: {lvl.chunk_count}, SECT size 0x{lvl.sect_size:x}")
    out = os.path.splitext(path)[0] + "_mesh.obj"
    with open(out, 'w') as fh:
        fh.write(f"# {path}\n")
        for i in range(lvl.chunk_count - 1):
            lvl.mesh_to_obj(i, fh)
    print(f"wrote {out} (placeholder vertices: {USE_PLACEHOLDER})")


if __name__ == '__main__':
    main(sys.argv[1])
