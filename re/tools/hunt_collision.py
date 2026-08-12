#!/usr/bin/env python3
"""hunt_collision.py — Cross-reference polygon bounding boxes to find the 86-vertex pool.

The SECT+0x38AC region in SBWorld_Detail_Level01_01.trb holds a BSP tree and
10 polygon records, each with a 4×f32 bounding box (min_x, max_x, min_z, max_z).
The polygons reference indices 0..85 (86 unique vertices) from a shared pool.
The pool location is unknown — this script uses the polygon boxes as spatial
constraints to search the SECT and mesh chunks for plausible vertex data.

Approach:
1. Parse the BSP tree nodes (0x38AC-0x38FB) and polygon records (0x38FC-0x3B08)
2. Extract the 4×f32 bounding box for each polygon
3. Search the SECT for any block that yields 86 vertices within those boxes
4. Try multiple encodings: f32 triples, s16/64 fixed-point, s8 quantized
5. Score each candidate by how many vertices fall in at least one poly's box
"""
import struct
import math
import sys
from collections import defaultdict

TRB_PATH = "/home/cyan/code/nicku-mapper/asset-extract/nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb"


def parse_container(d):
    """Return (sect_bytes, chunk_sizes, sect_offset)."""
    hdrx_size = struct.unpack_from(">I", d, 0x10)[0]
    n = struct.unpack_from(">I", d, 0x18)[0]
    sizes = [struct.unpack_from(">I", d, 0x20 + 16 * i)[0] for i in range(n)]
    sect_off = hdrx_size + 20 + 8
    sect = d[sect_off : sect_off + sizes[0]]
    return sect, sizes, sect_off


def parse_bsp_tree(sect):
    """Parse the BSP tree at SECT+0x38AC.

    Each internal node is 40 bytes: [child_a u32][4xf32 box_a][child_b u32][4xf32 box_b].
    Leaf nodes have child=0 and the box describes a polygon. Polygon data follows
    immediately after the leaf box: [u32 count][count x u16 indices][u16 term][u32 next].

    Returns: (nodes, polygons) where:
      nodes = [(offset, child_a, box_a, child_b, box_b), ...]
      polygons = [(offset, box, indices), ...]
    """
    # First, parse all BSP nodes starting at 0x38AC (40 bytes each)
    nodes = []
    i = 0x38AC
    while i < 0x38FC:  # 0x38FC is where polygon 0 data starts
        if i + 40 > len(sect):
            break
        child_a = struct.unpack_from(">I", sect, i)[0]
        ba = tuple(struct.unpack_from(">f", sect, i + 4 + j * 4)[0] for j in range(4))
        child_b = struct.unpack_from(">I", sect, i + 20)[0]
        bb = tuple(struct.unpack_from(">f", sect, i + 24 + j * 4)[0] for j in range(4))
        nodes.append((i, child_a, ba, child_b, bb))
        i += 40

    # Parse polygon records from the region 0x38FC..0x3B08
    # These are interleaved with node boxes because internal nodes link to them
    polygons = []
    # Known polygon data offsets (from rec38ac.py analysis)
    poly_data_offsets = [0x38FC, 0x394C, 0x396C, 0x399C, 0x39D0, 0x3A24, 0x3A54, 0x3AA4, 0x3AC8, 0x3AF0]
    # Each polygon is preceded by 16 bytes (4×f32 box)
    for poff in poly_data_offsets:
        box_off = poff - 16
        box = tuple(struct.unpack_from(">f", sect, box_off + j * 4)[0] for j in range(4))
        count = struct.unpack_from(">I", sect, poff)[0]
        indices = []
        for j in range(count):
            idx = struct.unpack_from(">H", sect, poff + 4 + j * 2)[0]
            indices.append(idx)
        polygons.append((poff, box, indices))

    return nodes, polygons


