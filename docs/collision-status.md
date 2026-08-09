# Collision status

> Live-debugging tooling + protocol knowledge: `scripts/dol/gdbstub/README.md`.
> Read its ⚠️ OPERATIONAL DOCTRINE before touching the stub: the connection
> is ONE-SHOT — no port probing, one persistent driver process, all probes
> through its command channel.

# Collision — status

## The collision mesh format is UNKNOWN

As of this session the collision mesh format is **unknown**. Every byte-level
reading attempted so far was an unverified structural hypothesis, and none of
them are to be treated as fact:

- the **4-byte `[flag:u8, x:s8, y:s8, z:s8]`** model with the
  `(s8+128)/255` vertex-bbox dequant (the "footprint + flags" reading) —
  never confirmed against the DOL;
- the **3-byte u8-triple** model (`[0x98][u16 count][count × 3 bytes]`
  "quantized vertices") from `docs/trb-collision-test.md` — unlikely to
  be correct.

Neither is supported by decomp or a located DOL reader. Do not encode
anything from the "coll" blocks until the real reader is found.

## What is actually known (DOL cross-referenced)

- Each mesh record carries a trailing data block (exported as each mesh's
  "coll" array in `web/collision/<level>.json`); its contents and role are
  undecoded.
- The DOL `collision_*` strings (`collision_char`, `collision_water`,
  `collision_goo`, `collision_phase`, `collision_damage`,
  `collision_kback`, `collision_kbackdam`, `collision_nopathfind`,
  `collision_pathonly`, `collision_cameraonly`, `collision_noocclude`)
  at 0x8004FC90 are **entity/trigger property names** (the same property
  pool mechanism as the Ents TRB), not per-vertex collision flags.
- The CollisionMask table at 0x8004FAB4 (`CollisionMask_Allies=0x1,
  Enemies=0x2, Phased=0x10, Shield=0x20, Players=0x100`) is entity
  collision *layers* — a different system.
- The OpCODE library is present in the DOL ("Collision might report wrong
  results!" @0x800A9E38); the engine builds a runtime collision model from
  parsed data, but the TRB-side reader was not located.
- `web/collision/<Level>_footprints.json` and the viewer's footprint
  overlay were generated under the retracted hypotheses and have been
  REMOVED (blank slate). Only the raw byte extraction survives:
  `asset-extract/tools/trb_mesh.py` `mesh_collision()` exports each mesh's
  collision block as a flat "coll" byte array in the web JSON
  (`collFormat: "unknown"`), with no record-width, alignment, or
  coordinate interpretation. The interpretation tools (gen_footprints.py,
  validate_coll.py, analyze_footprints.py, trb_collision.py,
  verify_cblocks.py, decode_hypothesis.py) were deleted.

## Next steps

- Find the real collision reader in the DOL (vtable-reachable region
  0x800A9xxx / Dolphin trace) before re-encoding anything.
- The Ghidra project exists at `analysis/ghidra/` but the collision-
  processing code lies in a vtable-reachable region that the static
  analyzer did not identify as functions.
