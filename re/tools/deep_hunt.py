#!/usr/bin/env python3
"""Deep hunt for the 86-vertex collision pool.

Strategy:
1. Parse the polygon records at 0x38AC to understand the index ranges
2. Look for pools in ALL chunks (not just SECT), in both f32 and s16 formats
3. If no explicit pool exists, check if the pool is built from mesh vertices
4. Compare polygon-record index ranges against mesh vertex pools
5. Check the C-block regions for embedded vertex data
"""
import struct, math, sys, os

TRB = "/home/cyan/code/nicku-mapper/asset-extract/nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb"

d = open(TRB, "rb").read()

# Parse TSFB container
hdrx_size = struct.unpack_from(">I", d, 0x10)[0]
n = struct.unpack_from(">I", d, 0x18)[0]
sizes = [struct.unpack_from(">I", d, 0x20 + 16 * i)[0] for i in range(n)]
sect_off = hdrx_size + 20 + 8
sect = d[sect_off:sect_off + sizes[0]]

def get_chunk(idx):
    """Get chunk data for section index idx."""
    off = sum(sizes[:idx])
    return d[sect_off + off : sect_off + off + sizes[idx]]

def s16(v):
    return v if v < 0x8000 else v - 0x10000

def read_f32(sect, off, count):
    """Read count f32 triples from sect at off."""
    verts = []
    for i in range(count):
        x = struct.unpack_from(">f", sect, off + i*12)[0]
        y = struct.unpack_from(">f", sect, off + i*12 + 4)[0]
        z = struct.unpack_from(">f", sect, off + i*12 + 8)[0]
        if math.isnan(x) or math.isinf(x) or math.isnan(y) or math.isinf(y) or math.isnan(z) or math.isinf(z):
            return None
        verts.append((x, y, z))
    return verts

def read_s16_pool(data, off, count, div=64.0):
    """Read count s16 triples from data at off."""
    verts = []
    for i in range(count):
        x = s16(struct.unpack_from(">H", data, off + i*6)[0]) / div
        z = s16(struct.unpack_from(">H", data, off + i*6 + 2)[0]) / div
        y = -s16(struct.unpack_from(">H", data, off + i*6 + 4)[0]) / div  # +y up
        verts.append((x, y, z))
    return verts

# === Part 1: Parse polygon records ===
print("=" * 70)
print("PART 1: Polygon Records at SECT+0x38AC")
print("=" * 70)

# First, walk the linked structure
cur = 0x38AC
nodes = []
for node_idx in range(4):
    node_data = []
    for j in range(4):
        v = struct.unpack_from(">I", sect, cur + j*4)[0]
        f = struct.unpack_from(">f", sect, cur + j*4)[0]
        node_data.append((v, f))
    print(f"  Node {node_idx} at +{cur:04X}:")
    print(f"    f32: ({node_data[0][1]:.4f}, {node_data[1][1]:.4f}, {node_data[2][1]:.4f})")
    print(f"    next_ptr: 0x{node_data[3][0]:08X}")
    nodes.append(cur)
    next_ptr = node_data[3][0]
    if 0x38AC <= next_ptr <= 0x3B10:
        cur = next_ptr
    else:
        print(f"    (next_ptr outside 0x38AC region, breaking)")
        break

# Now parse polygon records. They're at known offsets
poly_offsets = [0x38FC, 0x394C, 0x396C, 0x399C, 0x39D0, 0x3A24, 0x3A54, 0x3AA4, 0x3AC8, 0x3AF0]
print(f"\n  Parsing {len(poly_offsets)} polygon records:")
all_indices = set()
for pi, poff in enumerate(poly_offsets):
    count = struct.unpack_from(">I", sect, poff)[0]
    indices = [struct.unpack_from(">H", sect, poff + 4 + j*2)[0] for j in range(count)]
    term = struct.unpack_from(">H", sect, poff + 4 + count*2)[0]
    next_ptr = struct.unpack_from(">I", sect, poff + 6 + count*2)[0]
    all_indices.update(indices)
    print(f"  Poly[{pi}] +{poff:04X}: count={count:2d} indices={str(indices):40s} term=0x{term:04X} next=0x{next_ptr:08X}")

