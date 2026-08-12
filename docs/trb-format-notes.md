# Nicktoons Unite! (GameCube) — TRB / TTL reverse-engineering notes

Reverse-engineering notes for the level asset format used by *Nicktoons Unite!*
(GC, disc ID `P-GNOE`). The engine is the **Toshi engine** (Blue Tongue; also
used by de Blob, Barnyard, Nicktoons Battle for Volcano Island). Level files
live in `nicku-ntsc/P-GNOE/files/Data/<LevelName>/`:

- `*_Detail_Level*.trb` — **level world geometry** (the interesting files; a
  level is split into `_01`..`_08` parts, each with its own mesh set)
- `*.ttl` — texture list (same container)
- `SBL1_Ents.trb` / `*_Ents.trb` — compiled `*_Ents.ini` (entity positions
  stored verbatim as f32, verified 1:1 against the .ini)
- `levelnfo.trb`, `SkyData.trb`, `RenderParams.trb`, `Network.trb` — tiny
  TSFB containers useful for learning the container by heart

**Status (2025 session):** container fully decoded; per-mesh records fully
decoded; the per-chunk u16 triplet streams are **verified per-mesh vertex
pools** — each 6-byte record is one `(x, z, y)` fixed-point vertex at 1/64
scale; the FACES come from the record's 0x98 index block (indexed GX
triangle strip, see §3 — the earlier "no shared pools / raw coordinates"
note was about the
pool itself, which is correct; the strip's indices live in the 0x98 block,
not in the pool). `tools/trb_mesh.py` extracts them to per-level OBJ
meshes. Open: meshes whose pos indices exceed the own chunk (true
shared pools, pools live in other sections) and the collision mesh format
(unknown — see §4c; the byte-interpretation tools were removed in the
blank-slate cleanup).

**Collision (2025-08 live session): RESOLVED — see §4f.** NTU has no
separate collision-mesh format. The game's collision = the level's
COLLISION MODEL: a list of named AABB volume objects ("Collision_*", the
0xc0-byte Database instance records) + the compiled collidable surfaces
(the W0C0M display meshes placed at integer offsets), queried by a
vmtext custom AABB-tree ray caster. OpCODE is dead in the DOL. Full
writeup: `docs/collision-runtime.md`.

---

## 1. Container (all `.trb`/`.ttl` files) — VERIFIED

Big-endian. 4-byte tags appear **byte-reversed** on disk (the engine stores
tags as LE u32 constants, so BE readers must compare reversed).

```
offset  size  field
0x00    4     magic "TSFB"
0x04    4     file size minus 8
0x08    4     "FBRT" (TRBF tag, always present, empty)
0x0C    4     "XRDH" (HDRX chunk directory tag)
0x10    4     HDRX size           (0x578 in SBWorld_Detail_Level01_01)
0x14    4     flags               (0x00010001)
0x18    4     section/chunk count (87 in SBWorld_Detail_Level01_01)
0x1C    4     zero
0x20    n*16  chunk table: n entries of 16 bytes:
              +0  u32 size of this chunk (BE)
              +4..15 zero
              NOTE: sizes tile the SECT exactly (sum == SECT size).
0x20+n*16 ...  "TCES" tag + u32 SECT size + SECT data
               "CLER" tag + u32 size + relocation list
               "BMYS" tag + u32 size + name table
```

### RELC (relocations) — VERIFIED

`"CLER"` + size + list of entries. Entry layout as consumed by the Toshi
loader (`TTRB::ProcessForm`): the pointer lives in **section 0** (the SECT)
and its **value is += the base of the target section**:

```
entry = (u32 offset_of_pointer_in_sect, u32 target_section)
```

Confirmed against the loader semantics in the reference engine
(OpenToshi `TTRB.cpp`: `*ptr += base(section[entry.HDRX2])`) and by hand:
the mesh-record fields A/B/C/E (+0x14/+0x18/+0x20/+0x28) all appear in the
RELC list, and each mesh's chunk pointer (+0x10) resolves to its own chunk.

### SYMB (names) — VERIFIED

`"BMYS"` + size + u32 count + count × 12-byte entries + NUL-terminated name
strings. Entry layout (matches `TTRB::TTRBSymbol` in OpenToshi):

