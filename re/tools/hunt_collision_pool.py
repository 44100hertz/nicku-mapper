#!/usr/bin/env python3
"""hunt_collision_pool.py — parse 0x38AC polygon records and hunt for the 86-vertex f32 pool."""
import struct, math, sys

TRB = "/home/cyan/code/nicku-mapper/asset-extract/nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb"

d = open(TRB, "rb").read()

# Parse TSFB container
hdrx_size = struct.unpack_from(">I", d, 0x10)[0]
n = struct.unpack_from(">I", d, 0x18)[0]
sizes = [struct.unpack_from(">I", d, 0x20 + 16 * i)[0] for i in range(n)]
sect_off = hdrx_size + 20 + 8
sect = d[sect_off:sect_off + sizes[0]]

print("=== Container ===")
print(f"HDRX size: {hdrx_size}, sections: {n}")
print(f"SECT offset: {sect_off}, SECT size: {sizes[0]}")
print(f"Sum all sizes: {sum(sizes)}")
print()

# === Parse 0x38AC polygon records ===
print("=== Polygon Records at SECT+0x38AC ===")
offset = 0x38AC
# First: parse the header/chain
# From the format notes: "a 4-node pointer chain of f32 box data"
# Let's read the raw bytes first
print("Raw hex dump of first 0x50 bytes:")
for i in range(0, 0x50, 16):
    line = sect[offset:offset+0x50]
    hexstr = " ".join(f"{b:02x}" for b in line[i:i+16])
    print(f"  +{i:04x}: {hexstr}")
print()

# Parse as: the region has a pointer table at 0x3748 with count=86, then 88 pointers
# Pointer table entry 1 (at 0x3754) = 0x38AC — this is the start of the polygon list
ptable_off = 0x3748
ptable_count = struct.unpack_from(">I", sect, ptable_off)[0]
print(f"Pointer table at +{ptable_off:04X}: count={ptable_count}")
ptrs = []
for i in range(88):  # count + 2 extra
    v = struct.unpack_from(">I", sect, ptable_off + 4 + i * 4)[0]
    ptrs.append(v)
    tag = ""
    if 0x38A0 <= v <= 0x3B10: tag = " ← polygon region"
    if 0x3B08 <= v <= 0x4C80: tag = " ← mesh records"
    if 0x36C0 <= v <= 0x3748: tag = " ← collision stub/zeros"
    print(f"  [{i:2d}] 0x{v:08X}{tag}")
print()

# Now parse the actual polygon records
# Each record: [u32 count][count×u16 indices][u16 0 terminator][u32 next_ptr]
print("=== Polygon record parsing ===")
cur = 0x38AC
records = []
# First 0x50 bytes at 0x38AC are 20 u32s. Let's see if the first 16 bytes are 4 f32s or a u32 chain
# From format notes: "a 4-node pointer chain of f32 box data (8.31, 10.46, 2.32 / -3.51, 14.80, 2.06 / 0.36, 20.40, 1.36 / 7.65, 17.75, 0.74 — z ≈ 1-2"
# These are at 0x38AC. Let's parse them:
for i in range(4):
    x = struct.unpack_from(">f", sect, 0x38AC + i*12)[0]
    y = struct.unpack_from(">f", sect, 0x38AC + i*12 + 4)[0]
    z = struct.unpack_from(">f", sect, 0x38AC + i*12 + 8)[0]
    print(f"  node[{i}] f32: ({x:.3f}, {y:.3f}, {z:.3f})")

# After the 4×3×f32 = 48 bytes (0x38DC), there might be next pointers
# Let's look at 0x38DC
for i in range(8):
    v = struct.unpack_from(">I", sect, 0x38DC + i*4)[0]
    f = struct.unpack_from(">f", sect, 0x38DC + i*4)[0]
    print(f"  +{0x38DC + i*4:04X}: u32=0x{v:08X} f={f:.4f}")

