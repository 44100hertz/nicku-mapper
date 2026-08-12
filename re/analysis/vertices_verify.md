# NTU GC Level Mesh — Vertex/Geometry Verification Report

**File**: `nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb`
(222192 B; SECT @ file 0x594, size 0x34680; 87 HDRX chunks)
**Date**: this session. **Method**: raw byte analysis + DOL (main.dol) loader archaeology.
**Status**: structure of the two per-mesh data regions **verified**; the exact
position-quantization and index↔array binding is **partially verified**, with the
remaining piece needing either the loader code or a render-verification pass.

---

## 0. Executive summary

- The user's correction is **confirmed at the data level**: the `Collision` SYMB
  chunk of the level file is an **empty stub** (`{0, 1, ptr→0x36CC, ptr→0x36D0}`
  with `0x36D0 = 0`, all pointers in the RELC list). There is no separate
  "wall array" block in the SECT — the old 5-byte wall interpretation
  (0x655A/0x759B/0xCEAD "boundaries") is definitively wrong: those offsets are
  literally the NameHashes of `SkeletonHeader` (0x655A), `Database` (0x759B) and
  `Header` (0xCEAD).
- Level geometry = **86 meshes** (`W0C0M0..85` = World0 Camera0 MeshN), each
  described by a 52-byte record, with TWO data regions:
  - a **C-block in chunk 0** (offsets tiling `[0x4C80, 0x1F7C0)`),
  - a **per-mesh chunk 1..86**.
- The two regions carry **different layouts depending on record flag `G`**:
  - `G = 0x06020202` (the common case): chunk = u16 index stream + UV pair
    array + s16 tail; C-block = `[0x98][u16 F][F×3 bytes]` (u8 "triples").
  - `G = 0x06030202 / 0x06030203` (meshes 5,6,7,8,9,13,38,45,69): chunk
    **starts with a large s16×3 vertex-position array** (mesh13: 1024 verts,
    mesh6: 816 verts); C-block = same `[0x98][u16 F][F×3]` plus an **extra**
    index stream after it.
- Verified: the u8 C-block "triples" decode as **quantized (x,y,z) positions**
  for flat geometry (the road mesh 1 gives an exactly-flat 2.0 × 8.9 unit slab at
  y=0 matching its record bounds — see §5). Their three slots behave like
  (x, y, z) with slot-b mostly 0 on floors.

---

## 1. Container recap (verified, unchanged)

TSFB → HDRX (87 chunk sizes that tile SECT exactly) → SECT → RELC (530
relocation pairs; relocates 0x30, 0x34, 0x36C8, 0x36CC, 0x374C.. and every mesh
record field C) → SYMB (92 names: `Header` @+0x00, `Database` @+0x2C,
`SkeletonHeader`(name) @+0x40, `Skeleton` @+0x70, `Materials` @+0x1D40,
`Collision` @+0x36C0, `W0C0M0..85` @ 0x3B08+0x34k).

## 2. Mesh record (52 bytes) — VERIFIED layout

At `SECT+0x3B08 + 0x34*k` (k = 0..85; W0C0M85 @ 0x4C4C):

```
+0x00..0x0C  f32 x0, x1, z0, z1     (bounding box, NOT necessarily min<max!)
+0x10        u32 0
+0x14        u32 A                  = UV-array offset within chunk (G=06020202)
+0x18        u32 B                  = position-array byte size (G=060302xx)
+0x1C        u32 0
+0x20        u32 C                  = C-block offset in chunk 0
+0x24        u32 D                  = C-block byte size
+0x28        u32 E                  = C + D (end offset)
+0x2C        u32 F                  = C-block record count (u8 triples)
+0x30        u32 G                  = format flag (0x06020202 / 0x06030202 / 0x06030203)
```

Evidence for A = UV-array offset: mesh0 A=0x180=384 → chunk1+384 = 0x1F960
where the u16-pair array starts ✓; mesh2 A=0x5E0=1504 → chunk3+1504 = 0x20140 ✓;
mesh5 A=0x720 → chunk6+0x720 = 0x21160 shows `00 55 ff a0 ...` (u, v) pairs ✓.
Evidence for B = position-array bytes (G=060302xx): mesh13 B=0x1800=6144 =
1024 s16×3 verts found at the head of chunk14 ✓; mesh6 B=0x1320=4896 = 816
s16×3 verts at head of chunk7 ✓ (see §4).