```
+0  u16  HDRX (section index; 0 in level files)
+2  u16  nameOff (offset of the name in the trailing string block)
+4  u16  padding
+6  i16  NameHash = (char + hash*0x1f) & 0xffff
+8  u32  DataOffset (offset of the symbol's data within section HDRX)
```

Sanity checks: `hash("SkeletonHeader") = 0x655A`, `hash("Database") = 0x759B`,
`hash("Header") = 0xCEAD`, `hash("Materials") = 0x600C`,
`hash("Collision") = 0x6712`, `hash("W0C0M0") = 0x38C9`.

`SBWorld_Detail_Level01_01.trb` has 92 symbols: `SkeletonHeader`, `Database`,
`Header`, `Materials`, `Skeleton`, `Collision` + **`W0C0M0`..`W0C0M85`**
(86 meshes = "World0 Camera0 MeshN"). `DataOffset` of each `W0C0Mk` = the
per-mesh 52-byte record at `SECT + 0x3B08 + 0x34*k`.

**The old "5-byte wall column" reading (0x655A/0x759B/0xCEAD) is definitively
wrong**: those values are literally the NameHashes of SkeletonHeader /
Database / Header. The `Collision` symbol is an empty stub
(`{0, 1, ptr→0x36CC, ptr→0x36D0}` with `0x36D0 = 0`).

## 2. SECT of a level part — VERIFIED

```
SECT+0x00  u32 1
SECT+0x04  f32 level-specific bound (93.9 in SB1_01)
SECT+0x08  u32 0x0C
SECT+0x0C  u32 0x56 = 86   (mesh count)
SECT+0x10  u32 0
SECT+0x14  u32 2
SECT+0x18  u32 0
SECT+0x1C  4xf32 level bounds (9.639, 8.873, -0.300, 36.375)
SECT+0x2C  u32 1
SECT+0x30  u32 0x34 (52, mesh-record stride)   [RELOCATED: +base(sec 0)]
SECT+0x34  u32 0x36C4 (object-table offset)    [RELOCATED]
SECT+0x38  u32 0
SECT+0x3C  u32 0
SECT+0x40  char[12] "SB_D_01_01\0\0"
SECT+0x4C..0x36C0  material records: len-prefixed names ("RoadLines",
                   "Metplate", "02_-_Default", ...) interleaved with
                   4x4 matrices (identity rotation + translation, and the
                   same matrix negated). Referenced by the mesh record's
                   +0x18 (B) field.
SECT+0x36C0  Collision stub {0, 1, ptr→0x36CC, ptr→0x36D0=0}
SECT+0x3748  u32 86, then 86+2 pointers (0x3754, 0x38AC, then the 86 mesh
             records 0x3B08..0x4C4C, then 0x39E8)
SECT+0x38AC  linked list of records (4xf32 + next-ptr + 4xf32 + count +
             u16 index ranges) — likely level-boundary polygons; layout
             not fully parsed
SECT+0x3B08+0x34k  per-mesh 52-byte records (below)
SECT+0x4C80..0x1F7C0  per-mesh C-blocks (below), in mesh order, with
             material-name gaps between blocks
```

### Per-mesh 52-byte record — VERIFIED layout, pointer semantics VERIFIED

```
+0x00  4xf32 (center_x, center_z, center_y, radius) — the (min+max)/2 and
        3D half-diagonal of the mesh's vertex run in world units (verified:
        run midpoint x 40/45, z 38/45, y 44/45 at /64 scale)
+0x10  u32 0                 [RELOCATED -> own chunk base]  = chunk ptr
+0x14  u32 A                 [RELOCATED -> own chunk + A]   = UV array in chunk
+0x18  u32 B                 [RELOCATED -> chunk0 + B]      = material record
+0x1C  u32 0
+0x20  u32 C                 [RELOCATED -> chunk0 + C]      = C-block offset
+0x24  u32 D                 (C-block byte size; not a pointer)
+0x28  u32 E = C + D         [RELOCATED -> section k+2]     (end of C-block)
+0x2C  u32 F                 (C-block record count)
+0x30  u32 G                 (format flag: 0x06020202 flat /
                              0x06030202|0x06030203 smooth)
```