# Let me try a different approach: walk the linked list from the format notes
# The notes say "linked structure: a 4-node pointer chain of f32 box data... then 11 polygon records"
# So maybe it's: [4xf32 box + next_ptr] × 4, then polygon records
# Let's parse it that way:
print("\n=== Walk linked structure ===")
cur = 0x38AC
for node_idx in range(4):
    x = struct.unpack_from(">f", sect, cur)[0]
    y = struct.unpack_from(">f", sect, cur + 4)[0]
    z = struct.unpack_from(">f", sect, cur + 8)[0]
    maybe_next = struct.unpack_from(">I", sect, cur + 12)[0]
    print(f"  Node {node_idx} at +{cur:04X}: box=({x:.3f}, {y:.3f}, {z:.3f}) next=0x{maybe_next:08X}")
    if 0x38AC <= maybe_next <= 0x3B10:
        cur = maybe_next
    else:
        print(f"  Next ptr 0x{maybe_next:08X} not in region, stopping")
        break

# Now, after the 4 nodes, we should be at polygon records
# Let's parse from where we ended up through the region
# The polygon records are at: 0x38FC, 0x394C, 0x396C, 0x399C, 0x39D0, 0x3A24, 0x3A54, 0x3AA4, 0x3AC8, 0x3AF0
poly_offsets = [0x38FC, 0x394C, 0x396C, 0x399C, 0x39D0, 0x3A24, 0x3A54, 0x3AA4, 0x3AC8, 0x3AF0]
print(f"\n=== Parsing {len(poly_offsets)} polygon records ===")
all_indices = set()
for pi, poff in enumerate(poly_offsets):
    count = struct.unpack_from(">I", sect, poff)[0]
    indices = []
    for j in range(count):
        idx = struct.unpack_from(">H", sect, poff + 4 + j * 2)[0]
        indices.append(idx)
    term = struct.unpack_from(">H", sect, poff + 4 + count * 2)[0]
    next_ptr = struct.unpack_from(">I", sect, poff + 4 + count * 2 + 2)[0]
    all_indices.update(indices)
    print(f"  Poly[{pi}] at +{poff:04X}: count={count}, indices={indices}, term=0x{term:X}, next=0x{next_ptr:08X}")

print(f"\nAll referenced indices: {sorted(all_indices)}")
print(f"Index range: {min(all_indices)}..{max(all_indices)}  (count={len(all_indices)})")

# === SEARCH FOR THE 86-VERTEX F32 POOL ===
print("\n" + "="*60)
print("=== HUNTING FOR 86-VERTEX F32 POOL (86×3×4 = 1032 bytes) ===")
print("="*60)

# A valid f32 pool would be 86 triples of reasonable f32 values.
# The level bounds are: (9.639, 8.873, -0.300, 36.375) from +0x1C
# Actually let me check the level bounds
bx, bz, by, bh = struct.unpack_from(">4f", sect, 0x1C)
print(f"Level bounds: x={bx:.3f}, z={bz:.3f}, y={by:.3f}, h={bh:.3f}")

def is_plausible_f32(sect, off, count):
    """Check if 'count' f32 triples at 'off' look like plausible vertex coordinates."""
    mins = [float('inf')]*3
    maxs = [float('-inf')]*3
    for i in range(count):
        for j in range(3):
            v = struct.unpack_from(">f", sect, off + i*12 + j*4)[0]
            if math.isnan(v) or math.isinf(v):
                return False, None, None
            mins[j] = min(mins[j], v)
            maxs[j] = max(maxs[j], v)
    spans = [maxs[i] - mins[i] for i in range(3)]
    return True, mins, maxs

def is_plausible_s16(sect, off, count, div=64.0):
    """Check if 'count' s16 triples at 'off' look like plausible vertex coordinates."""
    mins = [float('inf')]*3
    maxs = [float('-inf')]*3
    n_zero = 0
    for i in range(count):
        for j in range(3):
            raw = struct.unpack_from(">h", sect, off + i*6 + j*2)[0]
            v = raw / div
            mins[j] = min(mins[j], v)
            maxs[j] = max(maxs[j], v)
            if raw == 0:
                n_zero += 1
    spans = [maxs[i] - mins[i] for i in range(3)]
    # too many zeros might be padding
    return n_zero < count * 2, mins, maxs, n_zero