## 3. C-block — VERIFIED header + triple stream

Every one of the 86 C-blocks begins:

```
[0x98][u16 F BE][F × 3 bytes]
```

`0x98` is a fixed marker; the u16 equals record field F for **all 86 meshes**
(checked: 0x0139, 0x002F, 0x0379, 0x0043, 0x017C, 0x06D7, 0x06D9, 0x0303,
0x0925, 0x038E, ... all match). The F×3 payload is a stream of 3-byte records;
slots behave like (x, y, z) quantized values (§5). For G=06020202 meshes the
block is `3 + F×3 + ~2..31 pad` (D matches to within padding). For
G=060302xx meshes an **extra stream** follows the F×3 triples (mesh5: +3512 B of
u16-triple records; mesh6: +1778 B of u8 triples; mesh13: +4333 B).

C-blocks tile chunk0 `[0x4C80, 0x1F7C0)` with **0x20-byte gaps containing the
mesh's material name** ("path01", "RoadLines", "sand01", "09_-_Default", ...).

## 4. Chunks 1..86 — two layouts by flag G

**G = 0x06020202** (meshes 0,1,2,3,4,10,11,12,14..44 except 38, 46..86 except
69, ...):
```
chunk k+1 = [u16-triple index stream: A bytes]
          + [u16 (u, v) UV-pair array: starts at chunk+A]   v mostly 0xFFxx (flipped)
          + [s16 tail][pad to 32-byte alignment]
```
Example mesh0 chunk1 (608 B): 64 triples (384 B = A) + 48 UV pairs (192 B) +
`FF FF` marker + 6 s16 + pad. The u16 triples are `(posIdx, uvIdx, nrmIdx)` with
posIdx up to **1161** (mesh0), uvIdx up to 968, nrmIdx 0 / 5 / 0xFFDB(-37).
Across the file: pos ≤ 2335, uv ≤ 1584, nrm ≤ 355 + the -37 marker.

**G = 0x06030202 / 0x06030203** (meshes 5,6,7,8,9,13,38,45,69):
```
chunk k+1 = [s16×3 vertex-position array: B bytes]   (smooth, local coords)
          + [small extra region]
```
Verified: chunk14 (mesh13) head `03fc 048b 003b | 03f6 0479 0000 | ...` is a
smooth 1024-vertex s16×3 array exactly B=6144 bytes; chunk7 (mesh6) head
`015d 0391 0042 | 015c 0391 ...` smooth 816-vertex array exactly B=4896 bytes.
These arrays are NOT the world-position array (values are per-mesh local grid
coordinates, see risks).

## 5. Position decode — VERIFIED for flat case, quantization formula unproven

Hypothesis H (best fit): u8 triple `(a, b, c)` = `(x, y, z)` quantized per-mesh,
with record floats = `(x0, x1, z0, z1)` (use min/max per pair; the pairs are
unordered in some records — e.g. mesh55 30.18/19.28):

```
x = x0 + a * (x1 - x0) / Amax      (Amax = max slot-a of this mesh)
z = z0 + c * (z1 - z0) / Cmax
y = b * YSCALE                     (YSCALE unknown; b==0 on floors)
```

Evidence:
- **mesh1 (road)**: slot-b ≡ 0 (exactly one distinct value), slot-a 0..23,
  slot-c 0..20 → decode = perfectly flat y=0 slab, x 9.92..11.91 (2.0 wide),
  z 0.08..8.98 (8.9 long), median edge ≈ 0.9 units. A textbook flat road.
- mesh0: flat-ish (y 0..6), x 9.94..10.76, z -0.29..9.31; median edge 1.05.
- Player spawns (SBL1_Ents.ini: (1.29, -0.005, 7.58), (2.14, -0.005, 6.08),
  (1.18, -0.005, 6.20)) sit on y=0 and are covered by the (x0,x1,z0,z1)
  bounding boxes of floor meshes 17,18,21,22,23,35,36,37,69,70,77,78 — the
  floor is at y=0 in world units, consistent with slot-b=0 → y=0.