The RELC list relocates exactly these fields (+0x10, +0x14, +0x18, +0x20,
+0x28) for every mesh — this is the authoritative map of the record.
**The +0x10 relocation target is the mesh's vertex-pool SECTION — NOT
always k+1.** Level-global mesh tables (e.g. DPWorld_Level04_01_Detail,
JN parts 03/05) shift the mapping (mesh k's pool can be section k, k-2,
...); reading section k+1 there grabs the WRONG chunk as the pool, which
produces giant garbage triangles that still pass the manifoldness gate on
small pools (a 538-world-unit triangle from a 1.8-radius record). Fixed
in trb_mesh.py: each mesh record carries its pool section from the RELC.
The +0x20 index block always relocates to section 0 (the SECT). Meshes
whose +0x10 relocates to section 0 (some 0x06020101/0x06010101 records)
have no per-mesh pool pointer — their pools live in the SECT (true shared
pools, still open).

## 3. Per-mesh chunks (sections 1..86) — VERIFIED as per-mesh vertex arrays

Each mesh k owns section k+1 of the container. **Every 6-byte record is ONE
vertex**, in a per-mesh local frame:

```
u16 x (signed s16, world x = value / 64)
u16 z (signed s16, world z = value / 64)
u16 y (signed s16, height  = -value / 64)   [raw y is +y DOWN, game-native]
```

Scale 64 = 2^6 (fixed-point 6.10), confirmed for **all 55 level parts** by
matching each mesh's record floats (center = midpoint of the run) against the
chunk field midpoints: 26–36 of the first 40 meshes match to < 0.5 world units
at /64 in every file, 0/40 at /256 or /32.

**Y sign (corrected this session):** the raw y is +y DOWN. The .ini entities
are +y up, so an OBJ vertex's world-up height is `-y/64`. Overlay hit rates
against Entities.ini improve from 9% to 37% of in-bbox entities when the
height is negated, and every level part improves (part 01: 37/43 both ways —
its floors sit at y=0 so the original 82% check was sign-blind; parts 03–08
went from ~0% to 46–93/131 etc.). The web viewer's (x, -y, -z) convention
flips the game's +y-down into up, so a vertex displays at its raw y directly.

**Face topology (solved this session — corrected):** each mesh is NOT a
bare vertex run: the 52-byte record's u32[+0x20] (offset) / u32[+0x24]
(size) point at a `[0x98][u16 count][count x index triples]` block where
each record is an indexed strip vertex `(posIdx, nrmIdx, texIdx)`. Record
width and pos width vary per mesh:
- **pos is ALWAYS the FIRST field** (pos-first). Misaligned pos reads that
  "tile" a pool are false positives (the nrm stream can coincidentally
  look like a strip) — the old decoder's per-byte po scan produced them.
- **pos width is DERIVED, not stored**: u8 iff pos pool <= 256, u16 iff
  pos pool > 256 (GX_INDEX8/INDEX16). Verified 100%% (zero violations)
  across 9,264 mesh records / 69 level parts / 8 format flags. The game
  picks the index width at load from the pool it just built.
- **the record width IS encoded in the format flag** (+0x30) — the flag
  is the per-mesh vertex-format descriptor after all:
    - 0x06020202 -> recw 3 (pos u8, nrm u8, tex u8)
    - 0x06020203 -> recw 4 (pos u8, nrm u8, tex u16)
    - 0x06030202 -> recw 4 (pos u8/u16, nrm u8, tex u8)
    - 0x06030203 -> recw 5 (pos u8/u16, nrm u8, tex u16)
    - 0x06020201 -> recw 6 (SIX u8 attribute indices — the former
      "shared-pool" variant was never shared-pool, just recw > 5)
    - 0x06020101 -> recw 7
    - 0x06030101 -> recw 8 (pos u16)
  The old "width not stored, brute-force everything" reading came from
  searching recw 3/4/5 only: with 6/7/8 included, recw is a clean
  function of the flag. The earlier "signaled by the flag byte" note was
  directionally right but incomplete.