def extract_poly_boxes(polygons):
    """Return list of (min_x, max_x, min_z, max_z) for each polygon.

    The 4-float box is interpreted as (min_x, max_x, min_z, max_z) per the task.
    """
    boxes = []
    for poff, box, indices in polygons:
        # box = (f0, f1, f2, f3) → (min_x, max_x, min_z, max_z)
        min_x = box[0]
        max_x = box[1]
        min_z = box[2]
        max_z = box[3]
        boxes.append((min_x, max_x, min_z, max_z))
    return boxes


def box_union(boxes):
    """Union of all bounding boxes."""
    all_min_x = min(b[0] for b in boxes)
    all_max_x = max(b[1] for b in boxes)
    all_min_z = min(b[2] for b in boxes)
    all_max_z = max(b[3] for b in boxes)
    return all_min_x, all_max_x, all_min_z, all_max_z


def vertex_in_any_box(x, z, boxes):
    """Check if (x, z) falls inside at least one polygon's box."""
    for min_x, max_x, min_z, max_z in boxes:
        if min_x - 0.5 <= x <= max_x + 0.5 and min_z - 0.5 <= z <= max_z + 0.5:
            return True
    return False


def scan_f32(sect, boxes, stride=12):
    """Scan SECT for 86-vertex f32 pools."""
    candidates = []
    total = 86 * stride  # default: 12 bytes per vertex (x, y, z)
    for off in range(0, len(sect) - total, 4):
        in_box = 0
        xs, zs, ys = [], [], []
        bad = False
        for vi in range(86):
            x = struct.unpack_from(">f", sect, off + vi * stride)[0]
            y = struct.unpack_from(">f", sect, off + vi * stride + 4)[0]
            z = struct.unpack_from(">f", sect, off + vi * stride + 8)[0]
            if math.isnan(x) or math.isinf(x) or abs(x) > 1e6:
                bad = True
                break
            xs.append(x)
            zs.append(z)
            ys.append(y)
            if vertex_in_any_box(x, z, boxes):
                in_box += 1
        if bad:
            continue
        xspan = max(xs) - min(xs)
        zspan = max(zs) - min(zs)
        yspan = max(ys) - min(ys)
        # Must have non-trivial spans and high box coverage
        if xspan > 1.0 and zspan > 1.0 and in_box >= 75:
            candidates.append((off, "f32", stride, in_box,
                              min(xs), max(xs), min(zs), max(zs), min(ys), max(ys),
                              xspan, zspan, yspan))
    return candidates


def scan_s16(sect, boxes, div=64.0):
    """Scan SECT for 86-vertex s16 fixed-point pools."""
    candidates = []
    stride = 6  # (x, z, y)
    total = 86 * stride
    for off in range(0, len(sect) - total, 2):
        in_box = 0
        xs, zs, ys = [], [], []
        bad = False
        zero_count = 0
        for vi in range(86):
            raw_x = struct.unpack_from(">h", sect, off + vi * stride)[0]
            raw_z = struct.unpack_from(">h", sect, off + vi * stride + 2)[0]
            raw_y = struct.unpack_from(">h", sect, off + vi * stride + 4)[0]
            if raw_x == 0 and raw_y == 0 and raw_z == 0:
                zero_count += 1
            x = raw_x / div
            z = raw_z / div
            y = raw_y / div
            if abs(x) > 1000 or abs(z) > 1000:
                bad = True
                break
            xs.append(x)
            zs.append(z)
            ys.append(y)
            if vertex_in_any_box(x, z, boxes):
                in_box += 1
        if bad or zero_count > 40:
            continue
        xspan = max(xs) - min(xs)
        zspan = max(zs) - min(zs)
        yspan = max(ys) - min(ys)
        if xspan > 1.0 and zspan > 1.0 and in_box >= 70:
            candidates.append((off, f"s16/{div}", stride, in_box,
                              min(xs), max(xs), min(zs), max(zs), min(ys), max(ys),
                              xspan, zspan, yspan))
    return candidates