# Strategy 1: Scan the entire SECT for 1032 bytes of plausible f32 triples
print("\n--- Scanning SECT (0..{}) for 86-vertex f32 runs ---".format(len(sect)))
candidates = []
for off in range(0, len(sect) - 1032, 4):
    ok, mins, maxs = is_plausible_f32(sect, off, 86)
    if ok:
        spans = [maxs[i] - mins[i] for i in range(3)]
        # Must have some meaningful span
        if all(s > 0.01 for s in spans) and all(s < 1000 for s in spans):
            candidates.append((off, mins, maxs, spans))
if candidates:
    for off, mins, maxs, spans in candidates[:20]:
        print(f"  +{off:06X}: spans=({spans[0]:.2f}, {spans[1]:.2f}, {spans[2]:.2f}) "
              f"range=({mins[0]:.2f}..{maxs[0]:.2f}, {mins[1]:.2f}..{maxs[1]:.2f}, {mins[2]:.2f}..{maxs[2]:.2f})")
    if len(candidates) > 20:
        print(f"  ... and {len(candidates)-20} more")
else:
    print("  No plausible f32 runs found!")

# Strategy 2: Scan the CHUNKS (sections 1-86) for the pool
print("\n--- Scanning mesh CHUNKS 1-86 for 86-vertex f32 pool ---")
for sec_idx in range(1, min(87, n)):
    off = sum(sizes[:sec_idx])
    chunk = d[sect_off + off : sect_off + off + sizes[sec_idx]]
    for coff in range(0, len(chunk) - 1032, 4):
        ok, mins, maxs = is_plausible_f32(chunk, coff, 86)
        if ok:
            spans = [maxs[i] - mins[i] for i in range(3)]
            if all(s > 0.01 for s in spans) and all(s < 1000 for s in spans):
                print(f"  Chunk {sec_idx} +{coff:06X}: spans=({spans[0]:.2f}, {spans[1]:.2f}, {spans[2]:.2f})")
print("  Done scanning chunks")

# Strategy 3: Check the gap regions
print("\n--- Checking key gap regions ---")
gaps = [
    ("Collision stub→Ptr table", 0x36D0, 0x3748),
    ("Last poly rec→Mesh recs", 0x3B08, 0x3B08 + 0x34),  # first mesh rec
    ("After mesh recs→C-blocks", 0x3B08 + 86*0x34, 0x4C80),
    ("After C-blocks", 0x4C80 + 100, len(sect)),
]
for name, start, end in gaps:
    end = min(end, len(sect))
    print(f"  {name}: 0x{start:X}..0x{end:X} ({end-start} bytes)")
    for off in range(start, min(end - 1032, end), 4):
        ok, mins, maxs = is_plausible_f32(sect, off, 86)
        if ok:
            spans = [maxs[i] - mins[i] for i in range(3)]
            if all(s > 0.01 for s in spans):
                print(f"    FOUND at +{off:06X}: spans=({spans[0]:.2f}, {spans[1]:.2f}, {spans[2]:.2f})")

# Strategy 4: look for the pool in the C-block region more carefully
print("\n--- C-block region analysis ---")
cblock_start = 0x4C80
# The C-blocks are for each mesh. The first few bytes
# Let's look at the beginning of C-blocks
print(f"  C-block region starts at 0x{cblock_start:X}")
for i in range(8):
    v = struct.unpack_from(">I", sect, cblock_start + i*4)[0]
    f = struct.unpack_from(">f", sect, cblock_start + i*4)[0]
    print(f"    +{cblock_start + i*4:06X}: u32={v:10d} (0x{v:08X})  f={f:.4f}")