The strip walks consecutive records' pos indices; the repeated-index
(degenerate) triangles are the engine's strip-restart markers. The
strip's pool is the vertex chunk's FIRST max(posIdx)+1 triples (the
record's own pool delimiter), NOT the bounding-sphere run. No fixed
coordinate cap is valid for pool reads — levels span different scales
(SB ~256 world units, JN ~512 = the full s16 range); pool correctness
comes from the bounding-sphere and manifoldness gates (the old hardcoded
12000 cap wrongly rejected JN's larger pools).

Verified on SB part 01: 85/86 meshes decode to perfect manifolds (zero
edges used by >2 triangles, no crossing/overlapping faces, 100% pool
coverage); flat floor tiles triangulate exactly (2.24-unit tiles -> 10419
raw^2 per triangle pair); the road-line mesh (k=1) becomes 8 clean dash
quads (16 triangles) instead of the old 22-triangle decode with 10 garbage
slivers spanning the level. Level-wide (9 levels, 8,467 meshes): 6,652
carry faces (78.6%%, up from 61.7%%), the rest being junk records or
meshes whose indices exceed the own chunk (true shared pools — pools live
in other sections; the +0x10 relocation target identifies which). Of the
decoded faces, only ~72 triangles (0.007%% of 430k+) exceed 2.2x the
record radius (gate-tolerated long triangles, mostly legit in coarse
meshes). The 0x06030202/03 smooth meshes show lower pool coverage (avg
0.79) but ZERO oversized edges — that is strip sparsity (several
restart-heavy strips sharing one pool), not garbage.

Structure of a chunk: `[vertex pool][0-padding][secondary data][trailer]`.
The pool is the prefix whose s16 triples the index block references (first
max(posIdx)+1 records; often equal to the bounding-sphere run, but the
sphere test under-reads some meshes). Records after the pool include
all-zero padding, a small secondary block (some meshes: u16 pairs = texture
coords), and a garbage trailer.


The earlier "(posIdx, uvIdx, nrmIdx) index streams into a shared pool"
reading of the CHUNK triples themselves is WRONG — the "pos pairs" are
adjacent strip x-coordinates, the "smooth uv" is the depth (z) advancing
along geometry, "nrm constant 5" is a flat ground height 5/64 = 0.078, and
the "-37 (0xFFDB) seam marker" is the s16 height -37/64 = -0.58 (duplicate
below-ground vertex for hard edges). The REAL index stream is the record's
0x98 block.

**Verification:** overlaying `SBL1_Ents.ini` entity positions, 40/49 entities
(82%) inside the part's bounding box have a strip vertex within 1.2 world
units (ground-truth: entities stand on the geometry). A top-down render of
all 9629 vertices of `SBWorld_Detail_Level01_01.trb` shows the coherent level
layout (plaza, raised platforms, lower areas).

**Note:** the mesh-record table is NOT at a fixed offset across files — use the
SYMB table: `W0C0Mk` DataOffset = mesh k's 52-byte record (SB1_01 happens to
be `0x3B08 + 0x34*k`; other parts vary). Some files list more meshes than the
part has chunks (level-global mesh tables) — skip meshes with `k+1 >= chunk
count` or garbage radius.

## 4. C-blocks (chunk 0) — the 0x98 index blocks; NOT a verified walkmesh

Every mesh's C-block region (record +0x20 offset / +0x24 size, always in
section 0) begins:

```
[0x98] [u16 F] [F x u8 triples]   (F == the record's +0x2C field, checked 86/86)
```

CORRECTION (2025-08): these u8 triples are byte-identical to the strip's
index records for the recw-3 (flag 0x06020202) meshes — each triple IS
(posIdx, nrmIdx, texIdx). The b byte is the NORMAL index, not a height:
checked against pool-vertex heights (mesh 2: b=0..56 vs real floor
heights, no correlation), and the recw-4+ meshes' blocks are their wider
index records (reading them as u8 triples is misaligned). The earlier
"walkmesh grid" decode (x = x0 + a*(x1-x0)/amax, z = z0 + c*(z1-z0)/cmax,
y = b/8 against the record AABB) was NOT verified: the "player spawns
stand on the decoded grid within 0.1 units" check passed because the
AABB grids are dense (cells ~0.1-0.3 units apart) and nrmIdx=0 dominates
floor strips — a coincidence, not a collision surface. The viewer's
"Walkmesh grids (C-blocks)" overlay renders that documented decode as-is
for eyeballing (mint points + grid-adjacent lines), but the REAL verified
collision is the display-mesh triangles (88% of entities within 1.2 units
of a strip vertex) and the 5-byte wall records (see below).