def scan_s8_quantized(sect, boxes, box_union_bounds):
    """Scan SECT for 86-vertex s8 quantized pools (3 bytes per vertex: x, y, z).

    The format notes (§4c) show s8 quantization against a mesh's own bbox:
      world_x = xmin + (s8x + 128) * (xmax - xmin) / 255
    For the shared collision pool, the bbox would be the union of all polygon boxes.
    """
    all_min_x, all_max_x, all_min_z, all_max_z = box_union_bounds
    candidates = []
    stride = 3  # (x, y, z)
    total = 86 * stride
    for off in range(0, len(sect) - total, 1):
        in_box = 0
        xs, zs, ys = [], [], []
        zero_count = 0
        for vi in range(86):
            raw_x = struct.unpack_from(">b", sect, off + vi * stride)[0]
            raw_y = struct.unpack_from(">b", sect, off + vi * stride + 1)[0]
            raw_z = struct.unpack_from(">b", sect, off + vi * stride + 2)[0]
            if raw_x == 0 and raw_y == 0 and raw_z == 0:
                zero_count += 1
            # Quantize using the overall bbox
            x = all_min_x + (raw_x + 128) * (all_max_x - all_min_x) / 255.0
            z = all_min_z + (raw_z + 128) * (all_max_z - all_min_z) / 255.0
            y = raw_y / 16.0  # guess for y scale
            xs.append(x)
            zs.append(z)
            ys.append(y)
            if vertex_in_any_box(x, z, boxes):
                in_box += 1
        if zero_count > 40:
            continue
        xspan = max(xs) - min(xs)
        zspan = max(zs) - min(zs)
        if xspan > 1.0 and zspan > 1.0 and in_box >= 65:
            candidates.append((off, "s8_quant", stride, in_box,
                              min(xs), max(xs), min(zs), max(zs), min(ys), max(ys),
                              xspan, zspan, max(ys) - min(ys)))
    return candidates


def scan_s8_4byte(sect, boxes, box_union_bounds):
    """Scan for 4-byte s8 records: (flag, x, y, z) — the per-mesh collision format."""
    all_min_x, all_max_x, all_min_z, all_max_z = box_union_bounds
    candidates = []
    stride = 4
    total = 86 * stride
    for off in range(0, len(sect) - total, 4):
        in_box = 0
        xs, zs, ys, flags = [], [], [], []
        for vi in range(86):
            flag = sect[off + vi * stride]
            raw_x = struct.unpack_from(">b", sect, off + vi * stride + 1)[0]
            raw_y = struct.unpack_from(">b", sect, off + vi * stride + 2)[0]
            raw_z = struct.unpack_from(">b", sect, off + vi * stride + 3)[0]
            x = all_min_x + (raw_x + 128) * (all_max_x - all_min_x) / 255.0
            z = all_min_z + (raw_z + 128) * (all_max_z - all_min_z) / 255.0
            y = raw_y / 16.0
            xs.append(x)
            zs.append(z)
            ys.append(y)
            flags.append(flag)
            if vertex_in_any_box(x, z, boxes):
                in_box += 1
        xspan = max(xs) - min(xs)
        zspan = max(zs) - min(zs)
        if xspan > 1.0 and zspan > 1.0 and in_box >= 65:
            candidates.append((off, "s8_4byte(tag,x,y,z)", stride, in_box,
                              min(xs), max(xs), min(zs), max(zs), min(ys), max(ys),
                              xspan, zspan, max(ys) - min(ys)))
    return candidates


def scan_chunks(d, sect_off, sizes, boxes, n_chunks=86):
    """Scan each mesh chunk for 86-vertex pools."""
    all_candidates = []
    for sec_idx in range(1, min(n_chunks + 1, len(sizes))):
        off = sum(sizes[:sec_idx])
        chunk = d[sect_off + off : sect_off + off + sizes[sec_idx]]
        # f32 scan
        for cand in scan_f32(chunk, boxes):
            cand = (sec_idx, cand[0],) + cand[1:]
            all_candidates.append(cand)
        # s16 scan
        for cand in scan_s16(chunk, boxes, 64):
            cand = (sec_idx, cand[0],) + cand[1:]
            all_candidates.append(cand)
    return all_candidates


