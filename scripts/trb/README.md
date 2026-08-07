# TRB scanners

Scripts that hunt for the mesh/position pools inside the game's TRB container
files (e.g. `nicku-ntsc/P-GNOE/files/Data/SpongeBobLevel1/SBWorld_Detail_Level01_01.trb`).

A TRB starts with a header: `u32 hdrx_size` at 0x10, `u32 n_chunks` at 0x18,
then `n` 16-byte chunk-size records at 0x20; chunk data starts at
`hdrx_size + 20 + 8`. Chunk 0 is a big u16/u32 word pool that the per-mesh
index records reference.

| Script        | Approach                                                              |
|---------------|-----------------------------------------------------------------------|
| `scan_pool.py`| Validates candidate pool offsets against *known* mesh geometry: it reads a verified mesh's `posIdx` stream (road strip, x≈9.9–11.9, z≈0.1–9.0, y≈0) and scans every offset × stride × format for a pool whose indexed points land in that box. Clean, documented, canonical. |
| `w2_scan.py`  | Blind structural scan of chunk 0: for each stride phase (s16/u16/f32 views, stride 3/4/6/8 words) finds the longest *suffix run* of valid + consecutive-smooth values and reports the best candidate pool starts. Useful when geometry isn't known yet. |

Both take the TRB path from `NICK_EXTRACT` (default: mounted disc-extract
root) — see the top-level [`scripts/README.md`](../README.md).

Earlier iterations (`poolscan.py`, `poolscan2.py`, `w2_scan2/3/4.py`) were
superseded by these two and deleted.