What the overlay DOES show (verified via top/side projections of the
decoded cells, 2025-08): the (a, c) -> (x, z) mapping reproduces the
level's real footprint (a C-shaped layout with corridors and voids shows
through), and nrmIdx=0 cells blanket the whole footprint (24/24 x-buckets
have floor cells) — which is exactly why the old "spawns stand on the
decoded floor" check passed. The b/8 heights above 0 are a smooth nrmIdx
gradient (28% of cells at 0, then 0.125, 0.25, ...), not platform heights.

The C-block region can be larger than the triples: the large world meshes
(5, 6, 8 in SB1_01) carry secondary data (incl. the Collision symbol)
after their index records inside the same span.

## 4b. 5-byte wall records — coordinate findings (2025-08)

SUPERSEDED: the "5-byte wall records" were the recw-5 INDEX records of the
0x06030203 meshes (u16 posIdx + u8 nrmIdx + u16 texIdx), misread as
(F, X, Z, Y1, Y2). X/Z/Y behavior (no z clustering, profile follows the
mesh) is exactly what index streams do. Not collision.

## 4c. Per-mesh collision footprints + flags — RETRACTED (collision now resolved in §4f)

The "collision footprint + flags" reading of the per-mesh data block that
follows each vertex pool (record +0x14 = padded pool size, +0x18 = pool +
collision block) is **retracted**. It decoded the block as 4-byte
`(flag, x, y, z)` s8 records and dequantized the (x, y, z) bytes against
the mesh's own vertex-pool bbox per axis —

    world_x = xmin + (s8x + 128) * (xmax - xmin) / 255
    world_z = zmin + (s8z + 128) * (zmax - zmin) / 255

— but the record width, the transform and the flag semantics were **never
confirmed in the DOL**: no reader was located, and the old statistics
(0x00 = "default solid" 71.1%, 0x01 = "char" 12.1%, 0xFF = "all-bits" 6.8%;
median coll→nearest-vertex distance ~1.16 u; "identical-geometry copies
carry identical flag sets") describe the hypothesis's output, not ground
truth. The block-size arguments for the later 3-byte u8-triple "walkmesh"
reading are equally unverified. **The collision mesh format is unknown**
was the conclusion then; the 2025-08 live session superseded it: there is
NO separate per-mesh collision format — the collision model lives in the
level's Database object instances + the compiled display-mesh surfaces
(see §4f). The "coll" byte arrays in the web JSONs are the display-mesh
index records, not collision data.

What does stand independently:

- The blocks are exported to the web JSON as each mesh's "coll" array
  (raw bytes, "collFormat": "unknown"); the flag-colored footprint
  overlay and the footprints JSONs were removed in the blank-slate
  cleanup.
- The DOL `collision_*` strings @0x8004FC90 and the CollisionMask_*
  {name→value} table @0x8004FAB4 are dead data in the retail DOL (zero
  instruction/pointer xrefs, re-verified 2025-08) — they are entity/
  trigger property names and entity collision *layers*, not a per-mesh
  collision format.
- Also corrected: the "AWorldMesh vtable functions" (strip-walk attribute
  helpers, r29=stream/r24=format) were actually vsnprintf — the 0x7f04xxxx
  pointers are its switch tables.

**Sibling-engine comparison (2025-08):** Battle for Volcano Island (same
Toshi engine family) switched to DEDICATED collision: its level/model
TRBs carry a real `Collision` symbol (a TModelCollision header: hash,
m_iNumCollisionModels, radius, bbox, leaf descriptors — matching
OpenToshi's `TModelCollision { TINT m_iNumCollisionModels; }` and
OpenBarnyard's `CollisionHeader/CollisionMesh/CollisionGroup` TMD v2.0
structs) plus a `CollisionTree_0` AABB tree (40-byte nodes
{childA, min 4xf32, max 4xf32, childB}, leaf indices < 0x100) over a f32
point pool + u16 index strips, in separate `*_col.trb`/`Collision.trb`
files or built into `Cell*_L0*.trb`. NTU's `Collision` symbol is an empty
stub {0, 1, ptr, 0} = "zero collision models"; where NTU's real collision
lives is unknown. The best "dedicated collision" candidate remains the
SECT+0x38AC polygon list (below), still partially decoded.

## 4d. SECT+0x38AC polygon list — best "dedicated collision" candidate (2025-08, partially decoded)

SECT+0x38AC (SB1_01) holds a linked structure: a 4-node pointer chain of
f32 box data (8.31, 10.46, 2.32 / -3.51, 14.80, 2.06 / 0.36, 20.40, 1.36 /
7.65, 17.75, 0.74 — z ≈ 1-2, vertical wall profiles, extending beyond the
level bounds), then 11 polygon records each `[u32 count][count×u16
indices][u16 0 terminator][u32 next]` with CONSECUTIVE index ranges into a
shared 86-vertex pool: 0..16, 17..20, 21, 22..34, 35..43, 44..54, 55..62,
63..68, 69..76, 77..85. Matches the docs' old "4xf32 + next-ptr + 4xf32 +
count + u16 index ranges" note ("likely level-boundary polygons"). The
shared 86-vertex pool is NOT in the parsed region (may live in the C-block
span 0x4C80+). Full decode (record framing, pool location, and whether
this is gameplay collision or occluders) is the highest-value follow-up.

## 4f. The collision model — Database object instances (2025-08, RESOLVED)

NTU's collision is NOT a separate mesh format. It is a **collision model**
built at level load from the level's object-instance list (the `Database`
record / SECT object table). Live evidence (grilled-dolphin, s01→run level
load, world part ctor 0x7f2a4db4 firing for the exact runtime part
0x81282620 through FUN_7f2a5308 — the same "Collision"-symbol builder the
entity collisions use):

