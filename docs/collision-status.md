# Collision — status (2025-08, RESOLVED)

> Live-debugging tooling + protocol knowledge: `scripts/dol/gdbstub/README.md`.
> Read its ⚠️ OPERATIONAL DOCTRINE before touching the stub: the connection
> is ONE-SHOT — no port probing, one persistent driver process, all probes
> through its command channel.

## The collision system — now understood end-to-end

The core questions are ANSWERED (this is the state after the 2025-08 live-RE
session on grilled-dolphin + the combined vmtext+DOL ELF). Detailed writeup:
`asset-extract/docs/collision-runtime.md`; TRB format details:
`asset-extract/docs/trb-format-notes.md`.

1. **The "collision mesh" mining was a misalignment, not a different
   format.** `extract_collision.py` read the same 52-byte W0C0M display-mesh
   records shifted +0x20 (its "flag" was the real flag@+0x30; its "COLL-k"
   records = real record k+1's data). The mined collision meshes ARE the
   display meshes. Byte-proven.

2. **OpCODE is dead code in the DOL** (strings only, zero refs). The real
   collision system is a custom quantized-AABB-tree ray caster in vmtext
   (FUN_7f0686d8 → 7f067e60 → 7f0650d0/414 → 7f2546e8 → 7f259760
   Möller–Trumbore, 3×u16 into a float pool).

3. **How the collision is determined (the thing we wanted all along):**
   each level's active world is a **collision model** — the runtime builds
   it from the level's data at load:
   - The model object (e.g. 0x81257158) is named **"dpl1_c1"** (level +
     collision variant) and is built by `FUN_7f2a5308` — the same
     "Collision"-symbol model builder the entity collisions use
     (live-caught: the world part's ctor 0x7f2a4db4 fires for the exact
     runtime part address through that chain at the level load).
   - It carries a list of **named AABB collision objects**, each a 0xc0-
     byte record {name, flags@+0x1c (0x0000ffff), transform matrices,
     corners}: `Collision_`, `Collision_nopathfind1`, `Collision_noocclude`,
     `Collision_Prison01_01`, `Collision_Pris2`, `Collision_prisy`,
     `Collision_part2`, `Collision_new01/00/02/03`, `Collision_woo`, ...
     The name suffixes encode behavior (noocclude, nopathfind, ...).
   - The same 0xc0-record format is what the level files' `Database`
     records contain ("dpl1_04" = Pris_S4_01..26, "dpl1_01" = Pris_S1, ...)
     — the Database = the object-instance list with transforms.
   - The compiled world mesh (float pool + u16 triangle table, e.g.
     11379 verts / 5991 tris in 3 layers 0x27/0x26/0x7) = the collidable
     surfaces, compiled as placed instances of the W0C0M mesh templates
     (mesh verts + integer placement offsets — no rotation, no scale).
   - `levelnfo.trb` names the active level ("dpworld_level04_01_Detail").
   - The file `Collision` symbols are all EMPTY stubs {count=0}; the model
     is materialized at load from the Database instance lists + W0C0M
     display data — NTU does NOT use the Barnyard TModelCollisionData path.

4. **"Much of the visual has no in-game collision" is by design.** The
   collision = the collision model (named Collision_* volumes + collidable
   surfaces) only; display-only meshes have no collision object. Playtesting
   matches: visual ≈ collision with a few extras (one invisible wall, two
   invisible floors = collision volumes without visible meshes).

## Still open (honest list)

- The exact compilation of Database instances → world mesh (pool ordering,
  per-object placement derivation).
- The shared-pool meshes (posIdx ≥ own chunk; pools live in other chunks) —
  the extractor's JSON pools are wrong for ~76/209 Level01_04 meshes.
- The precise semantics of the 3 runtime layer flags (0x27/0x26/0x7) vs the
  object-name behavior suffixes.

## History (why the old notes say what they say)

Earlier sessions treated the per-mesh data blocks (the "coll" arrays, the
3-byte u8-triple "walkmesh", the 4-byte (flag,x,y,z) "footprints") as a
separate collision format. Those readings were retracted: they were
structural heuristics never confirmed in the DOL. The bytes are the
display-mesh index records (see trb-format-notes §4 correction). The
footprint JSONs/overlays were removed in the blank-slate cleanup; only the
raw "coll" byte arrays survive in the web JSONs (`collFormat: "unknown"`).

## 2025-xx: Route A→B pipeline + new strip decode (trb2ram.py)

`scripts/trb/trb2ram.py` = the Route A decoder (TRB → RAM model → viewer JSON,
route B = `--json`). Verified byte-exact against `/tmp/rt_pool.bin` +
`/tmp/rt_idx.bin` (the s02 RAM dump ground truth).

**Newly cracked — the 0x98 strip block is MIXED-WIDTH:**
- Header: `[0x98][u16 cnt]`.
- Quad 1: 6 records × 4 bytes, posIdx at payload byte 1 → walk `(a,b,c,X,d,e)`;
  the 4th position is a restart marker, the runtime rewrites it to the 3rd
  index → tri-verts `(a,b,c,c,d,a)`.
- Subsequent quads: 5 records × 3 bytes, posIdx at byte 0 → walk
  `(a',b',c',d',X')` with the closing index implicit → tri-verts
  `(b',c',a',a',d',b')`.
- Verified on W0C0M113's second quad: file `(1,4,5,0,0)` → runtime
  `(4,5,1,1,0,4)` = the L-panel's second half (the q0,q1,p1,p0 corners).

**Dedup rules (the runtime appends tri-verts to the global pool; the rule
varies per object — the walker tries R1/R2/R3/R4 and the ground truth picks):**
- R1: append everything. R2: value-dedup vs the current pool.
- R3: a,b,c,d append iff ∉ P0; c-dupe/closing-a append only when P0 empty.
- R4: append iff ∉ P0 (pool at the object's start).

**Pool encodings:** s16 triples (integer coords) for most meshes; f32 (×64)
and z/5 (the ×5 z-scale) variants tried for the slope/quantized meshes.

**Verified chain (byte-exact):** 6 objects / 43 pool verts — the floor quad
(W0C0M113 @ O1, O1+768), the L-panel (W0C0M113 full @ O3 = (-5120,-11200,384)),
more quads. STALLS at pool 43 = the first slope/wedge mesh — its file record
is not locatable in the 8 DP1 TRBs under any pool encoding yet (the wedge's
z = 265.6 with an x-diff of 192 and y-diff of 16 — likely a third pool format
or a source outside these TRBs).

**Still open:** (1) the slope-pool encoding / wedge source; (2) the file-side
instance list (the "Collision" resource = volume records + u16 W0C0M
mesh-ref arrays) — the runtime compiles the pool/idx from it, the file copy
has not been located (not a 0x1c-stride section in L04; Entities.trb = entity
names; levelnfo.trb = 152-byte stub). The walker = the verification harness;
the release decoder = the instance list once located.

## 2025-xx: MULTIPASS WIN — the collision source = AssetsAuto.nta (not the TRBs!)

The user-directed multipass ("detect the data in RAM while counting frames")
cracked the wedge stall AND exposed the walker's wrong-source assumption:

**Pass 1 — build window by frame counting** (`emulation.run_frames` +
`memchecks.set` write-watch on the pool region, from s01):
- The collision world (pool + idx) is written **in a SINGLE frame** — all 64
  first verts appear in one frame (~695 frames after s01 in the first
  progression; the build frame varies per progression — re-derive each run).
- s03 already has the world fully built (part 0x81282620, pool count 11379).

**Pass 2 — catch the append's source** (memcheck on pool[43].x = 0x81258508
= the wedge's first vert; `ppc.registers` at the pause):
- pc = 0x8000a810 (a DOL copy helper), r9 = dest 0x81258508 (pool[43]),
  r7 = 0xC0FFF000 (the value), **r4 = 0x809b4360 = the SOURCE pointer**.
- The source = the RAM file cache of **AssetsAuto.nta** ("NTA-File",
  DPWorld_Level04_01_Detail — the ACTIVE level).
- The wedge pool = **f32 triples at ×64 scale**: (-8, 28.0625, 0),
  (-11, 28.0625, 0), (-11, 28.0625, 4.15)... = the runtime values EXACTLY.

**THE WALKER'S ERROR**: the "per-object offsets" and "dedup rules" were
artifacts of reading the WRONG source (the trb W0C0M s16 display records).
The real source = the nta f32 pools, copied 1:1 (no offsets, no dedup).
The trb W0C0M113 matches on objects 1-3 = the same geometry in both
representations (display s16 vs collision f32), not the actual pipeline.

**The nta layout** (AssetsAuto.nta):
- Header "NTA-File" + level name + name directory
  ("DPWorld_Collision_Level01_01", "DPWorld_Level01_01/01a/02/02a/03/04").
- Concatenated f32 pool stream (floor pool @ 0x21ab1c, wedge pool @ 0x21ad20
  = 12 triples incl. the 3rd-quad dupes, next mesh @ 0x21adb0, ...).
- Concatenated u16 idx stream (wedge idx @ 0x23c0e0 = 18 u16s = 3 quads:
  43-50 + the (51,52,53,53,54,51) side face — the runtime copies it directly).
- Tail = offset table ending in a "BMYS" chunk descriptor ("Main").

**Builder record structure** (FUN_7f2a5308 decompile):
- "Collision" resource: count@+0, records@+4.
- Part record (0x1c-stride): 0x14 bytes (AABB), mesh-count@+0x14,
  mesh-records@+0x18.
- Mesh record (0x18-stride): name@+0, fields@+8/+0xc, count@+0x10,
  idx-data@+0x14 (the u16 copy loop = the idx; the pool = the DOL f32 copy).

**Runtime structure** (live): part 0x81282620 (0x28) → 3 layer slots
(0x24-stride @ 0x81282658): flags 0x27/0x26/0x7, tri counts 5735/74/182,
idx @ 0x81282f68; global pool 0x81258304 (11379) + idx 0x81279868 (17973).

**Release decoder** = parse the nta's Collision resource → parts → mesh
records → pools (f32×64) + idx (u16) in record order → the 1:1 runtime
pool/idx. The chained walker (trb2ram.py) is superseded. Remaining: the
nta section table (where the records array lives in the file) + the
offset-base for the records' pointers.

**Layer names (live-read) — the flag→behavior-suffix mapping RESOLVED:**
- layer 0: "default" (flag 0x27, 5735 tris, start 0)
- layer 1: "collision_nopathfind" (flag 0x26, 74 tris, start 5735)
- layer 2: "collision_noocclude" (flag 0x7, 182 tris, start 5809)
The runtime layer records (0x24-stride @ 0x81282658): name-struct, start
offset, tri count, shared method ptr 0x80197624, idx ptr, flag.

**Remaining for the release decoder:** the nta's section table (the mesh-
record array location in the file + the pointer base — the file's record
pointers are relative, the RAM's = resolved absolute).

## 2025-xx: RELEASE DECODER — 1:1 from the game data (no hardcoded geometry)

`scripts/trb/nta2json.py` parses `AssetsAuto.nta` and emits the viewer JSON
with **ZERO hardcoded collision geometry**:

- Resource header @ 0x21aac0: {poolcnt=11379, data_len=140136, idxcnt=17973,
  layercnt=3} — found structurally (validated by layer counts + idx/pool
  relations, so other levels' ntas should work too).
- pool = f32 triples @ header+0x5c (×64 scale).
- idx = u16 triples @ pool + poolcnt×12.
- 3 layer records @ header+0x10 (0x18 each): tri counts @ +0x10 = 5735/74/182.

Verified:
- `pool MATCH: True` + `idx MATCH: True` vs /tmp/rt_pool.bin + /tmp/rt_idx.bin
  (the s02 RAM dump) — the full 11379-vert pool and 17973-u16 idx are
  byte-identical.
- The emitted viewer JSON == the runtime-dump JSON except the mesh names
  (ours = the real runtime strings "default" / "collision_nopathfind" /
  "collision_noocclude").

Installed as web/collision/dannyphantomlevel1-coll.json, LOAD_VERSION 19.
The chained walker (trb2ram.py) is superseded. Remaining hardcoded = only
the layer flags/names/level-name constants (see still_hardcoded.md).

## 2025-xx: Whole-game coverage — 9/15 levels decode from AssetsAuto.nta

The structural header search now handles variable layer counts (1-3) and the
pool-offset = header + 0x10 + layercnt*0x18 + 4 (records end). Batch-decoded
all 15 levels' ntas:

- **9 decodable**: dannyphantomlevel1/3, JimmyNeutronLab, JimmyNeutronLevel1_01,
  SpongeBobLevel1/2/3, TimmyTurnerLevel1/2 — pool verts 6603-27492, layers 1-3.
- **6 without** the collision resource: dannyphantomlevel2/4, JimmyNeutronLevel4,
  SpongeBobLevel4, TimmyTurnerLevel4, TestWorld — their ntas are entity-assets
  only (the {count, name, ...} entity table, e.g. "DW_02_cafedoors"), and the
  level-2's Detail trb/ttl and levelnfo also lack the {poolcnt...} header.
  Likely unfinished levels or collision built at runtime from entities.

Per-level viewer JSONs generated (web/collision/<level>-coll.json, LOAD_VERSION
20). The viewer's loadCollLines already fetches <dir>-coll.json per level and
gracefully skips missing ones (the 6 = no overlay). The level-1 JSON stays
byte-exact vs the RAM dump. Layer flags/names for 1-2-layer levels = the first
N of the hardcoded (0x27/0x26/0x7, default/nopathfind/noocclude) — see
still_hardcoded.md.