print(f"\n  Unique indices: {sorted(all_indices)}")
print(f"  Range: {min(all_indices)}..{max(all_indices)}, count={len(all_indices)}")

# === Part 2: Gather all mesh vertex pools ===
print("\n" + "=" * 70)
print("PART 2: Mesh Vertex Pools (s16/64 format)")
print("=" * 70)

# Get mesh records
mesh_recs = []
for k in range(86):
    moff = 0x3B08 + 0x34 * k
    rec = sect[moff:moff + 0x34]
    cx, cz, cy, rad = struct.unpack_from(">4f", rec, 0)
    C = struct.unpack_from(">I", rec, 0x20)[0]
    D = struct.unpack_from(">I", rec, 0x24)[0]
    A = struct.unpack_from(">I", rec, 0x14)[0]
    flag = struct.unpack_from(">I", rec, 0x30)[0]
    
    # Get the vertex pool from chunk k+1 (or relocated)
    # For SB1_01, chunks are at k+1
    chunk = get_chunk(k + 1)
    # The vertex pool is the first A bytes (padded pool size from +0x14)
    nverts = min(A // 6, len(chunk) // 6) if A >= 6 else 0
    
    mesh_recs.append({
        'k': k, 'center': (cx, cz, cy), 'radius': rad,
        'C': C, 'D': D, 'A': A, 'flag': flag, 'nverts': nverts,
        'chunk_size': len(chunk)
    })

# Read the vertex pools
mesh_pools = {}
for k in range(86):
    rec = mesh_recs[k]
    chunk = get_chunk(k + 1)
    nv = rec['nverts']
    if nv >= 3:
        verts = read_s16_pool(chunk, 0, nv)
        mesh_pools[k] = verts
    else:
        mesh_pools[k] = []

print(f"  Total meshes with vertices: {sum(1 for v in mesh_pools.values() if v)}")
print(f"  Total vertices across all meshes: {sum(len(v) for v in mesh_pools.values())}")

# === Part 3: Check if any mesh's vertex pool could serve as the collision pool ===
print("\n" + "=" * 70)
print("PART 3: Could any mesh pool be the collision pool?")
print("=" * 70)

# The collision pool needs exactly 86 vertices. Check each mesh's vertex count.
for k, verts in sorted(mesh_pools.items()):
    if len(verts) == 86:
        print(f"  Mesh {k}: EXACTLY 86 vertices!")
    elif 80 <= len(verts) <= 92:
        print(f"  Mesh {k}: {len(verts)} vertices (close to 86)")

# Check combined pools
print("\n  Checking if the pool is a concatenation of mesh pools...")
# No single mesh has 86 vertices, so it's not from one mesh

# === Part 4: Search for 86-vertex s16/64 pool in chunks ===
print("\n" + "=" * 70)
print("PART 4: Search for 86-vertex s16/64 pool in ALL chunks")
print("=" * 70)

for sec_idx in range(1, n):
    chunk = get_chunk(sec_idx)
    for off in range(0, len(chunk) - 86*6, 2):
        verts = read_s16_pool(chunk, off, 86)
        if verts is None:
            continue
        # Check plausibility
        xs = [v[0] for v in verts]
        ys = [v[1] for v in verts]
        zs = [v[2] for v in verts]
        xspan = max(xs) - min(xs)
        yspan = max(ys) - min(ys)
        zspan = max(zs) - min(zs)
        if 0.5 < xspan < 100 and 0.1 < yspan < 50 and 0.5 < zspan < 100:
            print(f"  Chunk {sec_idx} +{off:06X}: spans x={xspan:.2f} y={yspan:.2f} z={zspan:.2f}")
            print(f"    First 5: {verts[:5]}")
            break

# === Part 5: Search C-block region for 86-vertex s16/64 pool ===
print("\n" + "=" * 70)
print("PART 5: Search C-block region (SECT) for 86-vertex s16/64 pool")
print("=" * 70)

cblock_start = 0x4C80
# Find the actual end of all C-blocks
max_cend = 0
for k in range(86):
    max_cend = max(max_cend, mesh_recs[k]['C'] + mesh_recs[k]['D'])
print(f"  C-block range: 0x{cblock_start:X}..0x{max_cend:X}")

# Search in SECT from cblock_start to max_cend
for off in range(cblock_start, min(max_cend + 1000, len(sect) - 86*6), 2):
    verts = read_s16_pool(sect, off, 86)
    if verts is None:
        continue
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    xspan = max(xs) - min(xs)
    yspan = max(ys) - min(ys)
    zspan = max(zs) - min(zs)
    if 0.5 < xspan < 100 and 0.1 < yspan < 50 and 0.5 < zspan < 100:
        print(f"  SECT +{off:06X}: spans x={xspan:.2f} y={yspan:.2f} z={zspan:.2f}")
        print(f"    First 5: {verts[:5]}")

# === Part 6: Look at the C-block index data for meshes 5, 6, 8 ===
print("\n" + "=" * 70)
print("PART 6: C-block index data for large meshes (5, 6, 8)")
print("=" * 70)

for k in [5, 6, 8]:
    rec = mesh_recs[k]
    C, D = rec['C'], rec['D']
    print(f"\n  Mesh {k}: C=0x{C:X} D={D} (end=0x{C+D:X})")
    
    # Read the C-block data
    cblock = sect[C:C+D]
    if len(cblock) < 5:
        print(f"    C-block too small ({len(cblock)} bytes)")
        continue
    
    marker = cblock[0]
    if marker == 0x98:
        cnt = struct.unpack_from(">H", cblock, 1)[0]
        print(f"    0x98 marker, count={cnt}")
        # Try reading as u8 triples (recw 3)
        recw = 3
        data_start = 3
        data_end = data_start + cnt * recw
        if data_end <= len(cblock):
            pos_indices = [cblock[data_start + i*recw] for i in range(cnt)]
            print(f"    u8 pos indices: range {min(pos_indices)}..{max(pos_indices)}, unique={len(set(pos_indices))}")
        
        # The collision wall arrays might come after the index triples
        after_triples = data_start + cnt * recw
        remaining = len(cblock) - after_triples
        print(f"    Bytes after index triples: {remaining}")
        if remaining >= 86 * 12:  # 86 f32 triples
            print(f"    Has enough bytes for 86 f32 triples!")
            # Check
            f32_verts = read_f32(cblock, after_triples, 86)
            if f32_verts:
                xs = [v[0] for v in f32_verts]
                ys = [v[1] for v in f32_verts]
                zs = [v[2] for v in f32_verts]
                print(f"    f32 spans: x={max(xs)-min(xs):.2f} y={max(ys)-min(ys):.2f} z={max(zs)-min(zs):.2f}")
        
        if remaining >= 86 * 6:  # 86 s16 triples
            print(f"    Has enough bytes for 86 s16 triples!")
            s16_verts = read_s16_pool(cblock, after_triples, 86)
            if s16_verts:
                xs = [v[0] for v in s16_verts]
                ys = [v[1] for v in s16_verts]
                zs = [v[2] for v in s16_verts]
                print(f"    s16/64 spans: x={max(xs)-min(xs):.2f} y={max(ys)-min(ys):.2f} z={max(zs)-min(zs):.2f}")
    else:
        print(f"    No 0x98 marker at start (got 0x{marker:02X})")
        # Try reading the whole thing as f32 triples
        if len(cblock) >= 86 * 12:
            f32_verts = read_f32(cblock, 0, 86)
            if f32_verts:
                xs = [v[0] for v in f32_verts]
                ys = [v[1] for v in f32_verts]
                zs = [v[2] for v in f32_verts]
                print(f"    As f32: spans x={max(xs)-min(xs):.2f} y={max(ys)-min(ys):.2f} z={max(zs)-min(zs):.2f}")

# === Part 7: Examine extra data after ALL C-blocks ===
print("\n" + "=" * 70)
print("PART 7: Data after all C-blocks")
print("=" * 70)

# After each mesh's C-block there's a material name gap. Check what's there.
for k in range(86):
    rec = mesh_recs[k]
    gap_off = rec['C'] + rec['D']
    if gap_off + 0x20 <= len(sect):
        gap = sect[gap_off:gap_off + 0x20]
        name = gap.split(b"\x00")[0].decode("latin1", errors="replace")
        if name:
            pass  # Just material names
    # Check if there's extra data between material name gap and next C-block
    # For the last mesh, check from gap_off+0x20 to end
    if k == 85:
        extra_start = gap_off + 0x20
        while extra_start < len(sect) and sect[extra_start] == 0:
            extra_start += 1
        extra_start = (extra_start // 4) * 4
        extra_size = len(sect) - extra_start
        print(f"  After mesh 85 material name: {extra_size} bytes at +{extra_start:X}")
        if extra_size >= 86*12:
            f32_verts = read_f32(sect, extra_start, 86)
            if f32_verts:
                xs = [v[0] for v in f32_verts]
                ys = [v[1] for v in f32_verts]
                zs = [v[2] for v in f32_verts]
                print(f"    f32: spans x={max(xs)-min(xs):.2f} y={max(ys)-min(ys):.2f} z={max(zs)-min(zs):.2f}")
        if extra_size >= 86*6:
            s16_verts = read_s16_pool(sect, extra_start, 86)
            if s16_verts:
                xs = [v[0] for v in s16_verts]
                ys = [v[1] for v in s16_verts]
                zs = [v[2] for v in s16_verts]
                print(f"    s16/64: spans x={max(xs)-min(xs):.2f} y={max(ys)-min(ys):.2f} z={max(zs)-min(zs):.2f}")

# === Part 8: Examine the gaps between C-blocks (material name gap + following data) ===
print("\n" + "=" * 70)
print("PART 8: Gaps between C-blocks")
print("=" * 70)

# For each mesh, check what's between its C-block end and the start of the next C-block
cblocks_sorted = sorted([(mesh_recs[k]['C'], mesh_recs[k]['C'] + mesh_recs[k]['D'], k) for k in range(86)])
for i in range(len(cblocks_sorted) - 1):
    this_end = cblocks_sorted[i][1]
    next_start = cblocks_sorted[i+1][0]
    gap = next_start - this_end
    if gap > 32:  # more than just a material name
        k_this = cblocks_sorted[i][2]
        print(f"  Gap between mesh {k_this} end (0x{this_end:X}) and mesh {cblocks_sorted[i+1][2]} start (0x{next_start:X}): {gap} bytes")
        # Check for pool
        for off in range(this_end, next_start - 86*6, 2):
            verts = read_s16_pool(sect, off, 86)
            if verts:
                xs = [v[0] for v in verts]
                ys = [v[1] for v in verts]
                zs = [v[2] for v in verts]
                if 0.5 < max(xs)-min(xs) < 100 and 0.1 < max(ys)-min(ys) < 50:
                    print(f"    s16/64 pool at +{off:X}: spans x={max(xs)-min(xs):.2f} y={max(ys)-min(ys):.2f} z={max(zs)-min(zs):.2f}")
                    break

# === Part 9: Look at the material records region for embedded data ===
print("\n" + "=" * 70)
print("PART 9: Material records region analysis")
print("=" * 70)

# Materials start at 0x4C and end at 0x36C0
mat_start = 0x4C
mat_end = 0x36C0
print(f"  Material region: 0x{mat_start:X}..0x{mat_end:X} ({mat_end-mat_start} bytes)")

# The material region has len-prefixed names interleaved with 4x4 matrices
# Each material entry seems to be: name (padded to 0x20) + 0xFFFF + two 4x4 matrices (2 × 64 bytes = 128 bytes)
# This would be ~160 bytes per material. With ~28 materials, that's ~4480 bytes.
# But the region is 13940 bytes. There's a lot more here!
# Let's scan for interesting patterns

# Scan for 86-vertex f32 pools
for off in range(mat_start, mat_end - 86*12, 4):
    verts = read_f32(sect, off, 86)
    if verts:
        xs = [v[0] for v in verts]
        ys = [v[1] for v in verts]
        zs = [v[2] for v in verts]
        xspan, yspan, zspan = max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs)
        if 0.5 < xspan < 50 and 0.1 < yspan < 30 and 0.5 < zspan < 50:
            print(f"  f32 pool at +{off:06X}: spans x={xspan:.2f} y={yspan:.2f} z={zspan:.2f}")
            print(f"    First 5: {verts[:5]}")
            break

# === Part 10: Check if pool pointer is embedded in the polygon list header ===
print("\n" + "=" * 70)
print("PART 10: Pointer table analysis")
print("=" * 70)

# Pointer table at 0x3748
ptable_off = 0x3748
ptable_count = struct.unpack_from(">I", sect, ptable_off)[0]
print(f"  Pointer table count: {ptable_count}")
print(f"  Total entries: {ptable_count + 2}")

# Entry 87 (index 87) = 0x39E8
ptr87 = struct.unpack_from(">I", sect, ptable_off + 4 + 87*4)[0]
print(f"  ptr[87] = 0x{ptr87:08X}")

# What's at 0x39E8?
print(f"\n  Data at 0x{ptr87:04X}:")
for i in range(12):
    v = struct.unpack_from(">I", sect, ptr87 + i*4)[0]
    f = struct.unpack_from(">f", sect, ptr87 + i*4)[0]
    print(f"    +{ptr87 + i*4:04X}: u32=0x{v:08X} f={f:.4f}")

# Entry 0 = 0x3754 (self-reference)
# This is interesting: ptr[0] points to the pointer table's own data
print(f"\n  ptr[0] = 0x{ptrs_0:08X}" if False else "")

# Read entries 0 and 1
ptr0 = struct.unpack_from(">I", sect, ptable_off + 4 + 0*4)[0]
ptr1 = struct.unpack_from(">I", sect, ptable_off + 4 + 1*4)[0]
print(f"  ptr[0] = 0x{ptr0:08X} (pointer table self-ref)")
print(f"  ptr[1] = 0x{ptr1:08X} (polygon list)")

# Let me also look at what's between ptr[0] (0x3754) and ptr[1] (0x38AC)
# Data at 0x3754:
print(f"\n  Data between ptr[0] and ptr[1] (0x3754..0x38AC):")
# The ptr[0] at 0x3754 points to... the pointer table data area
# Actually 0x3754 is where the pointer array starts!
# ptr[0] = 0x3754, which is ptable_off + 4 + 8 = 0x3748 + 4 + 8 = 0x3754
# So ptr[0] points to the first data entry in the pointer table
# That would be: [86 count][86+2 pointers]
# ptr[0] at 0x3754 = start of the pointer array (after the count)

# Let's check: what is at 0x3754 in terms of the pointer table?
# 0x3754 = ptable_off + 12 = after count + ptr[0..1]
# Wait no: ptable_off = 0x3748. Count at +0, then ptr[0] at +4, ptr[1] at +8, ...
# ptr[0] value = 0x3754 = ptable_off + 12 = the start of main data after ptr[0] and ptr[1]
# So ptr[0] points to... the "data" part of the table. What's there?

print(f"  Data at 0x3754 (pointed to by ptr[0]):")
for i in range(8):
    v = struct.unpack_from(">I", sect, 0x3754 + i*4)[0]
    f = struct.unpack_from(">f", sect, 0x3754 + i*4)[0]
    tag = ""
    if i == 0:
        tag = "  <- ptr[1] value"
    print(f"    +{0x3754 + i*4:04X}: u32=0x{v:08X} f={f:.4f}{tag}")

print("\nDone.")