def verify_connectivity(vertices, polygons):
    """Check if vertices at polygon corners are shared (connected mesh).

    For each polygon, vertices referenced at its edges should be shared with
    adjacent polygons. Returns a score: shared edges / total edges.
    """
    # Build edge→polygons mapping
    edge_polys = defaultdict(set)
    for pi, (poff, box, indices) in enumerate(polygons):
        n = len(indices)
        for j in range(n):
            v1 = indices[j]
            v2 = indices[(j + 1) % n]
            edge = tuple(sorted([v1, v2]))
            edge_polys[edge].add(pi)

    total_edges = len(edge_polys)
    shared_edges = sum(1 for e, polys in edge_polys.items() if len(polys) >= 2)
    boundary_edges = total_edges - shared_edges
    return shared_edges, total_edges, boundary_edges


def dump_candidate_detail(sect, off, encoding, stride, in_box, ranges):
    """Dump the first few vertices of a candidate for inspection."""
    if "f32" in encoding:
        for vi in range(min(10, 86)):
            x = struct.unpack_from(">f", sect, off + vi * stride)[0]
            y = struct.unpack_from(">f", sect, off + vi * stride + 4)[0]
            z = struct.unpack_from(">f", sect, off + vi * stride + 8)[0]
            print(f"    v[{vi:2d}]: ({x:8.3f}, {y:8.3f}, {z:8.3f})")
    elif "s16" in encoding:
        div = float(encoding.split("/")[1]) if "/" in encoding else 64.0
        for vi in range(min(10, 86)):
            raw_x = struct.unpack_from(">h", sect, off + vi * stride)[0]
            raw_z = struct.unpack_from(">h", sect, off + vi * stride + 2)[0]
            raw_y = struct.unpack_from(">h", sect, off + vi * stride + 4)[0]
            print(f"    v[{vi:2d}]: raw=({raw_x:6d}, {raw_z:6d}, {raw_y:6d}) → ({raw_x/div:8.3f}, {raw_y/div:8.3f}, {raw_z/div:8.3f})")