- The runtime world model (0x81257158) is named **"dpl1_c1"** (level name +
  collision variant) and its source part carries the identical
  pool/idx/counts as the compiled mesh (11379 verts / 17973 idx).
- The model = a list of **named AABB collision objects**, each a 0xc0-byte
  record:

```
+0x00  u8 nameLen + name ("Collision_", "Collision_nopathfind1", ...)
+0x1c  u32 flags (0x0000ffff = enabled)
+0x20  u32 0
+0x24  3xf32  transform/corner 1
+0x30.. 4x4 identity-ish matrices (rotation + position)
+0x70  3xf32  transform/corner 2
+0x7c.. rest of the matrices
```

  Observed names: `Collision_`, `Collision_nopathfind1`, `Collision_noocclude`,
  `Collision_Prison01_01`, `Collision_nopathfind`, `Collision_Pris2`,
  `Collision_prisy`, `Collision_part2`, `Collision_new01/00/02/03`,
  `Collision_woo`, ... — the suffixes encode behavior (noocclude =
  no occlusion culling, nopathfind = no pathfinding, the rest are authored
  volume names).
- The SAME 0xc0-record format is the level files' `Database` content:
  `dpl1_04` has Pris_S4_01..26, `dpl1_01` has Pris_S1 (records are
  byte-identical except the name field). The Database = the object-instance
  list with transforms.
