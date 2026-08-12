# TRB collision hypothesis test — "same as Barnyard?"

> Date: this session. Question: *"Assume all of our notes and research about
> collision in the current format are wrong, and it uses the exact same as
> Barnyard [Toshi TModel]. Can we test this assumption?"*
>
> Method: parse the actual GameCube TRB with the OpenBarnyard `TTRB`/
> `TTMDBase` structs + relocation (`RELC`) data, and cross-check the DOL.
> Sources of truth used: the TRB bytes, the DOL bytes, and the
> OpenBarnyard decomp (Barnyard = Blue Tongue Software — the same studio
> that made Nicktoons Unite!, per the `P7\n# File created by Blue Tongue
> Software's AC.` string at DOL 0x80042FEC).

## Verdict: the *container* is identical to Barnyard; the collision mesh *format* is unknown

> ⚠️ SUPERSEDED (2025-08 live session): the container-vs-Barnyard
> comparison below stands, but the collision question is RESOLVED — see
> `asset-extract/docs/collision-runtime.md` §"HOW THE COLLISION IS ACTUALLY
> DETERMINED" and trb-format-notes §4f. NTU has no per-mesh collision
> format: the collision = the level's collision model (named "Collision_*"
> AABB volume objects from the Database instance records + the compiled
> display-mesh surfaces), queried by a vmtext custom AABB-tree ray caster.
> The Barnyard TModelCollisionData path is NOT used (the `Collision` symbol
> is an empty stub in every game TRB). The "coll" byte arrays = display-mesh
> index records.

### ✅ Confirmed identical to Barnyard (byte-level, validated)

1. **TTRB container**: `TSFB` (BE) → `HDRX` chunk table (16-byte records,
   u32 size + pad) → `SECT` (section data) → `RELC` → `SYMB`. FourCCs
   stored LE ("FBRT" = TRBF, "XRDH" = HDRX, "CLER" = RELC, "BMYS" = SYMB).
2. **RELC**: `{u32 offset, u32 section}` entries; loader does
   `*ptr += base(section)`. All entries in this TRB are section 0. This
   matches Barnyard's `TTRB::ProcessForm` RELC handling exactly.
3. **SYMB**: `{u16 hdrx, u16 nameOff, u16 pad, i16 nameHash, u32 dataOff}`
   with names after `4 + 12*count`. All **92/92** symbols validated against
   Barnyard's `HashString` (`hash*0x1f + char`, 16-bit) — the exact same
   layout. (`scripts/trb/dump_symbols.py`)
4. **Symbol set**: `Header`, `Database`, `SkeletonHeader`, `Skeleton`,
   `Materials`, `Collision` + 86 `W0C0M0..85` mesh symbols — the same
   symbol names `TModel::LoadTRB` / `TModel::GetSymbol` uses in Barnyard.
5. The **`Collision` symbol exists** and its data begins with a small
   header whose pointer fields are RELC-relocated:
   `+0x36C0: { 0, 1, ptr→+0x36CC, ptr→+0x36D0 }` followed by ~0x74 zero
   bytes. (Interpretation below.)

### The collision mesh encoding — UNKNOWN (retracted)

Barnyard `TTMDBase::CollisionMesh` is:
`{ i32 boneID; TVector3* pVerts; u32 nVerts; u16* pIndices; u32 nIndices;
u32 nCollTypes; CollisionGroup* pGroups }`, with `CollisionGroup
{ pszName, iUnk1, iUnk3, uiNumFaces, iSomeCount, pS1 }` and
`CollisionTypeS1 { u16, u16 }` — float vertex pools + u16 indexed faces +
named material groups + 4-byte S1 pairs.

Earlier this session this doc claimed the per-mesh data block (the "C-block"
at record +0x20) was `[0x98:u8 marker][u16 count][count × 3 bytes (x, y, z)
quantized vertices]` and used block-overlap arguments to call that "fact".
That reading is a structural heuristic and is probably wrong; without it we
cannot conclude anything about how — or whether — the per-mesh blocks encode
collision. Both that model and the earlier 4-byte `[flag,x,y,z]` s8 model
(`docs/collision-status.md`) are unverified; the collision mesh format is
**unknown**.

### The `collision_*` strings and CollisionMask table

The DOL `collision_*` strings at 0x8004FC90 (`collision_char`,
`collision_water`, `collision_goo`, `collision_phase`, `collision_damage`,
`collision_kback`, `collision_kbackdam`, `collision_nopathfind`,
`collision_pathonly`, `collision_cameraonly`, `collision_noocclude`) are
**entity/trigger property names** (the same property-pool mechanism as the
Ents TRB), not per-vertex mesh collision flags. The DOL CollisionMask table
at 0x8004FAB4 is `{name, mask}` = `CollisionMask_Allies=0x1, Enemies=0x2,
Phased=0x10, Shield=0x20, Players=0x100` — entity collision *layers*, a
different system. The `(s8+128)/255` bbox dequant was never confirmed in
code and is not assumed anymore.

## The Collision symbol header — what it might be

Data at `SECT+0x36C0` (relocated):
`0, 1, ptr→+0x36CC, ptr→+0x36D0` then 0x74 zero bytes, then the mesh
pointer table at `+0x3748: { 0x56 (86), ptr→+0x3754, ... }` where
`+0x3754` holds 86 relocated pointers to the mesh records.

Most consistent reading with Barnyard: `{ version/flags=0, iNumMeshes=1,
pMeshes→+0x36CC }` where the single "CollisionMesh" at `+0x36CC` is
`{ pVerts→+0x36D0, 0, 0, 0, 0, 0 }` — an *empty* collision mesh (the
level model carries a skeleton — `SkeletonHeader` "SB_D_01_01" — so the
level is a TModel; its TModel-level collision is empty; where the real
world collision data lives is unknown).

## DOL cross-check status

The exact `"Collision"` literals exist at `0x800500A5` and `0x800AF044`
but have **no code references** (verified with the Ghidra references
query and a full lis/addi+ori scan of all text sections; the query is
proven working via `/vmtext.bin` @ 0x800424E8 → caller 0x80041600).
Same for `"Header"`, `"Materials"`, `"W%dC%dM%d"`, `"Database"`,
`"Terrain_%d"`, the CollisionMask table and the `collision_*` strings.
The level loader therefore resolves symbol names through the string
pool (`data\strpool.dat`), not rodata literals.
The OpCODE library is present (`"Collision might report wrong results!"`
@ 0x800A9E38) — consistent with the DOL feeding collision data into
Opcode, but the TRB-side reader was not located this session.

## Tooling added

- `scripts/trb/dump_symbols.py` — TTRB symbol table dump/validate (hash
  checked, resolves `Collision` etc. to chunk+offset).
- `scripts/trb/decode_collision.py` — RELC-aware decode of the Collision
  symbol + mesh pointer slots.
- Note: the u8-triple C-block verifier (`verify_cblocks.py`) and the other
  byte-interpretation tools were removed in the blank-slate cleanup — only
  the raw byte extraction (`trb_mesh.py::mesh_collision`) survives (see
  docs/collision-status.md).

## Recommended next steps

1. **Find the real collision reader** in the DOL (Dolphin trace of the
   level load / vtable walk of `ANTWorldMesh`) before encoding any
   collision format; both byte-readings are unverified.
2. Keep the Barnyard `S1` u16-pair "TODO" (OpenBarnyard `TTMDBase.h`)
   open — whether the per-mesh blocks are the same quantized-vertex strip
   family is unknown.
3. Optional: string-pool theory check — load `data/strpool.dat` from the
   disc and confirm `"Collision"`/`"W%dC%dM%d"` resolve from it.