def main():
    print("=" * 70)
    print("hunt_collision.py — Cross-reference polygon boxes → vertex pool search")
    print("=" * 70)

    # Load and parse
    with open(TRB_PATH, "rb") as f:
        d = f.read()

    sect, sizes, sect_off = parse_container(d)
    print(f"\nContainer: {len(sizes)} sections, SECT={len(sect)} bytes")

    # Parse BSP tree and polygons
    nodes, polygons = parse_bsp_tree(sect)
    print(f"\nBSP tree: {len(nodes)} nodes, {len(polygons)} polygon records")

    for i, (off, ca, ba, cb, bb) in enumerate(nodes):
        print(f"  Node {i} at 0x{off:04X}: child_a=0x{ca:08X} box_a={ba}")
        print(f"           child_b=0x{cb:08X} box_b={bb}")

    print(f"\nPolygon records:")
    all_indices = set()
    for pi, (poff, box, indices) in enumerate(polygons):
        all_indices.update(indices)
        print(f"  Poly[{pi}] at 0x{poff:04X}: box=({box[0]:.2f},{box[1]:.2f},{box[2]:.2f},{box[3]:.2f}) "
              f"count={len(indices)} indices={min(indices)}..{max(indices)}")

    print(f"\nAll referenced indices: {sorted(all_indices)} ({len(all_indices)} unique)")

    # Extract bounding boxes as (min_x, max_x, min_z, max_z)
    boxes = extract_poly_boxes(polygons)
    box_ub = box_union(boxes)
    print(f"\nPolygon boxes (min_x, max_x, min_z, max_z):")
    for pi, b in enumerate(boxes):
        print(f"  Poly[{pi}]: ({b[0]:.2f}, {b[1]:.2f}, {b[2]:.2f}, {b[3]:.2f})")
    print(f"  Union: x=[{box_ub[0]:.2f}..{box_ub[1]:.2f}] z=[{box_ub[2]:.2f}..{box_ub[3]:.2f}]")

    # Connectivity check (before finding vertices)
    shared, total, boundary = verify_connectivity(None, polygons)
    print(f"\nPolygon connectivity: {shared}/{total} edges shared, {boundary} boundary edges")

    # === SEARCH SECT for vertex pools ===
    print(f"\n{'='*70}")
    print("SEARCHING SECT for 86-vertex pool...")
    print(f"{'='*70}")

    print("\n--- f32 format (12 bytes/vertex) ---")
    f32_candidates = scan_f32(sect, boxes)
    if f32_candidates:
        for cand in f32_candidates[:5]:
            off, enc, stride, in_box, *ranges = cand
            xmin, xmax, zmin, zmax, ymin, ymax, xs, zs, ys = ranges
            print(f"  +{off:06X} [{enc}]: in_box={in_box}/86 "
                  f"x=[{xmin:.2f}..{xmax:.2f}] z=[{zmin:.2f}..{zmax:.2f}] y=[{ymin:.2f}..{ymax:.2f}]")
            dump_candidate_detail(sect, off, enc, stride, in_box, ranges)
            print()
    else:
        print("  No candidates found.")

    print("\n--- s16/64 fixed-point (6 bytes/vertex) ---")
    s16_candidates = scan_s16(sect, boxes, 64)
    if s16_candidates:
        for cand in s16_candidates[:5]:
            off, enc, stride, in_box, *ranges = cand
            xmin, xmax, zmin, zmax, ymin, ymax, xs, zs, ys = ranges
            print(f"  +{off:06X} [{enc}]: in_box={in_box}/86 "
                  f"x=[{xmin:.2f}..{xmax:.2f}] z=[{zmin:.2f}..{zmax:.2f}] y=[{ymin:.2f}..{ymax:.2f}]")
            dump_candidate_detail(sect, off, enc, stride, in_box, ranges)
            print()
    else:
        print("  No candidates found.")

    print("\n--- s8 quantized format (3 bytes/vertex) ---")
    s8_candidates = scan_s8_quantized(sect, boxes, box_ub)
    if s8_candidates:
        for cand in s8_candidates[:5]:
            off, enc, stride, in_box, *ranges = cand
            xmin, xmax, zmin, zmax, ymin, ymax, xs, zs, ys = ranges
            print(f"  +{off:06X} [{enc}]: in_box={in_box}/86 "
                  f"x=[{xmin:.2f}..{xmax:.2f}] z=[{zmin:.2f}..{zmax:.2f}] y=[{ymin:.2f}..{ymax:.2f}]")
    else:
        print("  No candidates found.")

    print("\n--- s8 4-byte (flag,x,y,z) format ---")
    s8_4_candidates = scan_s8_4byte(sect, boxes, box_ub)
    if s8_4_candidates:
        for cand in s8_4_candidates[:5]:
            off, enc, stride, in_box, *ranges = cand
            xmin, xmax, zmin, zmax, ymin, ymax, xs, zs, ys = ranges
            print(f"  +{off:06X} [{enc}]: in_box={in_box}/86 "
                  f"x=[{xmin:.2f}..{xmax:.2f}] z=[{zmin:.2f}..{zmax:.2f}] y=[{ymin:.2f}..{ymax:.2f}]")
    else:
        print("  No candidates found.")

    # === SEARCH CHUNKS ===
    print(f"\n{'='*70}")
    print("SEARCHING MESH CHUNKS (sections 1..86) for 86-vertex pool...")
    print(f"{'='*70}")

    chunk_cands = scan_chunks(d, sect_off, sizes, boxes)
    if chunk_cands:
        print(f"\nFound {len(chunk_cands)} chunk candidates:")
        for cand in chunk_cands[:10]:
            sec_idx = cand[0]
            off = cand[1]
            enc = cand[2]
            stride = cand[3]
            in_box = cand[4]
            xmin, xmax, zmin, zmax, ymin, ymax, xs, zs, ys = cand[5:14]
            print(f"  Chunk {sec_idx} +{off:06X} [{enc}]: in_box={in_box}/86 "
                  f"x=[{xmin:.2f}..{xmax:.2f}] z=[{zmin:.2f}..{zmax:.2f}] y=[{ymin:.2f}..{ymax:.2f}]")
        if len(chunk_cands) > 10:
            print(f"  ... and {len(chunk_cands) - 10} more")
    else:
        print("  No chunk candidates found.")

    # === ADDITIONAL: Check key regions ===
    print(f"\n{'='*70}")
    print("ADDITIONAL CHECKS")
    print(f"{'='*70}")

    # Check if the polygon boxes themselves ARE the vertex pool
    # (just the box corners as vertices — 10 boxes × 2 distinct corners each = 20 points)
    # But we need 86 vertices, not 20

    # Check the C-block region for suspicious data
    print("\n--- C-block region (0x4C80+) scan for 86-vertex data ---")
    cblock_sect = sect[0x4C80:]
    cblock_f32 = scan_f32(cblock_sect, boxes)
    if cblock_f32:
        for cand in cblock_f32[:3]:
            off, enc, stride, in_box, *ranges = cand
            xmin, xmax, zmin, zmax, ymin, ymax, xs, zs, ys = ranges
            print(f"  C-block +{off:06X} [f32]: in_box={in_box}/86 "
                  f"x=[{xmin:.2f}..{xmax:.2f}] z=[{zmin:.2f}..{zmax:.2f}]")
            dump_candidate_detail(cblock_sect, off, enc, stride, in_box, ranges)
    else:
        print("  No f32 candidates in C-block region.")

    # Check the material matrix region for f32 data that might be the pool
    print("\n--- Material region (0x004C..0x36C0) for vertex-like f32 data ---")
    # The f32 data at ~0x4200 showed promising ranges. Let's check more carefully.
    material_region = sect[0x4200:0x4600]
    print(f"  Checking 0x4200..0x4600 ({len(material_region)} bytes)")
    for off in range(0, min(len(material_region) - 86*12, len(material_region)), 4):
        in_box = 0
        xs, zs = [], []
        bad = False
        for vi in range(86):
            if off + vi*12 + 8 >= len(material_region):
                bad = True
                break
            x = struct.unpack_from(">f", material_region, off + vi*12)[0]
            z = struct.unpack_from(">f", material_region, off + vi*12 + 8)[0]
            if math.isnan(x) or math.isinf(x) or abs(x) > 1e5:
                bad = True
                break
            xs.append(x)
            zs.append(z)
            if vertex_in_any_box(x, z, boxes):
                in_box += 1
        if bad:
            continue
        xspan = max(xs) - min(xs)
        zspan = max(zs) - min(zs)
        if xspan > 1 and zspan > 1 and in_box >= 70:
            print(f"  Material +{off:06X}: in_box={in_box}/86 x=[{min(xs):.2f}..{max(xs):.2f}] z=[{min(zs):.2f}..{max(zs):.2f}]")

    # === Summary ===
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"Polygons: {len(polygons)}")
    print(f"Unique vertex indices: {len(all_indices)} (range {min(all_indices)}..{max(all_indices)})")
    print(f"Expected pool: 86 vertices = {86*12} bytes (f32) or {86*6} bytes (s16)")
    print(f"SECT size: {len(sect)} bytes (0x{len(sect):X})")
    print(f"Chunks: {len(sizes)-1} sections (total {sum(sizes[1:]):,} bytes)")

    if f32_candidates or s16_candidates or chunk_cands:
        print("\nBest candidates found — review above for manual verification.")
    else:
        print("\nNo strong candidates found. Possibilities:")
        print("  1. Pool uses a non-standard encoding (not f32 or s16/64)")
        print("  2. Pool is interleaved with other data (not contiguous 86 records)")
        print("  3. Pool is in a different file or section entirely")
        print("  4. Polygon boxes are not (min_x,max_x,min_z,max_z) — try other axis orders")


if __name__ == "__main__":
    main()