- The compiled world mesh = the collidable surfaces = the W0C0M display
  templates placed at integer offsets (per-object placements, identity
  rotation/scale — see `docs/collision-runtime.md` "RESOLVED: the 88% =
  placed object instances").
- The file `Collision` symbol stays an EMPTY stub {0,1,ptr,0} in all
  game TRBs; the model is materialized at load from the Database
  instances + W0C0M data. NTU does NOT use the Barnyard
  TModelCollisionData path (that was the sibling-engine BFVI format).
- `levelnfo.trb` holds the ACTIVE level name ("dpworld_level04_01_Detail")
  — the sector/area whose collision model is live.

## 4e. OpCODE collision library (2025-08, DOL)

main.dol statically links Pierre Terdiman's OpCODE triangle-mesh collision
library: runtime strings at 0x800AA040-0x800AA110 ("Higher distance bound
must be positive!", "Temporal coherence only works with First contact
mode!", ...) and the mesh-builder warning @0x800A9E04: "OPCODE WARNING:
found %d degenerate faces in model! Collision might report wrong
results!". The engine builds its runtime collision model from the parsed
mesh triangles (the 0x98 index strips) at load — the strongest code-level
evidence that NTU's collision is part of the mesh data (the mesh triangles), not a separate collision mesh file. The
mesh-loader itself remains unpinnable statically (vtable-only reachability).

## 5. Large meshes (previously "smooth meshes")

Meshes 5, 6, 8 in SB1_01 are the large world meshes: their chunks hold the
most vertices (485 / 832 / 576 in part 01) and their C-block spans contain
the extra collision structures (the Collision symbol at 0x36C0 / the wall
arrays). The earlier note about a separate "s16 x3 position array at the head
of their chunk" is superseded: every chunk is a vertex array; the big meshes
are just bigger, with more secondary/trailer data after the run.

## 6. Entities file — VERIFIED

`SBL1_Ents.trb` is a compiled `SBL1_Ents.ini`: entity positions appear
verbatim as big-endian f32 triples (all 40 sampled positions matched 1:1,
including the y sign). World coordinates are (x, y, z) with +y up; entity
platforms sit at y ≈ 3..10, floors at y = 0. The viewer's `(x, -y, -z)`
convention comes from the game being +y-down and z-mirrored.

## 7. main.dol reverse-engineering status

Setup (working, reproducible):
- DOL has a **non-standard header**: data-section fields are garbage. The
  real text sections are indices 0,1,7,8,9,10:
  `file 0x100→0x80003100, 0x4A0→0x800034A0, 0x3F480→0x80042480,
  0xB3F40→0x800B6F40, 0xE5500→0x80195620, 0xE6A20→0x80197C40`.
  SDA bases set in `__start`: r13 = 0x8019D620, r2 = 0x801AD620.
- Zero out the data-section file-offset (0xD8..0x120) and size (0x168..0x194)
  fields, import the raw file in Ghidra with the PowerPC:BE:32 language, then
  create the six text blocks at the RAM addresses above (script in
  `analysis/ghidra/SetupMemory.java`). Full auto-analysis + decompiler work.

Findings:
- **GX library is statically linked** at 0x80006xxx..0x8003Exxx (70+
  functions write the CP FIFO at 0xCC008000; e.g. `FUN_8003d078` loads a
  constant array base, `FUN_8003da04` is a TEV/BP writer). The game's
  renderer reaches it through a thin HAL (ASysMeshHAL etc.).
- **All format strings are dead data**: class names (`AWorldMesh`,
  `AWorldMeshHAL`, `ANTWorldMesh`, `TVertexFactoryResource`, `TMesh`,
  `SkeletonHeader`, ...), the level-manifest paths (`Data/.../*.trb`), and
  `"TSFLTSFB"` at 0x80198518 have zero instruction and zero u32-pointer
  references in the whole file. The mesh-parsing code is reachable only via
  function-pointer tables; it could not be pinned statically this session.
- The TTRB container loader logic matches OpenToshi's `TTRB::ProcessForm`
  (same RELC/SYMB consumption), which is strong corroboration for §1.
- **Next steps that would close the remaining questions:**
  1. Dolphin emulator trace of the level load: breakpoint the RELC
     processing or the mesh-record reads, dump the runtime pools the u16
     indices resolve against (this is the only way to settle §3).
  2. Ghidra: walk the vtable of `ANTWorldMesh`/`ASysMeshHAL` from the
     class registration table, then decompile the load/validate methods.
  3. Compare with the PS2 build (`nicku-ntsc` is GC; a PS2 NTU dump's
     `TrbModelConverter`-style tmod/twld would show the sibling layout).

## 8. Tools

- `tools/trb_unpack.py FILE [outdir]` — **clean container unpacker**: writes
  every chunk as `chunkNN.bin` + a `manifest.txt` inventory (header, chunk
  table, RELC, SYMB, mesh records with C-block stats, material names).
- `tools/trb_container.py FILE` — older container walker (prints tables).
- `tools/trb_mesh.py [--file PATH] [--out DIR] [--faces]` — **display-mesh
  extractor** (2025): per mesh, reads its 52-byte record from the SYMB table,
  delimits the vertex run in its chunk (bounding-sphere test vs the record's
  center+radius), decodes `(x, z, y) s16 / 64`, and writes
  `mesh_<part>.obj` (vertices + wireframe lines + optional triangle-strip
  faces split at large jumps) per level part into `output/mesh/` plus
  `mesh_stats.json`. Verified: 82% of `SBL1_Ents.ini` entities have a vertex
  within 1.2 units; 414k vertices across all 55 parts.
- `tools/render_hypothesis.py`, `tools/render_strips.py`,
  `tools/pool_search.py` — hypothesis-testing scripts (index-pool binding).
- `tools/dol.py`, `tools/re_dol.py`, `tools/find_gx.py`,
  `tools/find_callers.py`, `tools/find_gxsetarray.py` — DOL section loader +
  capstone PPC-BE disassembler + xref/GX helpers (run under
  `nix-shell -p python3Packages.capstone`).
- `analysis/ghidra/SetupMemory.java` — Ghidra memory-map fixup for the
  raw-imported DOL.

## 9. Open items (honest list)

1. ~~Face topology~~ SOLVED: the mesh is an INDEXED GX triangle strip — the
   record's 0x98 block carries (posIdx, nrmIdx, texIdx) per strip vertex and
   the strip's pool is the chunk's first max(posIdx)+1 triples (see §3).
   Layout rules are analytic: pos-first; pos index width = pool size
   (u8 <= 256, u16 > 256, verified 100%%); recw = a function of the format
   flag (recw 3..8). Winding observation: the strips are wound so the front
   faces point at the side the in-game player sees (floors up, ceilings
   down, walls into the room) — the web viewer uses this for its
   back-face culling toggle.
2. ~~Exact C-block grid face semantics and the y-scale~~ CLOSED (2025-08):
   the u8 triples are the recw-3 strip's (posIdx, nrmIdx, texIdx) index
   records; b is the normal index, not a height (see §4 correction). The
   viewer's walkmesh overlay renders the old documented decode for
   eyeballing; the real collision data format is unknown (see §4c).
3. The UV arrays (the +0x14 A field). Counts vary per mesh (21-608 u16
   pairs vs 24-660 run vertices) and do not match 1:1 — the per-quad /
   per-corner mapping is unsolved. The pairs look like (u, v) with
   v mostly negative (flipped V) — see "Texture pipeline" below.
4. The 0x38AC linked-list structure semantics.
5. The +0x28 (E) RELC target section (k+2) semantics — the field value
   equals C+D but the relocation points at the *next* mesh's chunk.

## 10. Texture pipeline (feasibility notes from this session)

- **Textures are in the `.ttl` files** (same TSFB container, one chunk +
  one SYMB symbol "TTL"). The chunk begins with a per-texture list:
  entry 0 at chunk+0 has `[u32 0x308][u32 0x70][u32 0x80][u32 0x80]...`
  (0x308 = texture data size / entry size?, 0x70 = name offset, 0x80x0x80
  = 128x128?). The name string at +0x70 is the original asset path, e.g.
  `world\SB_SqudHouse.tga`. Raw pixel data follows (~0x98..0x308 for
  entry 0, ~624 bytes: image-like, neighbor-similarity 32-36% as I4).
  The exact entry layout / texture format (GX I4/I8/C8/RGB5A3?) is open.
- **Material records** in SECT (chunk0): `[u32 nameLen][name][pad to
  0x20][u16 0xFFFF][...][4x4 f32 matrix]` — names are "RoadLines",
  "Metplate", "02_-_Default", ... The mesh record's +0x18 (B) field
  points at the mesh's material; the matrix is identity rotation +
  translation (likely a UV scale/offset or world transform).
- **Next steps**: (1) decode the TTL entry header + GX texture format;
  (2) solve the UV count mapping (per-vertex vs per-corner vs per-face);
  (3) bind mesh -> material (+0x18) -> texture name -> TTL entry, apply
  the matrix; (4) viewer: CanvasTexture / data-URL images per mesh.