- The big s16 arrays (§4) scale to the same world volume at ~1/32 (mesh13 run:
  x -7.8..34.9, z -7.9..36.6 at /32; level z_max = 36.375 = SECT+0x1C[3]).

What remains unproven: the exact quantization formula (normalized-per-axis vs
fixed scale), YSCALE for slot-b, and whether the u16 index streams in
G=06020202 chunks index the §4 s16 arrays (which are stored in OTHER meshes'
chunks) or a still-unidentified shared array.

## 6. DOL loader archaeology (main.dol)

- SDA bases found: **r13 = 0x8019D620**, r2 = 0x801AD620 (set in `__start` at
  0x80003108-0x80003114). All of sections 9/10 is addressed via r13; this
  explains most "unreferenced strings".
- The level-name/manifest strings at 0x80050600 ("jimmyworld_demolevel",
  "danny01".., "NickToonWorld_DannyL1"..) are referenced ONLY by data tables:
  table A @ 0x80195928 (level names), table B @ 0x800B7FF8, and the per-level
  manifest records at 0x80051A40..0x80051E80 (file paths like
  "Data/JimmyNeutronLab/RenderParams.trb"). **No code references these tables
  via lis+addi, u32 pointers, or r13** — the loading-state strings
  (LOADINGSTATE_Collision @ 0x80050098 etc.) are likewise dead data in this
  build. The TMDL symbol-name strings ("SkeletonHeader"/"Skeleton"/"Collision"/
  "TMesh" @ 0x800AF028..) and the degenerate-face warning @ 0x800A9E04 are also
  unreferenced.
- No TSFB magic-compare, no SYMB hash immediates (0x6712/0x759B/0xCEAD/...), no
  `mulli 0x34`, no u16-triple reader pattern were found that would pin the mesh
  parser. Conclusion: **the mesh-parsing code in this DOL is not reachable
  through any string/symbol/hash anchor that survives in the binary** — it
  either lives behind function-pointer tables only, or the strings/asserts were
  compiled out. The file-format decoding therefore has to be validated
  structurally (this report) and by rendering.

## 7. Deliverables

- `analysis/cblock_hypothesis.obj` — OBJ export of meshes 1,0,2,35,55,63,24
  under hypothesis H (u8 triples → (x,y,z), y raw). Viewer-ready after applying
  the repo's `(x, -y, -z)` convention; edge-outline only.
- Tools added under `asset-extract/tools/`:
  `verify_cblocks.py` (header check, 86/86 OK), `chunk_analyze.py`,
  `cblocks.py`, `decode_hypothesis.py`, `final_check.py`, `scan_all.py`,
  `s16run.py`, `find_all_posarrays.py`, `remainder.py`, `dump_sect.py`,
  `dis_ram.py`, `dump_ram.py`, `find_u32.py`, `find_ptrs_to_range.py`,
  `probe_lis.py`, `xrefs.py`, `sda_refs.py`, `ptrchain.py`,
  `find_index_reader.py`.

## 8. Residual risks / open questions

1. **Quantization formula** for the u8 triples is inferred, not proven; YSCALE
   for slot-b unknown (0 = floor is certain, absolute scale is not).
2. **u16 index streams ↔ s16 arrays binding**: the G=06020202 chunks carry u16
   (posIdx ≤ 2335) streams but their positions are not visibly in those chunks;
   the only large position arrays found live in the G=060302xx chunks (stored in
   *other* meshes' chunk numbers). Either the renderer walks the whole file's
   arrays as one global pool, or an array region is still unidentified.
3. The record float pairs are unordered (x0>x1 in meshes 44..62, 63..85) — the
   min/max convention must be used.
4. Mesh 19 / 61 records have A=0, B=0x20 and G=0x06020201 (odd flags) — tiny
   degenerate meshes; handle defensively.
5. `main.dol` loader not found (see §6) — recommend validating by rendering the
   OBJ in the existing viewer and comparing against entity positions, then
   refining YSCALE/quantization until entities sit on surfaces.
