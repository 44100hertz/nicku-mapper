# NTU collision — runtime system + the extractor misalignment (2025-08 session)

Live RE session (grilled-dolphin control server + Ghidra on the combined
vmtext+DOL ELF, savestates GNOE78.s01/s02/s03). Two independent results:

1. The "collision mesh" mining (`re/trb/extract_collision.py`) was reading
   the **same 52-byte W0C0M mesh records as the visual meshes, misaligned by
   +0x20**. There is no separate collision-mesh record format at a different
   offset; the mined "coll" JSONs are a shifted view of the display records.
2. The runtime collision system is **NOT OpCODE**. OpCODE is dead code in the
   DOL (strings only, zero code references). The real system is a custom
   quantized-AABB-tree ray caster in vmtext, built from the level mesh data.

## 1. The extractor misalignment (proven, byte-level)

True record layout (52 bytes, W0C0Mk DataOffset, verified against file bytes
and the runtime model):

```
+0x00  4xf32 center (x, y, z), radius        <- real center
+0x10  u32 0
+0x14  u32 A (UV array off)   +0x18 u32 B (material/cblk?)  +0x1c u32 0
+0x20  u32 C-block offset (chunk0)  +0x24 u32 C-block size
+0x28  u32 C+D (end)                   +0x2c u32 strip count
+0x30  u32 format flag (0x06020202 flat / 0x06030202 smooth ...)
```