# Strategy 5: Check the RE Sector for pointers to the pool
print("\n--- Checking RELC for any pointer that might reference the pool ---")
p = sect_off + sum(sizes)
relc_entries = []
while p + 8 <= len(d):
    if d[p:p+4] == b"CLER":
        sz = struct.unpack_from(">I", d, p + 4)[0]
        print(f"  RELC at file+{p:#x}, size={sz}")
        for i in range(sz // 8):
            off_in_sect = struct.unpack_from(">I", d, p + 8 + 8*i)[0]
            target_sec = struct.unpack_from(">I", d, p + 8 + 8*i + 4)[0]
            relc_entries.append((off_in_sect, target_sec))
            # Look for any unusual target sections or offsets
            if target_sec == 0 and not (0x3B08 <= off_in_sect <= 0x4C4C) and not (0x36C0 <= off_in_sect <= 0x36D4):
                # Unusual: points into SECT but not at known mesh-record or collision fields
                what = struct.unpack_from(">I", sect, off_in_sect)[0]
                print(f"    UNUSUAL: off=0x{off_in_sect:04X} -> sec {target_sec}: value at SECT=0x{what:08X}")
        break
    p += 4
print(f"  Total RELC entries: {len(relc_entries)}")

# Strategy 6: Try s16 fixed-point at various scales across the SECT
print("\n--- s16 fixed-point scan (various scales) ---")
for div in [8, 16, 32, 64, 128, 256]:
    for off in range(0, min(len(sect) - 86*6, len(sect)), 2):
        ok, mins, maxs, nz = is_plausible_s16(sect, off, 86, div)
        if ok and nz < 86 and all(abs(mins[i]) < 200 and abs(maxs[i]) < 200 for i in range(3)):
            spans = [maxs[i] - mins[i] for i in range(3)]
            if all(s > 0.5 for s in spans):
                print(f"  +{off:06X} /{div}: spans=({spans[0]:.1f}, {spans[1]:.1f}, {spans[2]:.1f}) "
                      f"range y=[{mins[2]:.1f}..{maxs[2]:.1f}] zeros={nz}")
                break  # just one per div for now

# Strategy 7: Look for the pool as part of a larger structure
# The C-block region might contain the pool. Let's look more carefully.
# From format notes: "The C-block region can be larger than the triples"
# "the large world meshes (5, 6, 8 in SB1_01) carry the Collision/Database wall arrays after their index records"
# So maybe the pool is embedded in the C-block of one of the large meshes?

# Let me find the mesh records and see their C-block details
print("\n--- Mesh record C-block details for large meshes ---")
# Mesh records at SECT+0x3B08 + 0x34*k
for k in [5, 6, 8]:
    moff = 0x3B08 + 0x34 * k
    C = struct.unpack_from(">I", sect, moff + 0x20)[0]
    D = struct.unpack_from(">I", sect, moff + 0x24)[0]
    F = struct.unpack_from(">I", sect, moff + 0x2C)[0]
    G = struct.unpack_from(">I", sect, moff + 0x30)[0]
    print(f"  Mesh {k}: C=0x{C:X} D={D} F={F} G=0x{G:08X}")
    # Check for valid f32 pool at C offset
    if C + 1032 <= len(sect):
        ok, mins, maxs = is_plausible_f32(sect, C, 86)
        if ok:
            spans = [maxs[i] - mins[i] for i in range(3)]
            print(f"    f32 check: spans=({spans[0]:.2f}, {spans[1]:.2f}, {spans[2]:.2f})")
        # Also check right after C-block (= C+D)
        end_off = C + D
        if end_off + 1032 <= len(sect):
            ok2, mins2, maxs2 = is_plausible_f32(sect, end_off, 86)
            if ok2:
                spans2 = [maxs2[i] - mins2[i] for i in range(3)]
                print(f"    after C-block (+{end_off:X}): spans=({spans2[0]:.2f}, {spans2[1]:.2f}, {spans2[2]:.2f})")

# Strategy 8: Check inside each mesh chunk for f32 data (not just s16 vertices)
print("\n--- Checking mesh chunks for f32 data ---")
for sec_idx in [1, 2, 3, 5, 6, 8, 85, 86]:
    if sec_idx >= n:
        continue
    off = sum(sizes[:sec_idx])
    chunk = d[sect_off + off : sect_off + off + sizes[sec_idx]]
    # Scan chunk for any f32 data
    for coff in range(0, min(len(chunk) - 100, len(chunk)), 4):
        ok, mins, maxs = is_plausible_f32(chunk, coff, 20)  # just 20 triples
        if ok:
            spans = [maxs[i] - mins[i] for i in range(3)]
            if all(s > 0.1 for s in spans) and all(abs(mins[i]) < 500 for i in range(3)):
                print(f"  Chunk {sec_idx} +{coff:06X}: 20-vertex f32 spans=({spans[0]:.2f}, {spans[1]:.2f}, {spans[2]:.2f})")
                break

# Strategy 9: The pool might be at the END of the SECT or embedded in the C-block structure
# Let's look at the last few hundred bytes of the SECT
print("\n--- End of SECT ---")
tail_start = max(0, len(sect) - 200)
for i in range(tail_start, len(sect), 4):
    v = struct.unpack_from(">I", sect, i)[0]
    f = struct.unpack_from(">f", sect, i)[0]
    if v != 0:
        print(f"  +{i:06X}: u32=0x{v:08X} f={f:.4f}")

# Strategy 10: Maybe the pool is NOT in f32 but in the s16/64 format used by regular meshes
# Let's check: 86 vertices × 6 bytes = 516 bytes
print("\n--- Looking for 86-vertex s16 pool (516 bytes) ---")
for off in range(0, len(sect) - 516, 2):
    ok, mins, maxs, nz = is_plausible_s16(sect, off, 86, 64.0)
    if ok and nz < 43:  # at most half zeros
        spans = [maxs[i] - mins[i] for i in range(3)]
        if all(s > 0.5 for s in spans) and all(abs(mins[i]) < 200 for i in range(3)):
            print(f"  +{off:06X} /64: spans=({spans[0]:.1f}, {spans[1]:.1f}, {spans[2]:.1f}) "
                  f"range y=[{mins[2]:.1f}..{maxs[2]:.1f}] zeros={nz}")

# Strategy 11: Check the pointer table values more carefully
# ptr[87] = 0x39E8 — let's check what's there
print("\n--- Pointer table entry 87: 0x39E8 ---")
for i in range(16):
    v = struct.unpack_from(">I", sect, 0x39E8 + i*4)[0]
    f = struct.unpack_from(">f", sect, 0x39E8 + i*4)[0]
    print(f"  +{0x39E8 + i*4:04X}: u32=0x{v:08X} f={f:.4f}")

# Strategy 12: Dump the entire 0x4C80..0x6000 range as potential pool
print("\n--- C-block region sample ---")
# Let's look at the area after the C-blocks end
# The C-blocks end varies by mesh. Let's find the max C+D
max_cend = 0
for k in range(86):
    moff = 0x3B08 + 0x34 * k
    C = struct.unpack_from(">I", sect, moff + 0x20)[0]
    D = struct.unpack_from(">I", sect, moff + 0x24)[0]
    max_cend = max(max_cend, C + D)
print(f"Max C-block end: 0x{max_cend:X}")
# Look at what's right after
for i in range(16):
    off = max_cend + i*4
    v = struct.unpack_from(">I", sect, off)[0]
    f = struct.unpack_from(">f", sect, off)[0]
    print(f"  +{off:06X}: u32=0x{v:08X} f={f:.4f}")

# Also check if there's a material name gap after the C-blocks
# The format notes say "material-name gaps between blocks"
# Maybe the pool is in the region between C-blocks or after them
print("\n--- Material name gaps after C-blocks ---")
for k in range(min(10, 86)):
    moff = 0x3B08 + 0x34 * k
    C = struct.unpack_from(">I", sect, moff + 0x20)[0]
    D = struct.unpack_from(">I", sect, moff + 0x24)[0]
    gap_off = C + D
    # Read the material name at gap
    if gap_off + 0x20 <= len(sect):
        gap = sect[gap_off:gap_off + 0x20]
        name = gap.split(b"\x00")[0].decode("latin1", errors="replace")
        print(f"  Mesh {k}: C-block ends at 0x{gap_off:X}, material: '{name}'")