`extract_collision.py` scanned for records with flag==0x06020202 at **+0x10**
(that is the real flag at +0x30) and read the "center" at **+0x14** (the next
record's +0x00). Result: its "mesh k" is the real record k, shifted +0x20,
with the **next** record's center/radius/pools/strip. Verified:

- COLL-0 (file 0x2604 = W0C0M0.rec + 0x20): center == W0C0M1's center,
  faces == W0C0M1's 813-face posIdx stream, verts == W0C0M1's verts
  (count 336 vs 331 = stride padding).
- 685/687 "collision" meshes matched a visual record exactly for this reason;
  the flag filter (exact 0x06020202) is why the shifted table skipped the
  smooth (0x06030202) records and why counts differ (687 vs 876).

So: **same data, same file offsets, same records** — the "collision meshes"
are the display meshes. The old trb-format-notes §2 layout (center@+0x00,
flag@+0x30) is the true one; the extractor docstring's layout is wrong.

## 2. The runtime collision system (vmtext, custom — NOT OpCODE)

OpCODE ruling-out: "OPCODE WARNING: found %d degenerate faces in model!"
(0x800A9E04), "Higher distance bound must be positive!" (0x800AA040),
"bad_alloc"×4, and the RayCollider strings (0x800AA068..0x800AA110) are all
dead rodata — zero lis/addi and zero data-table references in the DOL *and*
in vmtext. The OpCODE region 0x800A9xxx-0x800Bxxxx is strings/RTTI/vtables
only (the "function pointers" there are string tables like
"Data/Locale/eng.trb").

The real collision system (vmtext = 0x7f004000..0x7f315a9f):

- Ray queries (game layer): `FUN_7f0686d8` (world-ray dispatcher,
  2 modes selected by ctx+0x30: 0 = bounds/AABB query via
  FUN_7f290258; != 0 = full mesh ray via FUN_7f067e60) →
  `FUN_7f067e60` (all meshes) → `FUN_7f0650d0` / `FUN_7f065414`
  (per-model ray, closest/first hit, group-mask filter).
  LIVE-VERIFIED (s02, breakpoint at FUN_7f0686d8): the game's actual
  ground-collision query is a downward ray (origin (-27.13,-0.62,44.33),
  dir (0,1,0) — the player gravity check), ctx = 0x804f5970,
  ctx+0x30 = 0x804c97d4 (non-zero → the MESH path, NOT the AABB-only
  mode). The AABB path is a bounds-only query variant.
- `FUN_7f290258` — **ray-vs-AABB "slabs" intersection test** (Williams
  method: per-axis t=(min−o)/d, t=(max−o)/d, swap, tNear=max,
  tFar=min, reject if tFar<tNear or tFar<0; returns tNear). This is the
  cheap coarse reject of the world ray's mode-0 path.
- Tree dispatch: `FUN_7f2546e8` — selects one of 8 tree walkers by the
  model's tree-type enum (model+4): leaf/no-leaf variants; the walkers are
  FUN_7f259760, 7f257038, 7f258b74, 7f2564a4, 7f257cac, 7f2556b4, 7f258390,
  7f255d30.
- `FUN_7f259760`: quantized-AABB-tree walk + ray-vs-indexed-triangle
  (Möller–Trumbore barycentrics; triangle = 3×u16 into a float pool; leaf
  nodes: bit0 + index>>1 into a 6-byte-per-triangle table). The tree node
  AABBs are the per-triangle broad-phase (the second coarse reject before
  the expensive test).
- Triangle→mesh/group mapping: `FUN_7f2a4ee0` (per-mesh records, 0x24 stride,
  triCount@+8, collision-layer flags@+0x20).
- Query context: SDA global at r13-0x7d10 (0x80195910); world part models at
  world+0xd4 (0x28 stride); query model inline at ctx+0x1c.

Runtime world model (verified live): float pool + u16 triangle table
(3×u16 per tri, consecutive triples) + quantized tree + per-mesh records
(0x24 stride: name@+0, ?@+4, triCount@+8, submodel@+0xc, u16 pairs@+0x1c),
grouped into collision layers. One live dump: 11379 verts / 5991 tris in 3
layers (flags 0x27/0x26/0x7). The pool = the file s16 pools × 1/64 in the
SAME component order (identity — NO axis swap; byte-exact: file s16
(256,768,0) = runtime (4.0,12.0,0.0), found verbatim in the file).
Component 3 is UP in the runtime world (the collision panels span
comp1×comp3 with comp2 fixed — vertical walls 4.2 units tall; the head
quads at comp3=0 are floors) — same convention as trb-format-notes §3.
The runtime pool is compiled per-mesh (strip-ordered, some dedup across
meshes); the exact compilation step (which builder reads the [0x98] strips
and fills the pool/idx/tree) is still open (FUN_7f2a5308 consumes the TRB
"Collision" symbol — but every game TRB has an EMPTY Collision stub
(count=0, all 207 scanned), so the world builder reads the W0C0M display
data instead).

**Slopes verified in the runtime world (s02 dump):** of the 5991 triangles,
4855 are axis-aligned (81%) but 1136 (19%) are NON-axis-aligned — real
slope geometry, e.g. 45° stair-step wedges (normals (0.71,0.71,0):
(5.5,13.5,10)→(5.5,13.5,0)→(4.0,15.0,0)) and a spread of angles 10-50°+.
So the collision is a true triangle mesh (the Möller–Trumbore caster
handles arbitrary orientations); the AABB tests (world bounds + tree
nodes) are the coarse rejects that gate the per-triangle tests — the
AABBs do NOT replace the triangles (the user's hypothesis).

TTRB chunk layout (this session, byte-proven): chunk 0 = the 52-byte mesh
records + all [0x98] strip blocks (record cblk field +0x20 is chunk-0-
relative; +0x2c = strip count); chunk k+1 = mesh k's [0x9b] s16 vertex pool
(W0C0M0→chunk1, W0C0M4→chunk5, W0C0M7→chunk8, W0C0M12→chunk13 — mesh index
+1, exact).

Mined-vs-runtime overlap (measured, NOT proof of collision-only):
11379-vert runtime pool vs union of mined DP1 pools = 13.1% match.
CAVEAT: the dumped world was the cutscene/active room (the DP1 level TRBs
were partially unloaded during the session, W0C0M name count 451→150), so
the 86.9% no-match is UNEXPLAINED, not proven collision-only. It is
consistent with gameplay: the level's collision ≈ its visual meshes, with a
small set of collision-only extras (per playtesting: one invisible wall and
two invisible floors in DP1) and some visual meshes that are non-colliding
(e.g. transparent/prop meshes). Confirmed against the file: the runtime
quad mesh's 13 distinct verts, 10 of which are in W0C0M4's pool
(DPWorld_Level01_01.trb) at exact file coordinates.

Ruled out: the SECT+0x38AC polygon list (86 verts / 11 polys) cannot be the
collision source — the runtime model holds 11379 verts per part.

## 3. The continuous line (asset → collision calls)

TRB files (Data/<level>/*.trb)
→ TTRB container loader: FUN_7f297178 (ProcessForm, RELC/SYMB/HDRX handling)
  + FUN_7f296f74 (TTRB::Load, magic check) — vmtext, 0x7f296f-0x7f2981
→ 52-byte W0C0M mesh records (center@+0x00, flag@+0x30, C-block@+0x20/+0x24)
→ runtime world model build (pool + u16 triangle table + quantized AABB tree
  + per-group records) — builder not yet pinned
→ ray queries: FUN_7f0686d8 → FUN_7f067e60 → FUN_7f0650d0/414
  → FUN_7f2546e8 → FUN_7f259760 (ray-triangle) — all vmtext
→ hit results filtered by collision-layer mask (per-mesh flags, group mask
  e.g. 0x27/0x26/0x7; entity masks from the DOL CollisionMask table are
  entity-layers, a different system)

The "Collision" TRB symbol is an empty stub {count=0, ptr=1} in ALL 207
game TRBs (scanned this session) — NTU does NOT use the Barnyard
TModelCollisionData path. The world collision model is built at load from
the level's Database object instances + the W0C0M display meshes by
FUN_7f2a5308 (the same "Collision"-symbol builder the entity models use,
fed runtime-materialized data) — see the "HOW THE COLLISION IS ACTUALLY
DETERMINED" section below.

## Gameplay observation (playtesting, to be tied to the data)

Collision ≈ visual mesh with exceptions, per playtesting in DP1:
- some visual meshes have NO collision (non-colliding/transparent props),
- some collision has NO visual counterpart — at least one invisible wall
  and two invisible floors in DP1.

This matches the runtime model containing both level-mesh verts (13.1% of
the dumped pool matches mined DP1 pools byte-exact) and panels at fixed
thin coordinates (wall/flo or-like geometry at z∈{0,4.2}, y∈{-13..211}) that
are absent from the mined visual pools. The exact set of collision-only
meshes (and where they're stored — likely W0C0M records the visual
extractor skips, or runtime-generated boundary geometry) is still open:
re-dump the collision model while the DP1 level is the ACTIVE world (the
level TRBs stay resident, W0C0M count 451) and diff against every W0C0M
pool, including records with non-0x06020202 flags (0x06030202 smooth,
0x06020201, 0x06010101, 0x06030203, 0x06020101 exist in Level01_01).

## 4. Savestates (GNOE78.s01/s02/s03)

- s01: start of DP level load (resume → dannyphantomlevel1 files dispatch:
  DPWorld_Level04_01_Detail.trb, Entities.trb, ...). Use to catch the
  level/mesh load chain.
- s02: in-level, collision certainly active (ground truth). In
  dannyphantomlevel1 (folder strings in RAM, W0C0M 451). The active world
  model (0x81257158 → single part 0x81282620 → pool 0x81258304, 11379 verts
  / 5991 tris) is the same object in s02 and after s03→run: it is the
  game's ACTIVE collision world.
- s03: end of cutscene, fading out, level load follows IMMEDIATELY (no
  loading screen → a few glitchy frames), then a dialog "cutscene" during
  which collision is probably (not certainly) active. Advance by pressing A
  several times + waiting → arrives at s02's in-level state.
- Practical flow: s03 → (A ×N) → s02. Collision certainty: s02 yes, s03
  (dialog) probably, s01 loading.

### OPEN ISSUE (this session): active-world geometry ≠ mined files

The s02/s03 active world (0x81257158, 11379 verts, bbox x[-88,105]
y[-13,211] z[-12,24] runtime units; as file coords x[-5632,6739]
y[-832,13504] z[-768,1534] ≈ Level01_04 ∪ Level04_01_Detail bbox) does
NOT match the mined DP1 pools: 12% vert overlap at identity /64 (best),
2.3% triangle overlap, and the runtime's unique verts are NOT in the raw
Level01_04 file at all. Mined pools themselves verified correct (JSON pool
== chunk k+1 bytes for W0C0M0 in L01 and L04). So either the dumped object
is not the level's collision (it is a single-part model with small
AABB-ish head floats), or the collision is rebuilt/placed geometry, or the
level collision comes from data not yet decoded. Playtesting says visual ≈
collision, which CONTRADICTS the 88% no-match — one of the two is wrong
and this is the #1 open question. The 12% identity matches include the
runtime quad mesh (10/13 verts in W0C0M4's pool, byte-exact) — a real but
small connection.

Streaming assessment (does the level stream?): streaming explains the
STRUCTURE — single-part world (count=1 at 0x81282620-8), 5991 tris vs
~23000 in the 7 part files, W0C0M 451 resident vs 875 total, and the
runtime bbox ≈ Level01_04 ∪ Level04_01_Detail (x[-5632,6739] y[-832,13504]
z[-768,1534]). 76/209 Level01_04 meshes reference posIdx ≥ own chunk size
(shared pools — the extractor's open item), consistent with pools being
streamed separately.

### RESOLVED: the 88% = placed object instances (file mesh + offset)

The runtime collision world is NOT generated geometry. It is the level's
objects compiled as instances: for each placed object, pool += (mesh verts
+ placement offset), idx += (reindexed strip tris). Evidence:

- Identity orientation + INTEGER offsets match file meshes into the
  runtime pool: 23-25 meshes at 40-100% coverage, e.g. W0C0M56 (L01,
  4-vert panel template) appears at ~190 distinct offsets (100% each),
  L03 W0C0M31 @ (-9535,-9728,-447), L04 W0C0M113 @ (-11008,-13824,320).
  Every found offset has identity perm=(0,1,2) sgn=(1,1,1) — NO rotation,
  NO scale, pure translation.
- Byte-level: runtime vert (-511.875, 1796, 0) = file s16 (-32760, 0, 5)
  + offset (0, 114688, -5) — integer offsets in s16 units (file s16
  -32760 = 0x8008 exists in L01 @0x209c1).
- 40% of runtime verts = file vert + one of the placement offsets with
  only 1/3 of offsets sampled (~55-60% full). The remainder are the
  SHARED-POOL meshes (76/209 in L04 reference posIdx ≥ own chunk): their
  real pools live outside their chunks, so the extractor's JSON pools are
  wrong for them — the verts exist in the file but not in the JSON.
- The 12% identity matches = objects placed at offset ≈ 0.

This reconciles with playtesting: collision ≈ visual because the
collision = the display meshes placed at their display positions (the
same objects the renderer draws). The "1 wall / 2 floors" extras = the
collision-only instances (or the shared-pool meshes the extractor can't
resolve). The placement table's exact source is still OPEN (NOT in the
DPWorld named records — only SkeletonHeader/Database/Header/Materials/
Skeleton/Collision — and NOT in Entities.trb as f32s); the builder
function remains unidentified. Why earlier tests failed: the 24-orientation
global tests assumed ONE transform for everything, but each object has
its OWN offset; the identity raw search failed because placed coords ≠
file coords.

The remaining open items are therefore: (a) the placement table's source,
(b) the builder function identity, (c) the shared-pool meshes' real pools
(extractor gap: pools live in other chunks, e.g. index 0x8008 = 32776 in
L01 strip data references the concatenated pool).

### HOW THE COLLISION IS ACTUALLY DETERMINED (the core question, answered)

Live evidence from a fresh s01→run (the level load, frame 30670): the
collision world's part-model ctor (0x7f2a4db4) fires for part 0x81282620
through the SAME chain as the entity collision models —
0x7f2a48a8 → 0x7f2ba3f0 → 0x7f2bcdcc → 0x7f2bcf00 → 0x7f2a515c →
0x7f2a52d0 → FUN_7f2a5308 (the "Collision"-symbol model builder) → ctor.
So the world IS built by the "Collision"-symbol builder — but from
RUNTIME-built data, not the (empty) file symbols: the world object's
trb-pointer (world+0xd8) holds the parsing state, and the built model is
the level's collision model named "dpl1_c1":

- world+0xd0 = 1 (parts count), +0xd4 = part array (0x81282620),
  pool 0x81258304 / 11379 verts / idx 0x81279868 / 17973 idx — the same
  compiled mesh, source part at 0x81258298 carries the identical
  pool/idx/counts (the world = the parsed model, not a copy).
- The model carries an AABB (head floats 237.03, 8.65/99.0/5.99/149.03
  = the world's head floats byte-for-byte) and a list of NAMED COLLISION
  OBJECTS, each a 0xc0-byte record {name, flags@+0x1c (0x0000ffff),
  transform matrices, AABB corners}: "Collision_", "Collision_nopathfind1",
  "Collision_noocclude", "Collision_Prison01_01", "Collision_nopathfind",
  "Collision_Pris2", "Collision_prisy", "Collision_part2",
  "Collision_new01", "Collision_new00", "Collision_new02",
  "Collision_new03", "Collision_woo", ...
- The SAME 0xc0-record format appears in the level files' Database records
  ("dpl1_04" has Pris_S4_01..26, "dpl1_01" has Pris_S1 etc. — 26/1
  instance records, byte-identical except names) — the file Database =
  the object instance list with transforms, the runtime = the collision
  model compiled from it.
- levelnfo.trb (the level info, 0x98 bytes) = "dpworld_level04_01_Detail"
  = the ACTIVE level — matches the runtime bbox (L04 ∪ Detail area).

THE DETERMINATION: the level's collision = a COLLISION MODEL of named
AABB volume objects ("Collision_*" — the suffixes encode behavior:
noocclude, nopathfind, and the authored volume names). The compiled world
mesh (the triangle pool/idx) = the collidable surfaces. The visual =
the display meshes (W0C0M) — the collision = the collision model only, so
"much of the visual geometry has no in-game collision" is EXPECTED: the
display-only meshes have no collision object. The "1 wall / 2 floors"
extras = collision volumes with no visible mesh.

Still open: the exact compilation of the volume list + W0C0M templates
into the world mesh (the pool ordering, the per-object placements), and
where the "dpl1_c1" model data is materialized from (the file Database
records → the runtime model) — the file "Collision" symbols themselves
are empty in all DPWorld trbs, so the model is built from the Database
instance list at load time.
- How: `savestate.load_from_file` (synchronous, stays paused), arm
  breakpoints/watchpoints, `emulation.run`. Breakpoints/watchpoints survive
  state loads. After a load, GDB-stub interrupts are dead (timing event) but
  breakpoints work; grilled's control server is not affected.
- Live observation: the runtime world model address/content varies per
  session (world pointer 0x81257158 vs 0x811695f8 across runs) — always
  re-derive it via a breakpoint at FUN_7f0650d0 (world = ctx[5]+0xd4).

## 6. Function map (significant addresses, all vmtext unless noted)

### Collision query chain (game layer → triangles)

| Address | Role | Evidence |
|---|---|---|
| `FUN_7f0686d8` | World-ray dispatcher. ctx+0x30==0 → bounds query (FUN_7f290258); else → mesh ray (FUN_7f067e60). +0x3c: 0/1 sub-mode (1 = bounds-only early return). | decomp + live bp (game uses the mesh path) |
| `FUN_7f290258` | Ray-vs-AABB slabs intersection (Williams method, 3 axes, tNear/tFar, reject tFar<tNear or tFar<0). Returns tNear. | decomp |
| `FUN_7f067e60` | Mesh ray (all meshes of the model). | decomp + live (chain) |
| `FUN_7f0650d0` | Per-model ray, closest-hit mode, group-mask filter. ctx[5] = the world. | decomp + live (bp fires constantly during gameplay) |
| `FUN_7f065414` | Per-model ray, first-hit mode. | decomp |
| `FUN_7f2546e8` | Tree dispatch: picks one of 8 walkers by model tree-type enum (model+4). | decomp |
| `FUN_7f259760` | Quantized-AABB-tree walk + Möller–Trumbore ray-vs-triangle (3×u16 idx into float pool; leaf = bit0+index>>1 into 6-byte/tri table). | decomp |
| `FUN_7f257038` … `FUN_7f255d30` | The other 7 tree walkers (leaf/no-leaf variants). | decomp |
| `FUN_7f2a4ee0` | Triangle→mesh lookup: walks per-mesh records (0x24 stride, triCount@+8), returns the mesh index containing tri N. | decomp |

### Collision model build (the world + entity models)

| Address | Role | Evidence |
|---|---|---|
| `FUN_7f2a5308` | The "Collision"-symbol model builder — builds the runtime model (parts 0x28-stride, pool/idx) from a Collision-shaped record {count@+0, parts@+4 0x1c-stride, mesh records 0x18-stride}. **The ACTIVE world builder** (live-caught) — also builds the entity collision models. | decomp + live (world part ctor through this chain) |
| `FUN_7f2a4db4` | Part-model ctor: zeroes part+4/8/c/10, inits per-mesh array at +0x14 (0x24 stride, capacity 0x40). | decomp + live (bp on world part 0x81282620) |
| `FUN_7f2a4874` | Entity collision chain top: vtable record fetch (+0xf4 slot) by id, then the build chain 0x7f2ba3f0 → 0x7f2bcdcc → 0x7f2bcf00 → 0x7f2a515c → 0x7f2a52d0 → FUN_7f2a5308. | live backtrace at ctor hits |
| `FUN_7f296f74` | TTRB::Load: checks RAM magic 0x46425254 at +0x194, then ProcessForm. | decomp + live (bp fires on loads) |
| `FUN_7f297178` | ProcessForm: the generic TTRB section loader (HDRX/SECC/RELC/SYMB, vtable callbacks at +0x1b4). | decomp |
| `FUN_7f2bb870` | Symbol-table record search by name (single caller 0x7f2bc178). | decomp |
| `FUN_7f2bc040` | Path-based record lookup (splits the path, searches the symbol table). | decomp |
| `FUN_7f2bc300` / `FUN_7f2bcaac` / `FUN_7f2bbe34` | Model loaders by path (0x28-byte model objects). | decomp |
| `FUN_7f112a24` | Generic TTRB chunk tag-mapper (0x98→0x94 etc., vtable callbacks) — NOT the builder. | decomp |

### Ruled out / dead

| Address | Role | Evidence |
|---|---|---|
| `FUN_80018ad4` | DOL SDK OSLockMutex (was suspected as the builder). | decomp |
| `0x800217bc` | Old scan2/scan3 dispatcher — never fires in this build. | live (0 hits) |
| OpCODE region 0x800A9xxx-0x800Bxxxx | Strings/RTTI/vtables only; zero code refs in DOL and vmtext. | strings + refs |

### Runtime structures (live-verified)

- World model (e.g. 0x81257158, "dpl1_c1"): +0x0c/+0x20..+0x2c AABB floats; +0x10 sub-object; +0x30 query mode (0 = bounds-only); +0x34 mesh query model (tree); +0xd0 parts count (1); +0xd4 part array (0x28 stride); +0xd8 trb/parse state; +0x1c0+ the named Collision_* volume records (0xc0 each).
- Part: +0x00 0xffffffff; +0x04 pool (f32); +0x08 nverts; +0x0c idx (u16); +0x10 nidx; +0x14 per-mesh array (0x24 stride: vtable, start@+4, triCount@+8, +0x1c tree, flags@+0x20 = layer 0x27/0x26/0x7).
- Query model (world+0x34): the mesh's quantized tree; carries the pool/idx/count refs.

## 5. Tools / notes

- The old scan2/scan3 dispatcher address 0x800217bc never fired in this
  build — the resource-dispatch path should be re-pinned (or use the TTRB
  loader FUN_7f297178 hits, sized by the file-size field at ttrb+0x190).
- grliled-dolphin control server worked flawlessly (sync state loads,
  memchecks, single-step, backtrace, memory.find). No new bugs found this
  session.
